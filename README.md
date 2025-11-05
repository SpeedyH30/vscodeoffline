# Visual Studio Code - Offline Gallery and Updater

This enables Visual Studio Code's web presence to be mirrored for seamless use in an offline environment (e.g. air-gapped), or to run a private gallery.

In effect, content is served through expected interfaces, without changing any of the publicly available binaries. Typically, you would sync the content needing to be availabe on the non-Internet connected system and point the DNS to the mirror service. **No binaries nor extensions are modified.**

## Features

On the Internet connected system , **vscsync** will:

- Mirror the VS Code installer/update binaries across platforms (Windows|Linux|Darwin) and builds (stable|insider);
- Mirror recommended/typical extensions from the marketplace;
- Mirror the malicious extension list;
- Mirror a list of manually specified extensions (artifacts/specified.json); and
- Optionally, mirror all extensions (--syncall, rather than the default of --sync).

On the non-Internet connected system, **vscgallery**:

- Implements the updater interface to enable offline updating;
- Implements the extension API to enable offline extension use;
- Implements the malicious extension list;
- Implements initial support for multiple versions;
- Supports extension search (name, author and short description) and sorting;
- Supports custom/private extensions (follow the structure of a mirrored extension);
- Supports Remote Development;
- **NEW**: Real-time status dashboard with system metrics and extension statistics;
- **NEW**: Enhanced web interface with responsive design and accessibility features;
- **NEW**: Environment-configurable CDN URLs for Bootstrap assets (dev/prod flexibility);
- **NEW**: Optimized Docker images with reduced dependencies and Python 3.12 support;
- **NEW**: Intelligent caching system for improved performance and reduced filesystem access;
- **NEW**: Comprehensive error handling and logging throughout the application.

## Recent Improvements (v2.0.0)

### Status Dashboard
- **Real-time monitoring**: Live status page at `/status` showing system health, extension counts, and cache information
- **System metrics**: Displays uptime, loaded extensions, total versions, unique publishers, and cache status
- **Cache monitoring**: Real-time cache statistics including size, age, hit rates, and automatic refresh status
- **Auto-refresh**: Updates every 30 seconds to provide current information
- **Responsive design**: Mobile-friendly interface with Bootstrap 5.3.3

### Enhanced Web Interface  
- **Modern UI**: Updated all HTML templates with improved accessibility and responsive design
- **Directory browser**: Enhanced file browsing interface with search, pagination, and keyboard navigation
- **Status indicators**: Visual feedback for system health and operational status

### Technical Improvements
- **Python 3.12 compatibility**: Removed deprecated `distutils` dependencies, replaced with modern alternatives
- **Optimized Docker images**: Reduced container size by removing unused dependencies (psutil, setuptools, pytimeparse)
- **Environment-aware CDN**: Configurable Bootstrap CDN URLs via `USE_LOCAL_CDN` and `CDN_BASE_URL` environment variables
- **Template system**: Unified template processing across all HTML pages with proper error handling
- **Intelligent caching**: Multi-layered caching system for extension metadata and filesystem operations
  - Compressed JSON caching with gzip for reduced storage and faster I/O
  - File system monitoring with automatic cache invalidation
  - Configurable cache storage location and refresh intervals
  - Persistent cache across container restarts and deployments

### ⚡ Performance & Caching
- **Extension cache**: Compressed JSON cache for faster extension listing and search operations
- **Configurable storage**: Set custom cache location via `CACHE_STORE` environment variable
- **File monitoring**: Automatic cache invalidation when extension files change
- **Reduced I/O**: Significant reduction in filesystem operations through intelligent caching
- **Cache statistics**: Monitor cache performance through the `/status` dashboard
- **Background refresh**: Automatic cache updates without blocking user requests
- **Persistent storage**: Cache survives container restarts when using external storage volumes

### 🔧 Configuration Options
```bash
# Use local CDN instead of public CDN
USE_LOCAL_CDN=true
CDN_BASE_URL=http://your-local-cdn.com

# Content and artifacts paths (for development)
CONTENT=/path/to/content
ARTIFACTS=/path/to/artifacts

# Cache configuration (optional)
CACHE_STORE=/path/to/cache    # Cache storage location (default: artifacts directory)
CACHE_REFRESH_INTERVAL=3600  # Cache refresh interval in seconds
CACHE_MAX_SIZE=100MB         # Maximum cache size
```

Possible TODO List:

- vscgallery - Support paging, if it's really needed (who searches 1000s of extensions anyway).
- Investigate some form of dependency handling (if possible).
- Add test cases.

## Requirements

- Docker (ideally with docker-compose for simplicity)

## Getting Started - Full Offline Use - Using Docker Containers

There are two components, **vscsync** which mirrors the content on an Internet connected system, and **vscgallery** which provides the necessary APIs and endpoints necessary to support VS Code's use. While it is designed for offline environments, it is possible, with some DNS trickery, that this could be operated as a "corporate" VS Code gallery.

On the Internet connected system:

1. Acquire/mirror the Docker containers (vscsync/vscgallery).

   `docker-compose pull`

2. Setup and run the vscsync service on the Internet connected system.

   - Ensuring the artifact directory is accessible to whatever transfer mechanism you will use and vscsync.
   - Run vscsync service and ensure the artifacts are generated.
   - Wait for the sync to complete. You should see 'Complete' and that it is sleeping when the artifacts have finished downloading.

   `docker-compose up vscsync`

