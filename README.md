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

## Version 2.0.0 Major Release

### Microsoft API Modernization
- Complete session management overhaul with enhanced retry logic and error handling
- Exponential backoff with jitter for Microsoft API rate limiting (429 errors)
- Modern request headers and authentication for improved API compatibility
- Resilient connection pooling and timeout management

### Expanded Platform Support
- Increased from 11 to 29 comprehensive VS Code platforms
- Full Windows ARM64, Linux variants, and macOS Intel/Apple Silicon support
- Added VS Code Server platforms for Remote Development scenarios
- Included VS Code CLI platforms for command-line usage
- Advanced platform filtering with include/exclude options

### Container Optimization
- Multi-stage Docker builds reducing image sizes by approximately 50% to 95-113MB
- Alpine Linux base images with optimized dependency management
- Enhanced DNS resolution and networking configuration for containerized environments
- Proper artifacts directory path handling for container compatibility

### Modern VS Code Feature Support
- AI/Chat endpoint compatibility for modern VS Code features
- CDN endpoint support for web-based VS Code components
- Enhanced marketplace API compatibility with current Microsoft infrastructure
- Updated extension handling for platform-specific variants

### Configuration Options
```bash
# Container networking (recommended for DNS resolution)
network_mode: host

# Platform filtering examples
SYNCARGS=--sync --platforms darwin,win32 --include-server
SYNCARGS=--syncall --exclude-platforms arm64,armhf
SYNCARGS=--sync --include-cli --total-recommended 100

# Content and artifacts paths
CONTENT=/path/to/content
ARTIFACTS=/path/to/artifacts
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
               [--extension-name EXTENSIONNAME] [--extension-search EXTENSIONSEARCH]
               [--prerelease-extensions] [--update-binaries] [--update-extensions]
               [--update-malicious-extensions] [--skip-binaries]
               [--vscode-version VERSION] [--total-recommended TOTALRECOMMENDED]
               [--debug] [--logfile LOGFILE] [--platforms PLATFORMS] [--include-server]
               [--include-cli] [--include-arm] [--exclude-platforms EXCLUDEPLATFORMS]
               [--list-platforms]

Synchronizes VSCode in an Offline Environment

Main Operations:
  --sync                The basic-user sync. Includes stable binaries and typical extensions
  --syncall             The power-user sync. Includes all binaries and extensions

Configuration:
  --artifacts ARTIFACTDIR
                        Path to downloaded artifacts (default: /artifacts/)
  --frequency FREQUENCY
                        The frequency to try and update (e.g. sleep for '12h' and try again)
  --total-recommended TOTALRECOMMENDED
                        Total number of recommended extensions to sync from Search API (default: 500)

Content Selection:
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
  --prerelease-extensions
                        Download prerelease extensions. Defaults to false
  --vscode-version VERSION
                        VSCode version to search extensions as

Actions:
  --update-binaries     Download binaries
  --update-extensions   Download extensions
  --update-malicious-extensions
                        Update the malicious extension list
  --skip-binaries       Skip downloading binaries

Platform Filtering (New in v2.0.0):
  --platforms PLATFORMS
                        Comma-separated list of platforms to sync (e.g., "win32,linux,darwin")
  --include-server      Include VS Code Server platforms for Remote Development
  --include-cli         Include VS Code CLI platforms
  --include-arm         Include ARM-based platforms (ARM64, ARMHF)
  --exclude-platforms EXCLUDEPLATFORMS
                        Comma-separated list of platforms to exclude
  --list-platforms      List all available platforms and exit

Debugging:
  --debug               Show debug output
  --logfile LOGFILE     Sets a logfile to store logging output
```

## Supported Platforms (v2.0.0)

VSCodeOffline now supports 29 comprehensive VS Code platforms:

### Desktop Platforms
- **Windows**: win32, win32-x64, win32-arm64
- **Linux**: linux, linux-x64, linux-arm64, linux-armhf, linux-deb, linux-rpm, linux-snap  
- **macOS**: darwin, darwin-x64, darwin-arm64, darwin-universal

### Server Platforms (Remote Development)
- **Linux Server**: server-linux, server-linux-x64, server-linux-arm64, server-linux-armhf
- **macOS Server**: server-darwin, server-darwin-x64, server-darwin-arm64
- **Windows Server**: server-win32, server-win32-x64, server-win32-arm64

### CLI Platforms
- **Linux CLI**: cli-linux, cli-linux-x64, cli-linux-arm64, cli-alpine
- **macOS CLI**: cli-darwin, cli-darwin-x64, cli-darwin-arm64
- **Windows CLI**: cli-win32, cli-win32-x64, cli-win32-arm64

### Platform Filtering Examples

