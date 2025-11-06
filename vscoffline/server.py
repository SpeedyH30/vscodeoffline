import os, sys, time, json, glob, gzip
import falcon
from packaging.version import Version
import logging as log
from wsgiref import simple_server
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from threading import Event, Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import vsc

# Configure logging for both direct execution and gunicorn
log.basicConfig(
    format='[%(levelname)s %(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=log.INFO,
    force=True  # Override any existing configuration
)
# Ensure logs go to stdout
log.getLogger().handlers[0].setStream(sys.stdout)


class VSCUpdater(object):

    def on_get(self, req, resp, platform, buildquality, commitid):
        updatedir = os.path.join(vsc.ARTIFACTS_INSTALLERS, platform, buildquality)
        if not os.path.exists(updatedir):
            log.warning(f'Update build directory does not exist at {updatedir}. Check sync or sync configuration.')
            resp.status = falcon.HTTP_500
            return
        latestpath = os.path.join(updatedir, 'latest.json')
        latest = vsc.Utility.load_json(latestpath)
        if not latest:
            resp.content = 'Unable to load latest.json'
            log.warning(f'Unable to load latest.json for platform {platform} and buildquality {buildquality}')
            resp.status = falcon.HTTP_500
            return
        if latest['version'] == commitid:
            # No update available
            log.debug(f'Client {platform}, Quality {buildquality}. No Update available.')
            resp.status = falcon.HTTP_204
            return
        name = latest['name']
        updatepath = vsc.Utility.first_file(updatedir, f'vscode-{name}.*')
        if not updatepath:
            resp.content = 'Unable to find update payload'
            log.warning(f'Unable to find update payload from {updatedir}/vscode-{name}.*')
            resp.status = falcon.HTTP_404
            return
        if not vsc.Utility.hash_file_and_check(updatepath, latest['sha256hash']):
            resp.content = 'Update payload hash mismatch'
            log.warning(f'Update payload hash mismatch {updatepath}')
            resp.status = falcon.HTTP_403
            return
        # Url to get update
        latest['url'] = vsc.URLROOT + updatepath
        log.debug(f'Client {platform}, Quality {buildquality}. Providing update {updatepath}')
        resp.status = falcon.HTTP_200
        resp.media = latest

class VSCBinaryFromCommitId(object):

    def on_get(self, req, resp, commitid, platform, buildquality):
        updatedir = os.path.join(vsc.ARTIFACTS_INSTALLERS, platform, buildquality)
        if not os.path.exists(updatedir):
            log.warning(f'Update build directory does not exist at {updatedir}. Check sync or sync configuration.')
            resp.status = falcon.HTTP_500
            return
        jsonpath = os.path.join(updatedir, f'{commitid}.json')
        updatejson = vsc.Utility.load_json(jsonpath)
        if not updatejson:
            resp.content = f'Unable to load {jsonpath}'
            log.warning(resp.content)
            resp.status = falcon.HTTP_500
            return
        name = updatejson['name']
        updatepath = vsc.Utility.first_file(updatedir, f'vscode-{name}.*')
        if not updatepath:
            resp.content = f'Unable to find update payload from {updatedir}/vscode-{name}.*'
            log.warning(resp.content)
            resp.status = falcon.HTTP_404
            return
        if not vsc.Utility.hash_file_and_check(updatepath, updatejson['sha256hash']):
            resp.content = f'Update payload hash mismatch {updatepath}'
            log.warning(resp.content)
            resp.status = falcon.HTTP_403
            return
        # Url for the client to fetch the update
        resp.set_header('Location', vsc.URLROOT + updatepath)
        resp.status = falcon.HTTP_302

class VSCRecommendations(object):

    def on_get(self, req, resp):
        if not os.path.exists(vsc.ARTIFACT_RECOMMENDATION):
            resp.status = falcon.HTTP_404
            return
        resp.status = falcon.HTTP_200
        resp.content_type = 'application/octet-stream'
        with open(vsc.ARTIFACT_RECOMMENDATION, 'r') as f:
            resp.text = f.read()

class VSCMalicious(object):

    def on_get(self, req, resp):
        if not os.path.exists(vsc.ARTIFACT_MALICIOUS):
            resp.status = falcon.HTTP_404
            return
        resp.status = falcon.HTTP_200
        resp.content_type = 'application/octet-stream'
        with open(vsc.ARTIFACT_MALICIOUS, 'r') as f:
            resp.text = f.read()

