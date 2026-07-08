# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.3.0...v0.4.0) (2026-07-08)


### Features

* add TsiEnergyReport endpoint + telemetry parser ([#16](https://github.com/KRoperUK/dimplex-controller-py/issues/16)) ([c125f19](https://github.com/KRoperUK/dimplex-controller-py/commit/c125f190bbafa337262707d9d7bbf00fd5f12900))

## [0.3.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.2.1...v0.3.0) (2026-06-22)


### Features

* robust headless B2C login ([#13](https://github.com/KRoperUK/dimplex-controller-py/issues/13)) ([a7d5064](https://github.com/KRoperUK/dimplex-controller-py/commit/a7d506466bf9177b1f850bb53678479a2c74f030))
* robust headless B2C login with proper cookie handling ([a7d5064](https://github.com/KRoperUK/dimplex-controller-py/commit/a7d506466bf9177b1f850bb53678479a2c74f030))


### Bug Fixes

* regenerate poetry.lock for yanked virtualenv ([#11](https://github.com/KRoperUK/dimplex-controller-py/issues/11)) ([93ca460](https://github.com/KRoperUK/dimplex-controller-py/commit/93ca460c654fce40366edd6f50b4db7bec36acdd))
* regenerate poetry.lock to resolve yanked virtualenv 20.37.0 ([93ca460](https://github.com/KRoperUK/dimplex-controller-py/commit/93ca460c654fce40366edd6f50b4db7bec36acdd))
* remove unused imports causing ruff lint failure ([#14](https://github.com/KRoperUK/dimplex-controller-py/issues/14)) ([7e97c30](https://github.com/KRoperUK/dimplex-controller-py/commit/7e97c30a4169e7379718bcebb355ad42e79e474c))
* ruff format ([#15](https://github.com/KRoperUK/dimplex-controller-py/issues/15)) ([ea24ad8](https://github.com/KRoperUK/dimplex-controller-py/commit/ea24ad8da60e13929bd6db33078057fdf3f39e11))

## [0.2.1](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.2.0...v0.2.1) (2026-02-18)


### Bug Fixes

* prettier ignore changelog ([#9](https://github.com/KRoperUK/dimplex-controller-py/issues/9)) ([d91ac64](https://github.com/KRoperUK/dimplex-controller-py/commit/d91ac64651c14c1ee53e627795e7563d120f47b7))

## [0.2.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.1.0...v0.2.0) (2026-02-17)


### Features

* release ([#6](https://github.com/KRoperUK/dimplex-controller-py/issues/6)) ([265dc4d](https://github.com/KRoperUK/dimplex-controller-py/commit/265dc4dbd8ed3d11103365bb0767c2fb325e0482))

## 0.1.0 (2026-02-17)


### Features

* initial ([#1](https://github.com/KRoperUK/dimplex-controller-py/issues/1)) ([074baac](https://github.com/KRoperUK/dimplex-controller-py/commit/074baac298688997d807a4f6e577a894639ac61c))


### Documentation

* add readme badges ([#4](https://github.com/KRoperUK/dimplex-controller-py/issues/4)) ([fc82d23](https://github.com/KRoperUK/dimplex-controller-py/commit/fc82d23da54176f35e35fb8e24270ddc3446ba97))

## [1.0.0] - 2026-02-17

### Added
- Initial stable release of dimplex-controller Python client
- Full async/await support with aiohttp for non-blocking operations
- **Authentication**: Azure B2C login flow with automatic token refresh
- **Hub Management**: List and access all hubs associated with your account
- **Zone and Appliance Discovery**: Browse zones, appliances, and their details
- **Real-time Status**: Fetch current room temperature, setpoints, comfort status, boost/away modes
- **Control Operations**:
  - Set operation modes (Manual, Timer, Frost Protection)
  - Activate/deactivate Boost mode with custom duration and temperature
  - Activate/deactivate Away mode with custom settings
  - Toggle EcoStart and Open Window Detection
  - Program heating schedules (Timer Periods with day/time/temperature)
- **Comprehensive Models**: Pydantic-based data models for type safety and validation
- **Error Handling**: Dedicated exception types for auth, API, and connection errors
- **Full Test Suite**: Unit tests with mocked API responses

### Technical Details
- Python 3.10+ support
- Uses Pydantic 2.0+ for data validation
- Dependencies: aiohttp, beautifulsoup4, python-dotenv
- Fully typed with type hints throughout