```bash
# Sync only macOS platforms
--platforms darwin,darwin-x64,darwin-arm64

# Sync Windows and Linux, exclude ARM variants
--platforms win32,linux --exclude-platforms arm64,armhf

# Include server and CLI platforms for comprehensive coverage
--include-server --include-cli

# Sync everything except ARM platforms
--include-server --include-cli --exclude-platforms arm64,armhf

# List all available platforms
--list-platforms
```

## Container Images

Pre-built container images are automatically published to GitHub Container Registry (GHCR) with multiple tagging strategies:

### Available Tags

| Tag Format | Example | Use Case |
|------------|---------|----------|
| `:latest` | `ghcr.io/speedyh30/vscodeoffline/vscsync:latest` | Development/testing (always latest main branch) |
| `:v{version}` | `ghcr.io/speedyh30/vscodeoffline/vscsync:2.0.0` | Production (pinned release versions) |
| `:v{major}.{minor}` | `ghcr.io/speedyh30/vscodeoffline/vscsync:2.0` | Auto-update patch versions |
| `:v{major}` | `ghcr.io/speedyh30/vscodeoffline/vscsync:2` | Auto-update minor/patch versions |
| `:{branch}-{sha}` | `ghcr.io/speedyh30/vscodeoffline/vscsync:main-abc123` | Development builds from specific commits |

### Recommended Usage

**Production**: Use specific version tags for stability
```yaml
services:
  vscsync:
    image: ghcr.io/speedyh30/vscodeoffline/vscsync:2.0.0
  vscgallery:
    image: ghcr.io/speedyh30/vscodeoffline/vscgallery:2.0.0
```

**Development**: Use `:latest` for the newest features
```yaml
services:
  vscsync:
    image: ghcr.io/speedyh30/vscodeoffline/vscsync:latest
  vscgallery:
    image: ghcr.io/speedyh30/vscodeoffline/vscgallery:latest
```

### Using Pre-built Images

Choose the appropriate docker-compose file for your use case:

**Development** (uses `:latest` tags):
```bash
# Pull and run the latest development images
docker-compose pull
docker-compose up -d
```

**Production** (uses pinned version tags):
```bash
# Use the production compose file with pinned versions
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

**Custom Version**:
```bash
# Override image tags for specific versions
export VSCODE_VERSION=2.0.0-beta
docker-compose up -d
# Or manually edit docker-compose.yml image tags
```

### Building Locally

To build the images locally instead:

```bash
# Build both images
docker-compose build

# Or build individually
docker build -f ./vscoffline/vscsync/Dockerfile -t vscsync .
docker build -f ./vscoffline/vscgallery/Dockerfile -t vscgallery .
```

## Fork and Contribution Guide

### For Fork Maintainers

If you fork this repository, the GitHub Actions workflow will automatically adapt to your fork:

1. **Container Images**: Images will be published to `ghcr.io/YOUR_USERNAME/vscodeoffline/vscsync` and `ghcr.io/YOUR_USERNAME/vscodeoffline/vscgallery`

2. **No Additional Setup Required**: The workflow uses `${{ github.repository }}` which automatically uses your fork's namespace

3. **Docker Compose**: Update the image names in `docker-compose.yml` to point to your fork:
   ```yaml
   services:
     vscsync:
       image: ghcr.io/YOUR_USERNAME/vscodeoffline/vscsync:${VSCODE_VERSION:-latest}
     vscgallery:  
       image: ghcr.io/YOUR_USERNAME/vscodeoffline/vscgallery:${VSCODE_VERSION:-latest}
   ```

4. **Version Management**: 
   - Use `.env` file: `echo "VSCODE_VERSION=2.0.0" > .env`
   - Or export environment variable: `export VSCODE_VERSION=2.0.0`
   - Production deployments should use `docker-compose.prod.yml` with pinned versions

4. **Permissions**: Ensure your repository has Actions enabled and the workflow has permission to write to GitHub Container Registry (enabled by default in public repos)

### Making Container Images Public

By default, GHCR images from public repositories are public. If you need to make them public manually:

1. Go to your GitHub profile → Packages
2. Find your vscodeoffline packages
3. Go to Package settings → Change visibility → Public

### Local Development

For development and testing:

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/vscodeoffline.git
cd vscodeoffline

# Build and test locally
docker-compose build
docker-compose up -d

# Run sync to populate artifacts
docker-compose exec vscsync python /app/sync.py --sync

# Check the gallery
open http://localhost:8080
```

### Contributing Back

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper commit messages
4. Ensure GPG signing is set up for verified commits
5. Push to your fork (`git push origin feature/amazing-feature`)  
6. Open a Pull Request with a clear description

All commits should be GPG signed. See the [GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification) for setup instructions.