class VSCGallery(object):

    def __init__(self, interval=3600):
        self.extensions = {}
        self.interval = interval
        self.loaded = Event()
        self.extensions_lock = Lock()
        self.start_time = time.time()
        
        # Refresh tracking
        self.last_refresh_time = 0
        self.next_refresh_time = time.time() + interval
        self.refresh_lock = Lock()
        
        # Indexing status tracking
        self.indexing = Event()  # Set when actively indexing
        self.indexing_progress = {'current': 0, 'total': 0, 'stage': 'idle'}
        self.indexing_lock = Lock()
        
        cache_dir = os.environ.get('CACHE_DIR', vsc.ARTIFACTS)
        self.cache_file = os.path.join(cache_dir, 'extensions_cache.json.gz')
        os.makedirs(cache_dir, exist_ok=True)
        
        self.update_worker = Thread(target=self.update_state_loop, args=())
        self.update_worker.daemon = True
        self.update_worker.start()

    def get_cache_mtime(self):
        """Get the modification time of the cache file, or 0 if it doesn't exist"""
        try:
            return os.path.getmtime(self.cache_file)
        except OSError:
            return 0

    def get_extensions_mtime(self):
        """Get the most recent modification time of any extension directory"""
        try:
            max_mtime = 0
            with os.scandir(vsc.ARTIFACTS_EXTENSIONS) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        dir_mtime = entry.stat().st_mtime
                        max_mtime = max(max_mtime, dir_mtime)
                        # Also check for updated.json which triggers updates
                        updated_json = os.path.join(entry.path, 'updated.json')
                        if os.path.exists(updated_json):
                            max_mtime = max(max_mtime, os.path.getmtime(updated_json))
            return max_mtime
        except OSError:
            return float('inf')  # Force cache miss if we can't check

    def load_cache(self):
        """Load extensions from cache if it's newer than the extensions directory"""
        cache_mtime = self.get_cache_mtime()
        extensions_mtime = self.get_extensions_mtime()
        
        if cache_mtime > extensions_mtime and os.path.exists(self.cache_file):
            try:
                log.info('Loading extensions from compressed cache (this should be fast)...')
                with gzip.open(self.cache_file, 'rt', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                with self.extensions_lock:
                    self.extensions = cached_data
                
                log.info(f'✅ Loaded {len(self.extensions)} extensions from cache in seconds!')
                return True
            except Exception as e:
                log.warning(f'Failed to load cache: {e}')
        
        return False

    def save_cache(self):
        """Save current extensions to cache"""
        try:
            with self.extensions_lock:
                cache_data = self.extensions.copy()
            
            # Write to temporary file first, then rename for atomicity
            temp_file = self.cache_file + '.tmp'
            with gzip.open(temp_file, 'wt', encoding='utf-8') as f:
                json.dump(cache_data, f, separators=(',', ':'))  # Compact format
            
            os.rename(temp_file, self.cache_file)
            log.info(f'Saved {len(cache_data)} extensions to compressed cache')
        except Exception as e:
            log.warning(f'Failed to save cache: {e}')

    def process_single_extension(self, extensiondir):
        """Process a single extension directory and return the processed extension or None"""
        try:
            # Load the latest version of each extension
            latestpath = os.path.join(extensiondir, 'latest.json')
            latest = vsc.Utility.load_json(latestpath)

            if not latest:
                return None
            
            # Early validation - must have required fields
            if 'identity' not in latest or 'versions' not in latest or not latest['versions']:
                return None

            latest = self.process_loaded_extension(latest, extensiondir)

            if not latest:
                return None

            # Determine the latest version
            latestversion = latest['versions'][0]

            # Find other versions - use scandir for better performance
            try:
                with os.scandir(extensiondir) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False) and entry.name != '.':
                            versionpath = os.path.join(entry.path, 'extension.json')
                            if not os.path.exists(versionpath):
                                continue
                                
                            vers = vsc.Utility.load_json(versionpath)
                            if not vers:
                                continue
                                
                            vers = self.process_loaded_extension(vers, extensiondir)

                            # If this extension.json is actually the latest version, then ignore it
                            if not vers or latestversion == vers['versions'][0]:
                                continue

                            # Append this other possible version
                            latest['versions'].append(vers['versions'][0])
            except OSError:
                # If we can't list the directory, just use the latest version
                pass

            # Sort versions
            latest['versions'] = sorted(latest['versions'], key=lambda k: Version(k['version']), reverse=True)

            return latest
        except Exception as e:
            log.debug(f'Error processing extension {extensiondir}: {e}')
            return None

    def update_state(self):
        if self.load_cache():
            return
            
        # Set indexing status
        self.indexing.set()
        
        extension_dirs = []
        with os.scandir(vsc.ARTIFACTS_EXTENSIONS) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    latest_path = os.path.join(entry.path, 'latest.json')
                    if os.path.exists(latest_path):
                        extension_dirs.append(entry.path)
        
        total_extensions = len(extension_dirs)
        
        # Update indexing progress
        with self.indexing_lock:
            self.indexing_progress = {'current': 0, 'total': total_extensions, 'stage': 'scanning'}
        
        log.info(f'🔄 No valid cache found - processing {total_extensions} valid extensions from scratch...')
        log.info(f'💡 This may take a while, but subsequent starts will be much faster!')
        
        max_workers = min(32, (os.cpu_count() or 1) + 4)
        processed_count = 0
        new_extensions = {}
        
        # Update progress to processing stage
        with self.indexing_lock:
            self.indexing_progress = {'current': 0, 'total': total_extensions, 'stage': 'processing'}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dir = {executor.submit(self.process_single_extension, extensiondir): extensiondir 
                           for extensiondir in extension_dirs}
            
            batch_size = 100
            batch_extensions = {}
            
            for future in as_completed(future_to_dir):
                processed_count += 1
                
                # Update progress
                with self.indexing_lock:
                    self.indexing_progress['current'] = processed_count
                
                if processed_count % 50 == 0 or processed_count == total_extensions:
                    extensiondir = future_to_dir[future]
                    extension_name = os.path.basename(extensiondir.rstrip('/'))
                    log.info(f'Processed {processed_count}/{total_extensions} ({processed_count/total_extensions*100:.1f}%) - Latest: {extension_name}')
                
                try:
                    latest = future.result()
                    if latest:
                        name = latest['identity']
                        new_extensions[name] = latest
                        batch_extensions[name] = latest
                        
                        if len(batch_extensions) >= batch_size or processed_count == total_extensions:
                            with self.extensions_lock:
                                self.extensions.update(batch_extensions)
                            batch_extensions.clear()
                        
                        if processed_count % 20 == 0:
                            log.debug(f'Loaded extension: {name}')
                except Exception as e:
                    extensiondir = future_to_dir[future]
                    extension_name = os.path.basename(extensiondir.rstrip('/'))
                    log.warning(f'Exception processing {extension_name}: {e}')
        
        with self.extensions_lock:
            self.extensions = new_extensions
        
        # Update progress to caching stage
        with self.indexing_lock:
            self.indexing_progress = {'current': total_extensions, 'total': total_extensions, 'stage': 'caching'}
        
        log.info(f'Loaded {len(self.extensions)} extensions')
        self.save_cache()
        
        # Clear indexing status
        with self.indexing_lock:
            self.indexing_progress = {'current': 0, 'total': 0, 'stage': 'idle'}
        self.indexing.clear()

    def process_loaded_extension(self, extension, extensiondir):
            name = extension['identity']
            base_uri = vsc.URLROOT + extensiondir
            for version in extension["versions"]:
                if "targetPlatform" in version:
                    asseturi = f"{base_uri}/{version['version']}/{version['targetPlatform']}"
                else:
                    asseturi = f"{base_uri}/{version['version']}"

                version['assetUri'] = asseturi
                version['fallbackAssetUri'] = asseturi
                for asset in version['files']:
                    asset['source'] = f"{asseturi}/{asset['assetType']}"

            stats = {
                'averagerating': 0,
                'install': 0,
                'weightedRating': 0
            }
            if 'statistics' not in extension or not extension['statistics']:
                log.debug(f'Statistics are missing from extension {name}, generating defaults.')
            else:
                extension_statistics = {}
                for statistic in extension['statistics']:
                    extension_statistics[statistic['statisticName']] = statistic['value']
                stats.update(extension_statistics)
            extension['stats'] = stats
            return extension

    def update_state_loop(self):
        while True:
            log.info('🔍 Checking for new extensions...')
            with self.refresh_lock:
                self.next_refresh_time = time.time()
            
            self.update_state()
            self.loaded.set()
            
            with self.refresh_lock:
                self.last_refresh_time = time.time()
                self.next_refresh_time = self.last_refresh_time + self.interval
            
            log.info(f'✅ Check complete. Next check in {vsc.Utility.seconds_to_human_time(self.interval)}')
            time.sleep(self.interval)

    def on_post(self, req, resp):
        if 'filters' not in req.media or 'criteria' not in req.media['filters'][0] or 'flags' not in req.media:
            log.warning(f'Post missing critical components. Raw post {req.media}')
            resp.status = falcon.HTTP_404
            return

        sortby = vsc.SortBy.NoneOrRelevance
        sortorder = vsc.SortOrder.Default
        criteria = req.media['filters'][0]['criteria']

        if req.media['filters'][0].get('sortOrder'):
            sortorder = vsc.SortOrder(req.media['filters'][0]['sortOrder'])

        if req.media['filters'][0].get('sortBy'):
            sortby = vsc.SortBy(req.media['filters'][0]['sortBy'])

        if sortby == vsc.SortBy.NoneOrRelevance:
            sortby = vsc.SortBy.InstallCount
            sortorder = vsc.SortOrder.Descending

        result = self._apply_criteria(criteria)
        self._sort(result, sortby, sortorder)
        resp.media = self._build_response(result)
        resp.status = falcon.HTTP_200

    def _sort(self, result, sortby, sortorder):
        if sortorder == vsc.SortOrder.Ascending:
            rev = False
        else:
            rev = True

        if sortby == vsc.SortBy.PublisherName:
            rev = not rev
            result.sort(key=lambda k: k['publisher']['publisherName'], reverse=rev)

        elif sortby == vsc.SortBy.InstallCount:
            result.sort(key=lambda k: k['stats']['install'], reverse=rev)

        elif sortby == vsc.SortBy.AverageRating:
            result.sort(key=lambda k: k['stats']['averagerating'], reverse=rev)

        elif sortby == vsc.SortBy.WeightedRating:
            result.sort(key=lambda k: k['stats']['weightedRating'], reverse=rev)

        elif sortby == vsc.SortBy.LastUpdatedDate:
            result.sort(key=lambda k: vsc.Utility.from_json_datetime(k['lastUpdated']), reverse=rev)

        elif sortby == vsc.SortBy.PublishedDate:
            result.sort(key=lambda k: vsc.Utility.from_json_datetime(k['publishedDate']), reverse=rev)

        else:
            rev = not rev
            result.sort(key=lambda k: k['displayName'], reverse=rev)

    def _apply_criteria(self, criteria):
        extensions = self.extensions.copy()
        result = []

        for crit in criteria:
            if 'filterType' not in crit or 'value' not in crit:
                continue
            ft = vsc.FilterType(crit['filterType'])
            val = crit['value'].lower()

            if ft == vsc.FilterType.Tag:
                log.info(f"Not implemented filter type {ft} for {val}")
                continue

            elif ft == vsc.FilterType.ExtensionId:
                for name in extensions:
                    if val == extensions[name]['extensionId']:
                        result.append(extensions[name])

            elif ft == vsc.FilterType.Category:
                log.info(f"Not implemented filter type {ft} for {val}")
                continue

            elif ft == vsc.FilterType.ExtensionName:
                for name in extensions:
                    if name.lower() == val:
                        result.append(extensions[name])

            elif ft == vsc.FilterType.Target:
                continue

            elif ft == vsc.FilterType.Featured:
                log.info(f"Not implemented filter type {ft} for {val}")
                continue

            elif ft == vsc.FilterType.SearchText:
                for name in extensions:
                    if val in name.lower():
                        result.append(extensions[name])
                    elif 'displayName' in extensions[name] and val in extensions[name]['displayName'].lower():
                        result.append(extensions[name])
                    elif 'shortDescription' in extensions[name] and val in extensions[name]['shortDescription'].lower():
                        result.append(extensions[name])

            elif ft == vsc.FilterType.ExcludeWithFlags:
                continue

            else:
                log.warning(f"Undefined filter type {crit}")

        if len(result) <= 0 and len(criteria) <= 2:
            log.info(f'Search criteria {criteria}')
            result = [ext for ext in extensions.values() if 'recommended' in ext and ext['recommended']]

        return result

    def _build_response(self, resultingExtensions):
        result = {
            'results': [
                {
                    'extensions': resultingExtensions,
                    'pagingToken': None,
                    'resultMetadata': [
                        {
                            'metadataType': 'ResultCount',
                            'metadataItems': [
                                {
                                    'name': 'TotalCount',
                                    'count': len(resultingExtensions)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        return result

class VSCStatus(object):
    
    def __init__(self, gallery):
        self.gallery = gallery
        self._cache = {}
        self._cache_lock = Lock()
        self._cache_ttl = 30  # 30 seconds cache
    
    def on_get(self, req, resp):
        try:
            # Check cache first for performance
            current_time = time.time()
            cache_key = 'enhanced_status_data'
            
            with self._cache_lock:
                if cache_key in self._cache:
                    cached_data, cache_time = self._cache[cache_key]
                    if current_time - cache_time < self._cache_ttl:
                        resp.media = cached_data
                        resp.status = falcon.HTTP_200
                        return
            
            # Generate enhanced status
            with self.gallery.extensions_lock:
                extension_count = len(self.gallery.extensions)
                extensions_sample = dict(list(self.gallery.extensions.items())[:100])  # Sample for stats
            
            is_loaded = self.gallery.loaded.is_set()
            is_indexing = self.gallery.indexing.is_set()
            
            # Get indexing progress
            indexing_info = {'current': 0, 'total': 0, 'stage': 'idle'}
            with self.gallery.indexing_lock:
                indexing_info = self.gallery.indexing_progress.copy()
            
            # Calculate uptime
            start_time = getattr(self.gallery, 'start_time', current_time)
            uptime_seconds = int(current_time - start_time)
            
            # Cache information
            cache_info = {'exists': False, 'size_mb': 0, 'age_hours': 0}
            if os.path.exists(self.gallery.cache_file):
                try:
                    cache_stat = os.stat(self.gallery.cache_file)
                    cache_info.update({
                        'exists': True,
                        'size_bytes': cache_stat.st_size,
                        'size_mb': round(cache_stat.st_size / 1024 / 1024, 2),
                        'age_hours': round((current_time - cache_stat.st_mtime) / 3600, 1),
                        'created': int(cache_stat.st_mtime)
                    })
                except OSError:
                    cache_info['exists'] = True  # File exists but can't stat
            
            # Basic extension statistics (from sample only for speed)
            publishers = set()
            categories = {}
            total_versions = 0
            
            for ext_name, ext_data in extensions_sample.items():
                if isinstance(ext_data, dict):
                    # Count versions
                    if 'versions' in ext_data and isinstance(ext_data['versions'], list):
                        total_versions += len(ext_data['versions'])
                    
                    # Publisher info
                    if 'publisher' in ext_data and isinstance(ext_data['publisher'], dict):
                        pub_name = ext_data['publisher'].get('publisherName')
                        if pub_name:
                            publishers.add(pub_name)
                    
                    # Categories
                    if 'categories' in ext_data and isinstance(ext_data['categories'], list):
                        for category in ext_data['categories'][:3]:  # Limit categories per extension
                            categories[category] = categories.get(category, 0) + 1
            
            # Estimate total versions from sample
            if extensions_sample and extension_count > 100:
                avg_versions_per_ext = total_versions / len(extensions_sample)
                estimated_total_versions = int(avg_versions_per_ext * extension_count)
            else:
                estimated_total_versions = total_versions
            
            # Get refresh timing information
            refresh_info = {}
            with self.gallery.refresh_lock:
                last_refresh = self.gallery.last_refresh_time
                next_refresh = self.gallery.next_refresh_time
                
                if last_refresh > 0:
                    refresh_info['last_refresh_timestamp'] = int(last_refresh)
                    refresh_info['last_refresh_ago_seconds'] = int(current_time - last_refresh)
                    refresh_info['last_refresh_ago'] = vsc.Utility.seconds_to_human_time(int(current_time - last_refresh))
                else:
                    refresh_info['last_refresh'] = 'Never (startup in progress)'
                
                refresh_info['next_refresh_timestamp'] = int(next_refresh)
                refresh_info['next_refresh_in_seconds'] = max(0, int(next_refresh - current_time))
                refresh_info['next_refresh_in'] = vsc.Utility.seconds_to_human_time(max(0, int(next_refresh - current_time)))
                refresh_info['is_checking_now'] = is_indexing
            
            status = {
                'status': 'indexing' if is_indexing else ('ready' if is_loaded else 'loading'),
                'loading_complete': is_loaded,
                'indexing_active': is_indexing,
                'indexing_progress': indexing_info if is_indexing else None,
                'timestamp': int(current_time),
                'server_uptime_seconds': uptime_seconds,
                'server_uptime_hours': round(uptime_seconds / 3600, 1),
                
                'refresh': refresh_info,
                
                'extensions': {
                    'loaded_count': extension_count,
                    'estimated_total_versions': estimated_total_versions,
                    'sample_size': len(extensions_sample),
                    'unique_publishers': len(publishers),
                    'top_categories': dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10])
                },
                
                'cache': cache_info,
                
                'configuration': {
                    'cache_location': self.gallery.cache_file,
                    'update_interval_seconds': self.gallery.interval,
                    'update_interval_hours': round(self.gallery.interval / 3600, 1),
                    'update_interval': vsc.Utility.seconds_to_human_time(self.gallery.interval),
                    'artifacts_root': vsc.ARTIFACTS,
                    'url_root': vsc.URLROOT
                }
            }
            
            # Cache the result
            with self._cache_lock:
                self._cache[cache_key] = (status, current_time)
            
            resp.media = status
            resp.status = falcon.HTTP_200
            
        except Exception as e:
            resp.media = {'error': str(e), 'status': 'error', 'timestamp': int(time.time())}
            resp.status = falcon.HTTP_500
    
    # Comprehensive status method removed - was causing performance issues

class VSCStatusPage(object):
    
    def __init__(self, content_dir, vsc_status):
        self.content_dir = content_dir
        self.vsc_status = vsc_status
    
    def on_get(self, req, resp):
        """Load status.html template and substitute placeholders with current data"""
        try:
            # Collect basic status data
            extension_count = 0
            total_versions = 0
            publishers = set()
            categories = {}
            
            try:
                with self.vsc_status.gallery.extensions_lock:
                    extensions = self.vsc_status.gallery.extensions
                    extension_count = len(extensions)
                    
                    # Sample extensions for performance (first 1000)
                    for ext_name, ext_data in list(extensions.items())[:1000]:
                        if isinstance(ext_data, dict):
                            # Count versions
                            if 'versions' in ext_data and isinstance(ext_data['versions'], list):
                                total_versions += len(ext_data['versions'])
                            else:
                                total_versions += 1
                            
                            # Publisher info
                            if 'publisher' in ext_data and isinstance(ext_data['publisher'], dict):
                                pub_name = ext_data['publisher'].get('publisherName', 'Unknown')
                                if pub_name != 'Unknown':
                                    publishers.add(pub_name)
                            
                            # Categories (sample only)
                            if 'categories' in ext_data and isinstance(ext_data['categories'], list):
                                for category in ext_data['categories'][:3]:
                                    categories[category] = categories.get(category, 0) + 1
                    
                    # If we sampled, estimate totals
                    if extension_count > 1000:
                        scaling_factor = extension_count / 1000
                        total_versions = int(total_versions * scaling_factor)
                        
            except Exception as e:
                log.warning(f"Error collecting extension statistics: {str(e)}")
            
            # Calculate status info
            is_loaded = self.vsc_status.gallery.loaded.is_set()
            is_indexing = self.vsc_status.gallery.indexing.is_set()
            
            # Get indexing progress
            indexing_info = {'current': 0, 'total': 0, 'stage': 'idle'}
            try:
                with self.vsc_status.gallery.indexing_lock:
                    indexing_info = self.vsc_status.gallery.indexing_progress.copy()
            except Exception as e:
                log.warning(f"Error getting indexing progress: {e}")
            
            if is_indexing:
                status_text = "Indexing Extensions"
                status_icon = "arrow-clockwise"
                status_class = "loading"
                status_animation = "spinning"
            elif is_loaded:
                status_text = "Server Ready"
                status_icon = "check-circle-fill" 
                status_class = "ready"
                status_animation = ""
            else:
                status_text = "Loading Extensions"
                status_icon = "hourglass-split"
                status_class = "loading"
                status_animation = ""
            
            # Calculate uptime
            current_time = time.time()
            start_time = getattr(self.vsc_status.gallery, 'start_time', current_time)
            uptime_seconds = int(current_time - start_time)
            uptime_hours = round(uptime_seconds / 3600, 1)
            
            # Loading progress
            if is_indexing:
                if indexing_info['total'] > 0:
                    percentage = round((indexing_info['current'] / indexing_info['total']) * 100, 1)
                    stage_text = {
                        'scanning': 'Scanning directories',
                        'processing': 'Processing extensions',  
                        'caching': 'Building cache'
                    }.get(indexing_info['stage'], 'Indexing')
                    loading_progress = "🔄 {}: {:,}/{:,} ({}%)".format(stage_text, indexing_info['current'], indexing_info['total'], percentage)
                else:
                    loading_progress = "🔄 Preparing to index extensions..."
            elif is_loaded:
                loading_progress = "✅ {:,} extensions loaded".format(extension_count)
            else:
                loading_progress = "⏳ Loading... {:,} extensions found".format(extension_count)
            
            # Cache status
            cache_status_text = "Unknown"
            cache_status_color = "secondary"
            cache_size_mb = 0
            cache_age_hours = 0
            
            try:
                cache_file = self.vsc_status.gallery.cache_file
                if os.path.exists(cache_file):
                    cache_stat = os.stat(cache_file)
                    cache_size_mb = round(cache_stat.st_size / 1024 / 1024, 1)
                    cache_age_hours = round((current_time - cache_stat.st_mtime) / 3600, 1)
                    cache_status_text = "Active"
                    cache_status_color = "success"
                else:
                    cache_status_text = "Not Found"
                    cache_status_color = "warning"
            except Exception as e:
                cache_status_text = "Error"
                cache_status_color = "danger"
            
            # Top categories (comma-separated string for template)
            top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:6]
            categories_list = ", ".join([f"{cat} ({count})" for cat, count in top_categories]) if top_categories else "No categories found"
            
            # Last updated timestamp
            last_updated = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            
            # Refresh timing information
            refresh_interval = vsc.Utility.seconds_to_human_time(self.vsc_status.gallery.interval)
            last_refresh_text = "Never"
            next_refresh_text = "Unknown"
            refresh_status_color = "secondary"
            
            try:
                with self.vsc_status.gallery.refresh_lock:
                    if self.vsc_status.gallery.last_refresh_time > 0:
                        last_refresh_ago = int(current_time - self.vsc_status.gallery.last_refresh_time)
                        last_refresh_text = vsc.Utility.seconds_to_human_time(last_refresh_ago) + " ago"
                        refresh_status_color = "success"
                    
                    next_refresh_in = max(0, int(self.vsc_status.gallery.next_refresh_time - current_time))
                    next_refresh_text = vsc.Utility.seconds_to_human_time(next_refresh_in)
                    
                    if is_indexing:
                        next_refresh_text = "Checking now..."
                        refresh_status_color = "primary"
            except Exception as e:
                log.warning(f"Error getting refresh timing: {e}")
            
            # CDN URLs - configurable for dev/prod environments
            # Check if running in container or if local CDN files should be used
            use_local_cdn = os.environ.get('USE_LOCAL_CDN', 'false').lower() == 'true'
            cdn_base = os.environ.get('CDN_BASE_URL', '')
            
            if use_local_cdn and cdn_base:
                # Use local/custom CDN
                bootstrap_css_url = f"{cdn_base}/bootstrap/5.3.3/css/bootstrap.min.css"
                bootstrap_icons_url = f"{cdn_base}/bootstrap-icons/1.9.1/font/bootstrap-icons.css"
                bootstrap_js_url = f"{cdn_base}/bootstrap/5.3.3/js/bootstrap.bundle.min.js"
            else:
                # Use public CDN (default)
                bootstrap_css_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
                bootstrap_icons_url = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.9.1/font/bootstrap-icons.css"
                bootstrap_js_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
            
            # Ensure all variables are proper strings
            template_vars = {
                'STATUS': str(status_class),
                'STATUS_ICON': str(status_icon),
                'STATUS_TEXT': str(status_text),
                'STATUS_ANIMATION': str(status_animation),
                'LOADING_PROGRESS': str(loading_progress),
                'UPTIME_HOURS': str(uptime_hours),
                'EXTENSIONS_LOADED': str(extension_count),
                'TOTAL_VERSIONS': str(total_versions), 
                'UNIQUE_PUBLISHERS': str(len(publishers)),
                'CACHE_STATUS_COLOR': str(cache_status_color),
                'CACHE_STATUS_TEXT': str(cache_status_text),
                'CACHE_SIZE_MB': str(cache_size_mb),
                'CACHE_AGE_HOURS': str(cache_age_hours),
                'CATEGORIES_LIST': str(categories_list),
                'LAST_UPDATED': str(last_updated),
                'REFRESH_INTERVAL': str(refresh_interval),
                'LAST_REFRESH': str(last_refresh_text),
                'NEXT_REFRESH': str(next_refresh_text),
                'REFRESH_STATUS_COLOR': str(refresh_status_color),
                'BOOTSTRAP_CSS_URL': str(bootstrap_css_url),
                'BOOTSTRAP_ICONS_URL': str(bootstrap_icons_url),
                'BOOTSTRAP_JS_URL': str(bootstrap_js_url)
            }
            
            # Load and substitute template
            resp.content_type = 'text/html; charset=utf-8'
            with open(os.path.join(self.content_dir, 'status.html'), 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Simple placeholder substitution like index.html
            try:
                html_content = template_content.format(**template_vars)
            except KeyError as e:
                log.error(f"Missing template placeholder: {e}")
                log.error(f"Available placeholders: {list(template_vars.keys())}")
                raise
            except ValueError as e:
                log.error(f"Template formatting error: {e}")
                log.error(f"Problematic values: {template_vars}")
                raise
            
            resp.text = html_content
            resp.status = falcon.HTTP_200
            
        except FileNotFoundError:
            log.warning("Status template not found")
            resp.content_type = 'text/html; charset=utf-8'
            resp.text = "<html><body><h1>VS Code Server Status</h1><p>Status template not found</p><p><a href='/'>Home</a></p></body></html>"
            resp.status = falcon.HTTP_200
            
        except Exception as e:
            log.error(f"Error generating status page: {str(e)}")
            resp.content_type = 'text/html; charset=utf-8'
            resp.text = f"<html><body><h1>VS Code Server Status</h1><p>Error: {str(e)}</p><p><a href='/'>Home</a></p></body></html>"
            resp.status = falcon.HTTP_200
    
    def _get_simple_status(self):
        """Get basic status data without expensive operations"""
        with self.vsc_status.gallery.extensions_lock:
            extension_count = len(self.vsc_status.gallery.extensions)
        
        is_loaded = self.vsc_status.gallery.loaded.is_set()
        current_time = time.time()
        uptime_seconds = int(current_time - getattr(self.vsc_status.gallery, 'start_time', current_time))
        uptime_hours = round(uptime_seconds / 3600, 1)
        
        return {
            'status': 'ready' if is_loaded else 'loading',
            'extensions': {
                'loaded_count': extension_count,
                'loading_progress': f"{extension_count} extensions loaded",
                'total_versions': extension_count,
                'unique_publishers': 'N/A',
                'categories': {},
                'newest_extension': None,
                'oldest_extension': None
            },
            'server_uptime_hours': uptime_hours,
            'cache': {
                'exists': os.path.exists(self.vsc_status.gallery.cache_file),
                'size_mb': 0,
                'age_hours': 0,
                'compression_ratio': None
            },
            'storage': {
                'extensions_directory': {'size_gb': 0, 'file_count': 0, 'path': vsc.ARTIFACTS_EXTENSIONS},
                'installers_directory': {'size_gb': 0, 'file_count': 0, 'path': vsc.ARTIFACTS_INSTALLERS}
            },
            'system': {
                'platform': 'Docker Container',
                'architecture': 'AMD64',
                'python_version': '3.12'
            },
            'configuration': {
                'cache_location': self.vsc_status.gallery.cache_file,
                'update_interval_hours': 1,
                'artifacts_root': vsc.ARTIFACTS,
                'url_root': vsc.URLROOT
            },
            'timestamp': int(current_time)
        }
    
    # Complex template generation method removed - using simple HTML generation now

class VSCStatusSimple(object):
    """Simple status endpoint for debugging"""
    
    def __init__(self, vsc_status):
        self.vsc_status = vsc_status
    
    def on_get(self, req, resp):
        try:
            with self.vsc_status.gallery.extensions_lock:
                extension_count = len(self.vsc_status.gallery.extensions)
            
            is_loaded = self.vsc_status.gallery.loaded.is_set()
            
            simple_status = {
                'status': 'ready' if is_loaded else 'loading',
                'extension_count': extension_count,
                'cache_exists': os.path.exists(self.vsc_status.gallery.cache_file),
                'timestamp': int(time.time())
            }
            
            resp.media = simple_status
            resp.status = falcon.HTTP_200
            
        except Exception as e:
            resp.media = {'error': str(e)}
            resp.status = falcon.HTTP_500

class VSCCDNConfig(object):
    """Endpoint to provide CDN configuration for client-side URL switching"""
    
    def on_get(self, req, resp):
        use_local_cdn = os.environ.get('USE_LOCAL_CDN', 'false').lower() == 'true'
        cdn_base = os.environ.get('CDN_BASE_URL', '')
        
        if use_local_cdn and cdn_base:
            # Use local/custom CDN
            cdn_config = {
                'bootstrap_css': f"{cdn_base}/bootstrap@5.3.3/dist/css/bootstrap.min.css",
                'bootstrap_icons': f"{cdn_base}/bootstrap-icons@1.9.1/font/bootstrap-icons.css", 
                'bootstrap_js': f"{cdn_base}/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
            }
        else:
            # Use public CDN (default)
            cdn_config = {
                'bootstrap_css': "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
                'bootstrap_icons': "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.9.1/font/bootstrap-icons.css",
                'bootstrap_js': "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
            }
        
        resp.content_type = 'application/json'
        resp.text = json.dumps(cdn_config)
        resp.status = falcon.HTTP_200

class VSCChat(object):
    """VS Code AI/Chat configuration endpoint"""

    def on_get(self, req, resp):
        chat_config = {
            "enabled": False,
            "models": [],
            "providers": [],
            "notice": "AI/Chat features are not available in offline mode"
        }
        resp.media = chat_config
        resp.status = falcon.HTTP_200

class VSCUnpkg(object):
    """Handle unpkg CDN requests for VS Code web components"""

    def on_get(self, req, resp, path):
        # In offline mode, we don't serve unpkg content but provide a meaningful response
        resp.media = {
            "error": "CDN content not available in offline mode",
            "path": path,
            "suggestion": "Use locally installed VS Code extensions instead"
        }
        resp.status = falcon.HTTP_404

class VSCIndex(object):

    def __init__(self):
        pass

    def on_get(self, req, resp):
        # CDN URLs - configurable for dev/prod environments (same as status and browse pages)
        # Check if running in container or if local CDN files should be used
        use_local_cdn = os.environ.get('USE_LOCAL_CDN', 'false').lower() == 'true'
        cdn_base = os.environ.get('CDN_BASE_URL', '')
        
        if use_local_cdn and cdn_base:
            # Use local/custom CDN
            bootstrap_css_url = f"{cdn_base}/bootstrap/5.3.3/css/bootstrap.min.css"
            bootstrap_icons_url = f"{cdn_base}/bootstrap-icons/1.9.1/font/bootstrap-icons.css"
            bootstrap_js_url = f"{cdn_base}/bootstrap/5.3.3/js/bootstrap.bundle.min.js"
        else:
            # Use public CDN (default)
            bootstrap_css_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
            bootstrap_icons_url = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.9.1/font/bootstrap-icons.css"
            bootstrap_js_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        
        # Template variables for placeholder substitution
        template_vars = {
            'BOOTSTRAP_CSS_URL': str(bootstrap_css_url),
            'BOOTSTRAP_ICONS_URL': str(bootstrap_icons_url),
            'BOOTSTRAP_JS_URL': str(bootstrap_js_url)
        }
        
        resp.content_type = 'text/html; charset=utf-8'
        with open(os.path.join(vsc.CONTENT, 'index.html'), 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Template substitution using .format() method (same as status and browse pages)
        try:
            html_content = template_content.format(**template_vars)
        except KeyError as e:
            log.error(f"Missing template placeholder in index.html: {e}")
            log.error(f"Available placeholders: {list(template_vars.keys())}")
            raise
        except ValueError as e:
            log.error(f"Template formatting error in index.html: {e}")
            log.error(f"Problematic values: {template_vars}")
            raise
            
        resp.text = html_content
        resp.status = falcon.HTTP_200

class VSCDirectoryBrowse(object):

    def __init__(self, root):
        self.root = root

    def on_get(self, req, resp):
        requested_path = os.path.join(self.root, req.get_param('path', required=True))
        # Check the path requested
        log.debug(f"Browse Debug - Root: '{self.root}'")
        log.debug(f"Browse Debug - Requested path: '{requested_path}'")
        log.debug(f"Browse Debug - Realpath of requested: '{os.path.realpath(requested_path)}'")
        log.debug(f"Browse Debug - Realpath of root: '{os.path.realpath(self.root)}'")
        log.debug(f"Browse Debug - Commonprefix result: '{os.path.commonprefix((os.path.realpath(requested_path), self.root))}'")
        log.debug(f"Browse Debug - Path exists: {os.path.exists(requested_path)}")
        

        
        # Check if requested path exists
        if not os.path.exists(requested_path):
            log.warning(f"Browse 404 - Path does not exist: {requested_path}")
            resp.status = falcon.HTTP_404
            return
        
        search_query = req.get_param('search', default='').strip()
        page = int(req.get_param('page', default=1))
        
        try:
            item_count = len(os.listdir(requested_path))
            if item_count > 50000:
                default_per_page = 25
            elif item_count > 10000:
                default_per_page = 50
            elif item_count > 1000:
                default_per_page = 100
            else:
                default_per_page = 500
                
        except OSError:
            log.warning(f"Directory listing error for {requested_path}")
            default_per_page = 25
            
        per_page = int(req.get_param('per_page', default=default_per_page))
        
        # CDN URLs - configurable for dev/prod environments (same as status page)
        # Check if running in container or if local CDN files should be used
        use_local_cdn = os.environ.get('USE_LOCAL_CDN', 'false').lower() == 'true'
        cdn_base = os.environ.get('CDN_BASE_URL', '')
        
        if use_local_cdn and cdn_base:
            # Use local/custom CDN
            bootstrap_css_url = f"{cdn_base}/bootstrap/5.3.3/css/bootstrap.min.css"
            bootstrap_icons_url = f"{cdn_base}/bootstrap-icons/1.9.1/font/bootstrap-icons.css"
            bootstrap_js_url = f"{cdn_base}/bootstrap/5.3.3/js/bootstrap.bundle.min.js"
        else:
            # Use public CDN (default)
            bootstrap_css_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
            bootstrap_icons_url = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.9.1/font/bootstrap-icons.css"
            bootstrap_js_url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        
        # Template variables for placeholder substitution
        template_vars = {
            'PATH': str(requested_path),
            'CONTENT': str(self.paginated_dir_browse_response(requested_path, page, per_page, search_query)),
            'BOOTSTRAP_CSS_URL': str(bootstrap_css_url),
            'BOOTSTRAP_ICONS_URL': str(bootstrap_icons_url),
            'BOOTSTRAP_JS_URL': str(bootstrap_js_url)
        }
        
        resp.content_type = 'text/html; charset=utf-8'
        with open(os.path.join(vsc.CONTENT, 'browse.html'), 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Template substitution using .format() method (same as status page)
        try:
            html_content = template_content.format(**template_vars)
        except KeyError as e:
            log.error(f"Missing template placeholder in browse.html: {e}")
            log.error(f"Available placeholders: {list(template_vars.keys())}")
            raise
        except ValueError as e:
            log.error(f"Template formatting error in browse.html: {e}")
            log.error(f"Problematic values: {template_vars}")
            raise
            
        resp.text = html_content
        resp.status = falcon.HTTP_200

    def simple_dir_browse_response(self, path):
        """Legacy method - kept for compatibility"""
        return self.paginated_dir_browse_response(path, 1, 10000)

    def paginated_dir_browse_response(self, path, page=1, per_page=100, search_query=''):
        response = ''
        
        try:
            max_scan = 100000 if not search_query else None
            
            folders = vsc.Utility.folders_in_folder(path, max_scan)
            files = vsc.Utility.files_in_folder(path, max_scan) 
            all_items = [(item, 'folder') for item in folders] + [(item, 'file') for item in files if item != path]
            
            if max_scan and (len(folders) + len(files)) >= max_scan:
                log.warning(f"Directory scan limited to {max_scan} items for performance")
                
        except Exception as e:
            log.error(f"Error scanning directory {path}: {e}")
            all_items = []
        
        if search_query:
            search_lower = search_query.lower()
            filtered_items = []
            for item, item_type in all_items:
                if search_lower in item.lower():
                    filtered_items.append((item, item_type))
            all_items = filtered_items
        
        total_items = len(all_items)
        total_pages = (total_items + per_page - 1) // per_page
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_items = all_items[start_idx:end_idx]
        
        current_path = os.path.relpath(path, self.root)
        response += f'''
        <section class="card mb-4" aria-labelledby="search-heading">
            <header class="card-header bg-light">
                <h2 id="search-heading" class="card-title mb-0 h6">
                    <i class="bi bi-search me-2" aria-hidden="true"></i>Search & Filter
                </h2>
            </header>
            <div class="card-body">
                <form method="GET" action="/browse" class="mb-3" role="search" aria-label="Filter directory contents">
                    <input type="hidden" name="path" value="{current_path}">
                    <input type="hidden" name="per_page" value="{per_page}">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-8">
                            <label for="search" class="form-label fw-bold">Search:</label>
                            <input type="text" 
                                   name="search" 
                                   id="search" 
                                   value="{search_query}" 
                                   placeholder="Filter by name..." 
                                   class="form-control"
                                   aria-describedby="search-help"
                                   autocomplete="off">
                            <div id="search-help" class="form-text visually-hidden">
                                Enter text to filter directory contents by name
                            </div>
                        </div>
                        <div class="col-md-4">
                            <button type="submit" class="btn btn-primary me-2" aria-describedby="filter-desc">
                                <i class="bi bi-funnel me-1" aria-hidden="true"></i>Filter
                            </button>
                            <span id="filter-desc" class="visually-hidden">Apply search filter to directory listing</span>
                            {f'<a href="/browse?path={current_path}&per_page={per_page}" class="btn btn-secondary" aria-label="Clear search filter"><i class="bi bi-x-circle me-1" aria-hidden="true"></i>Clear</a>' if search_query else ''}
                        </div>
                    </div>
                </form>
                <div class="row">
                    <div class="col-12">
                        <div class="text-muted small" role="status" aria-live="polite">
                            <i class="bi bi-info-circle me-1" aria-hidden="true"></i>
                            {'<strong>Filtered results:</strong> ' if search_query else '<strong>Total items:</strong> '}{total_items} | 
                            Page {page} of {total_pages} | 
                            Showing {len(page_items)} items
                            {f' | <strong>Active Filter:</strong> <span class="badge bg-warning text-dark">"{search_query}"</span>' if search_query else ''}
                        </div>
                    </div>
                </div>
            </div>
        </section>
        '''
        
        def build_url_params(page_num=None, new_per_page=None):
            params = []
            params.append(f'path={current_path}')
            if page_num:
                params.append(f'page={page_num}')
            if new_per_page:
                params.append(f'per_page={new_per_page}')
            elif per_page != 100:
                params.append(f'per_page={per_page}')
            if search_query:
                params.append(f'search={search_query}')
            return '&'.join(params)
        if total_pages > 1:
            nav = f'<nav aria-label="Directory pagination - Page {page} of {total_pages}" class="mb-4"><ul class="pagination justify-content-center">'
            
            if page > 1:
                nav += f'<li class="page-item"><a class="page-link" href="/browse?{build_url_params(page-1)}" aria-label="Go to previous page"><i class="bi bi-chevron-left" aria-hidden="true"></i> Previous</a></li>'
            else:
                nav += '<li class="page-item disabled"><span class="page-link" aria-label="Previous page unavailable"><i class="bi bi-chevron-left" aria-hidden="true"></i> Previous</span></li>'
            
            start_page = max(1, page - 2)
            end_page = min(total_pages, page + 2)
            
            if start_page > 1:
                nav += f'<li class="page-item"><a class="page-link" href="/browse?{build_url_params(1)}" aria-label="Go to page 1">1</a></li>'
                if start_page > 2:
                    nav += '<li class="page-item disabled"><span class="page-link" aria-label="More pages">...</span></li>'
            
            for p in range(start_page, end_page + 1):
                if p == page:
                    nav += f'<li class="page-item active"><span class="page-link" aria-current="page" aria-label="Current page {p}">{p}</span></li>'
                else:
                    nav += f'<li class="page-item"><a class="page-link" href="/browse?{build_url_params(p)}" aria-label="Go to page {p}">{p}</a></li>'
            
            if end_page < total_pages:
                if end_page < total_pages - 1:
                    nav += '<li class="page-item disabled"><span class="page-link" aria-label="More pages">...</span></li>'
                nav += f'<li class="page-item"><a class="page-link" href="/browse?{build_url_params(total_pages)}" aria-label="Go to page {total_pages}">{total_pages}</a></li>'
            
            if page < total_pages:
                nav += f'<li class="page-item"><a class="page-link" href="/browse?{build_url_params(page+1)}" aria-label="Go to next page">Next <i class="bi bi-chevron-right" aria-hidden="true"></i></a></li>'
            else:
                nav += '<li class="page-item disabled"><span class="page-link" aria-label="Next page unavailable">Next <i class="bi bi-chevron-right" aria-hidden="true"></i></span></li>'
                
            nav += '</ul></nav>'
            response += nav
        response += f'''
        <div class="d-flex justify-content-between align-items-center mb-3" role="region" aria-labelledby="per-page-label">
            <span id="per-page-label" class="text-muted">
                <i class="bi bi-grid-3x3-gap me-1" aria-hidden="true"></i>Items per page:
            </span>
            <div class="btn-group" role="group" aria-labelledby="per-page-label">
                <a href="/browse?{build_url_params(1, 50)}" 
                   class="btn {'btn-primary' if per_page == 50 else 'btn-outline-primary'} btn-sm"
                   {'aria-current="page"' if per_page == 50 else ''}
                   aria-label="Show 50 items per page">50</a>
                <a href="/browse?{build_url_params(1, 100)}" 
                   class="btn {'btn-primary' if per_page == 100 else 'btn-outline-primary'} btn-sm"
                   {'aria-current="page"' if per_page == 100 else ''}
                   aria-label="Show 100 items per page">100</a>
                <a href="/browse?{build_url_params(1, 250)}" 
                   class="btn {'btn-primary' if per_page == 250 else 'btn-outline-primary'} btn-sm"
                   {'aria-current="page"' if per_page == 250 else ''}
                   aria-label="Show 250 items per page">250</a>
                <a href="/browse?{build_url_params(1, 500)}" 
                   class="btn {'btn-primary' if per_page == 500 else 'btn-outline-primary'} btn-sm"
                   {'aria-current="page"' if per_page == 500 else ''}
                   aria-label="Show 500 items per page">500</a>
            </div>
        </div>
        '''
        response += f'<div class="list-group" role="list" aria-label="Directory contents - {len(page_items)} items">'
        for item, item_type in page_items:
            if item_type == 'folder':
                folder_path = os.path.relpath(os.path.join(path, item), self.root)
                response += f'''
                <a href="/browse?path={folder_path}" 
                   class="list-group-item list-group-item-action directory-item"
                   role="listitem"
                   aria-label="Open folder {item}">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-folder-fill folder-icon me-3 fs-5" aria-hidden="true"></i>
                        <div class="flex-grow-1">
                            <span class="fw-bold">{item}/</span>
                            <span class="visually-hidden">folder</span>
                        </div>
                        <i class="bi bi-chevron-right text-muted" aria-hidden="true"></i>
                    </div>
                </a>
                '''
            else:
                response += f'''
                <a href="{os.path.join(self.root, path, item)}" 
                   class="list-group-item list-group-item-action directory-item" 
                   target="_blank"
                   role="listitem"
                   aria-label="Download file {item}"
                   rel="noopener">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-file-earmark file-icon me-3 fs-5" aria-hidden="true"></i>
                        <div class="flex-grow-1">
                            <span>{item}</span>
                            <span class="visually-hidden">file - opens in new window</span>
                        </div>
                        <i class="bi bi-download text-muted" aria-hidden="true"></i>
                    </div>
                </a>
                '''
        
        if not page_items:
            response += '''
            <div class="list-group-item text-center py-5" role="listitem">
                <i class="bi bi-inbox display-1 text-muted mb-3" aria-hidden="true"></i>
                <h3 class="text-muted h5">No items found</h3>
                <p class="text-muted mb-0">This directory appears to be empty or no items match your search.</p>
            </div>
            '''
        
        response += '</div>'
        
        if total_pages > 1:
            response += '<div class="mt-4">' + nav.replace('mb-4', 'mb-0') + '</div>'
        
        return response

class ArtifactChangedHandler(FileSystemEventHandler):

    def __init__(self, gallery):
        self.gallery = gallery

    def on_modified(self, event):
        if 'updated.json' in event.src_path:
            log.info('Detected updated.json change, updating extension gallery')
            self.gallery.update_state()


if not os.path.exists(vsc.ARTIFACTS):
    log.warning(f'Artifact directory missing {vsc.ARTIFACTS}. Cannot proceed.')
    sys.exit(-1)

if not os.path.exists(vsc.ARTIFACTS_INSTALLERS):
    log.warning(f'Installer artifact directory missing {vsc.ARTIFACTS_INSTALLERS}. Cannot proceed.')
    sys.exit(-1)

if not os.path.exists(vsc.ARTIFACTS_EXTENSIONS):
    log.warning(f'Extensions artifact directory missing {vsc.ARTIFACTS_EXTENSIONS}. Cannot proceed.')
    sys.exit(-1)

# Get refresh interval from environment variable (default 3600 seconds = 1 hour)
refresh_interval = int(os.environ.get('REFRESH_INTERVAL', '3600'))
log.info(f'Extension refresh interval: {vsc.Utility.seconds_to_human_time(refresh_interval)}')

vscgallery = VSCGallery(interval=refresh_interval)

log.info('Extension gallery is loading in the background - server starting immediately...')
log.info('Check /status endpoint for loading progress')
log.info(f'Cache location: {vscgallery.cache_file}')

observer = PollingObserver()
observer.schedule(ArtifactChangedHandler(vscgallery), vsc.ARTIFACTS, recursive=False)
observer.start()

application = falcon.App(cors_enable=True)
application.add_route('/api/update/{platform}/{buildquality}/{commitid}', VSCUpdater())
application.add_route('/commit:{commitid}/{platform}/{buildquality}', VSCBinaryFromCommitId())
application.add_route('/extensions/workspaceRecommendations.json.gz', VSCRecommendations())
application.add_route('/extensions/marketplace.json', VSCMalicious())
application.add_route('/_apis/public/gallery/extensionquery', vscgallery)
vsc_status = VSCStatus(vscgallery)
application.add_route('/status', VSCStatusPage(vsc.CONTENT, vsc_status))  # Main HTML status page
application.add_route('/status.json', vsc_status)  # JSON API endpoint
application.add_route('/status-simple', VSCStatusSimple(vsc_status))  # Simple debug endpoint
application.add_route('/cdn-config.json', VSCCDNConfig())  # CDN configuration endpoint

# Modern VS Code endpoints for AI/Chat features and CDN compatibility
application.add_route('/chat.json', VSCChat())
application.add_route('/vscode-unpkg/{path}', VSCUnpkg())

application.add_route('/browse', VSCDirectoryBrowse(vsc.ARTIFACTS))
application.add_route('/', VSCIndex())
application.add_static_route('/artifacts/', vsc.ARTIFACTS)

if __name__ == '__main__':
    log.basicConfig(
        format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s',
        datefmt='%y%m%d %H:%M:%S',
        level=log.DEBUG
    )
    httpd = simple_server.make_server('0.0.0.0', 5000, application)
    httpd.serve_forever()