3. Copy the artifacts to the non-Internet connected system.

On the non-Internet connected system:

1. On the non-Internet connected system, ensure the following DNS addresses are pointed toward the vscgallery service.

   - update.code.visualstudio.com
   - az764295.vo.msecnd.net
   - marketplace.visualstudio.com

   This may be achieved using a corporate DNS server, or by modifying a client's host file.

2. Sort out SSL/TLS within your environment to support offline use.

   - Either create a certificate which is signed for the above domains, and is trusted by the clients; or
   - Deploy the bundled root and intermediate certificate authority (vscoffline/vscgallery/ssl/ca.crt and ia.crt), with the obvious security tradeoff.

   **Windows 10**: Import the certificates into the machine's trusted root certificate authority (Start > "Manage Computer Certificates").

   **Darwin**: Import the certificates into the machine's trusted root certificate authority.

   **Ubuntu**: Easiest method seems to be Open Chrome, navigate to
   chrome://settings/certificates, select authorities and add the certificates. Firefox on Ubuntu maintains its own certificate store. Either add the root CA, or switch Firefox to use OS provided certificates (see: <https://github.com/LOLINTERNETZ/vscodeoffline/issues/43#issuecomment-1545801875>).

3. Run the vscgallery service, ensuring the artifacts are accessible to the service. It needs to listen on port 443.

   `docker-compose up vscgallery`

5. Using Chrome/Firefox navigate to <https://update.code.visualstudio.com>. You should not see any certificate warnings, if you do it's unlikely to work in VS Code.

6. **NEW**: Access the status dashboard at `https://update.code.visualstudio.com/status` to monitor system health and view extension statistics.

7. Open VS Code, hopefully you can magically install extensions and update the install. The Help > Developer Tools > Network should tell you what is going on.

Note: Chrome, rather than other browsers, will likely give you a better indication as to what is going on as VS Code and Chrome share the same certificate trust.

## Getting Started - Standalone Install (Testing or Private Gallery) - Using Docker Containers

This guide will setup the vscsync and vscgallery service on the same Docker host.

1. Grab the docker-compose.yml file.

   - Ensure the docker-compose DNS configuration will override what is configured in step 2 (e.g. vscsync can access the Internet, whereas local hosts are directed toward the vscgallery service).
   - Ensure both containers will mount the same artifact folder.

2. Point the DNS addresses to the vscgallery service.

   - update.code.visualstudio.com
   - ~~az764295.vo.msecnd.net~~ (Removed 2025/08/22)
   - marketplace.visualstudio.com
   - main.vscode-cdn.net (Added 2025/08/22)

   This may be achieved using a corporate DNS server, or by modifying a client's host file.

3. Deploy SSL/TLS certificates as necessary, as described above.

4. Run the services

   `docker-compose up`

5. Using Chrome navigate to https://update.code.visualstudio.com. You should not see any certificate warnings, if you do it's unlikely to work in VS Code.

6. **NEW**: Monitor your installation at `https://update.code.visualstudio.com/status` for real-time system metrics and extension statistics.

7. Open VS Code, hopefully you can magically install extensions and update the install. The Help > Developer Tools > Network should tell you what is going on.

## Sync Arguments (vscsync)

These arguments can be passed as command line arguments to sync.py (e.g. --varA or --varB), or passed via the Docker environment variable `SYNCARGS`.

### Typical Sync Args

- `--sync` To fetch stable binaries and popular extensions.
- `--syncall` To fetch everything (stable binaries, insider binaries and all extensions).
- `--sync --check-insider` To fetch stable binaries, insider binaries and popular extensions.

### Possible Args

```text
usage: sync.py [-h] [--sync] [--syncall] [--artifacts ARTIFACTDIR]
               [--frequency FREQUENCY] [--check-binaries] [--check-insider]
               [--check-recommended-extensions] [--check-specified-extensions]
               [--extension-name EXTENSIONNAME]
               [--extension-search EXTENSIONSEARCH] [--update-binaries]
               [--update-extensions] [--update-malicious-extensions]
               [--prerelease-extensions] [--vscode-version VSCODEVERSION]
               [--skip-binaries] [--debug] [--logfile LOGFILE]

Synchronises VSCode in an Offline Environment

optional arguments:
  -h, --help            show this help message and exit
  --sync                The basic-user sync. It includes stable binaries and
                        typical extensions
  --syncall             The power-user sync. It includes all binaries and
                        extensions
  --artifacts ARTIFACTDIR
                        Path to downloaded artifacts
  --frequency FREQUENCY
                        The frequency to try and update (e.g. sleep for '12h'
                        and try again
  --total-recommended N
                        The number of recommended extensions to fetch
                        (default: 200)
  --check-binaries      Check for updated binaries
  --check-insider       Check for updated insider binaries
  --check-recommended-extensions
                        Check for recommended extensions
  --check-specified-extensions
                        Check for extensions in <artifacts>/specified.json
  --extension-name EXTENSIONNAME
                        Find a specific extension by name
  --extension-search EXTENSIONSEARCH
                        Search for a set of extensions
  --update-binaries     Download binaries
  --update-extensions   Download extensions
  --update-malicious-extensions
                        Update the malicious extension list
  --prerelease-extensions
                        Download prerelease extensions. Defaults to false.
  --vscode-version
                        VSCode version to search extensions as.
  --skip-binaries       Skip downloading binaries
  --debug               Show debug output
  --logfile LOGFILE     Sets a logfile to store loggging output
```

