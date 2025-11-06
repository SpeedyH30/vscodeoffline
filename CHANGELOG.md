# Change Log for Visual Studio Code - Offline Gallery and Updater

## [2.0.3] - 2025-11-06

### Added

- Configurable refresh interval via `REFRESH_INTERVAL` environment variable (default: 3600 seconds)
- Enhanced status page showing auto-refresh timing information
  - Last refresh time
  - Next refresh time
  - Refresh interval
  - Current refresh status
- Improved logging for extension refresh checks with emojis (🔍 Checking, ✅ Complete)
- JSON API now includes detailed refresh timing in `refresh` object
- Application logs now properly output to Docker logs via gunicorn configuration
  - Added `--error-logfile`, `--capture-output`, and `--enable-stdio-inheritance` flags
  - Set `PYTHONUNBUFFERED=1` for immediate log output
  - Logs show extension refresh checks and completion messages

### Changed

- Status page now clearly indicates when gallery is checking for new extensions
- Auto-refresh card added to status dashboard for better visibility
- Logging format standardized with timestamps for easier troubleshooting

## [2.0.2] - 2025-11-06

### Fixed

- **Critical:** Removed `--preload` flag from gunicorn configuration that prevented background extension indexing thread from running in worker processes
- Gallery now properly detects and indexes new extensions automatically within the hourly refresh interval
- Fixed issue where gallery would serve stale extension data indefinitely despite new extensions being synced
- Updated deprecated `datetime.utcnow()` to use timezone-aware `datetime.now(datetime.UTC)`
- Optimized Docker image size from 467MB to 25.5MB by combining build dependency installation and cleanup into single layer

## [2.0.1] - 2025-11-06

### Fixed

- Added validation for extension names in API queries to ensure proper `publisher.extension` format
- Improved error handling to prevent 400 errors from malformed extension name queries
- Added clear error messages when extension names don't include publisher prefix
- Enhanced extension name validation in custom extension JSON file processing

## [2.0.0] - 2025-11-05

### Major Changes

- Complete modernization for Microsoft API compatibility with enhanced session management and retry logic
- Expanded platform support from 11 to 29 comprehensive platforms including Windows ARM64, Linux variants, macOS Intel/Apple Silicon, Server packages, and CLI tools
- Added support for modern VS Code endpoints including AI/Chat features and CDN compatibility
- Enhanced error handling with exponential backoff, jitter, and rate limiting for 429 errors
- Updated Microsoft Update API integration with proper commit ID handling

### Added

- New platform filtering options: --include-server, --include-cli, --include-arm
- Enhanced --platforms flag supporting comma-separated platform lists
- --exclude-platforms option for granular platform control
- VSCChat class for modern VS Code AI/Chat endpoint support
- VSCUnpkg class for CDN compatibility and unpkg endpoint handling
- Resilient request handling with automatic retry mechanisms
- Support for 18 additional VS Code platforms covering comprehensive architecture matrix
- New status monitoring pages with real-time sync status and health checks
- Enhanced HTML interface with improved navigation and responsive design
- Modern web UI with updated styling and better user experience
- Status dashboard for monitoring sync operations and container health

### Changed

- Updated default artifacts directory path for container compatibility
- Improved Docker networking configuration with host network mode for DNS resolution
- Enhanced platform validation and smart combination filtering
- Modernized session management with connection pooling and timeout handling
- Optimized Docker builds using Alpine Linux base images with dependency isolation
- Updated container environment configuration removing obsolete directives
- Redesigned all HTML templates with modern CSS and responsive layout
- Improved gallery browsing interface with better extension discovery
- Enhanced status reporting with comprehensive metrics and health indicators
- Streamlined web interface navigation and accessibility improvements

### Fixed

- Resolved DNS resolution issues in containerized environments
- Fixed Microsoft Update API compatibility with proper version discovery
- Corrected artifacts directory path resolution in Docker containers
- Improved error handling for rate limiting and connection timeouts
- Enhanced platform compatibility matrix validation

## [1.0.24] - 2023-06-05

### Fixed

- Improvements to requests session handling to prevent ConnectionErrors due to repeated connections. Thanks @tomer953 for reporting.

### Added

- Note about Firefox in Readme.md. Thanks @jmorcate for highlighting this gap.

### Changed

- Sort gallery listings with simple python sort.
- Removed deprecated logzero dependency, switched to logging. Thanks @bdsoha for the implementation and note.

## [1.0.23] - 2022-11-09

### Fixed

- @forky2 resolved an issue related to incorrect version ordering (from reverse-alphanumberical to reverse-chronological), which prevented extensions updating correctly by vscode clients.

## [1.0.22] - 2022-10-31

### Added

- @maxtruxa added support for specifying docker container environment variable `SSLARGS` to control SSL arguments, or disable SSL by setting `BIND=0.0.0.0:80` and `SSLARGS=` (empty).

### Changed

- @Precioussheep improved consistency of the codebase, reducing bonus code and added typing.

## [1.0.21] - 2022-08-08

### Added

- @tomer953 added support for fetching a specified number of recommended extensions `--total-recommended`.
- @Ebsan added support for fetching pre-release extensions `--prerelease-extensions` and fix fetching other extensions [#31](https://github.com/LOLINTERNETZ/vscodeoffline/issues/31).
- @Ebsan added support for specifying which Visual Studio Code version to masquerade as when fetching extensions `--vscode-version`.

### Changed

- Merge dependabot suggestions for CI pipeline updates.
- Utilise individual requests, rather than a Requests session, for fetching extensions to improve stability of fetch process. Should resolve [#33](https://github.com/LOLINTERNETZ/vscodeoffline/issues/33). Thanks @Ebsan for the fix and @annieherram for reporting.
- Updated build-in certificate and key to update its expiry [#37](https://github.com/LOLINTERNETZ/vscodeoffline/issues/37). Included CA chain aswell. Thanks for reporting @Ebsan.
- Removed platform suport for ia32 builds, as they're no longer provided since ~1.35.
- Split out this changelog.

### Fixed

- @tomer953 removed a duplicate flag to QueryFlags.
- @Ebsan fixed an issue with downloading cross-platform extensions [#24](https://github.com/LOLINTERNETZ/vscodeoffline/issues/24).

## [1.0.20]

### Fixed

- Fixed an issue when downloading multiple versions of extensions. Thanks @forky2!

## [1.0.19]

### Fixed

- Lots of really solid bug fixes. Thank you to @fullylegit! Resilience improvements when fetching from marketplace. Thanks @forky2 and @ebsan.

## [1.0.18]

### Changed

- Meta release to trigger CI.

## [1.0.17]

### Changed

- CORS support for gallery. Thanks @kenyon!

## [1.0.16]

### Changed

- Support for saving sync logs to file. Thanks @ap0yuv!

## [1.0.16]

### Changed

- Improve extension stats handling.

## [1.0.14]

### Fixed

- Fixed insider builds being re-fetched.

## [1.0.13]

### Added

- Added initial support for extension version handling. Hopefully this resolves issue #4.

## [1.0.12]

### Fixed

- @ttutko fixed a bug preventing multiple build qualities (stable/insider) from being downloaded. Thanks @darkonejr for investigating and reporting.

## [1.0.11]

### Fixed

- Fixed bugs in Gallery sorting, and added timeouts for Sync.

## [1.0.10]

### Changed

- Refactored to improve consistency.

## [1.0.9]

### Added

- Added support for Remote Development, currently (2019-05-12) available to insiders. Refactored various badness.

## [1.0.8]

### Added

- Insiders support and extension packs (remotes).
