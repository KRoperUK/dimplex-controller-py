# Changelog

All notable changes to this project will be documented in this file.

## [0.10.1](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.10.0...v0.10.1) (2026-07-13)


### Bug Fixes

* document and test the empty-overview (HTTP 200) return value ([#67](https://github.com/KRoperUK/dimplex-controller-py/issues/67)) ([642dde3](https://github.com/KRoperUK/dimplex-controller-py/commit/642dde3de4e882699ebe9f26b845b8871a9d11cd))

## [0.10.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.9.0...v0.10.0) (2026-07-13)


### Features

* add dimplex CLI for hubs, status, energy, control ([520219c](https://github.com/KRoperUK/dimplex-controller-py/commit/520219c718d3ff726b7195fc932483691837b1a2)), closes [#48](https://github.com/KRoperUK/dimplex-controller-py/issues/48)
* appliance capability matrix ([#55](https://github.com/KRoperUK/dimplex-controller-py/issues/55)) ([e2b0bf7](https://github.com/KRoperUK/dimplex-controller-py/commit/e2b0bf717c0ebbcc67325bc7b966b74b8014bc13))
* centralized HTTP retry with backoff for idempotent GETs ([2711950](https://github.com/KRoperUK/dimplex-controller-py/commit/2711950bed05378f09fae064a75c84aec4c054da)), closes [#49](https://github.com/KRoperUK/dimplex-controller-py/issues/49)
* dimplex CLI for smoke tests ([#59](https://github.com/KRoperUK/dimplex-controller-py/issues/59)) ([520219c](https://github.com/KRoperUK/dimplex-controller-py/commit/520219c718d3ff726b7195fc932483691837b1a2))
* HTTP retry and rate-limit backoff ([#57](https://github.com/KRoperUK/dimplex-controller-py/issues/57)) ([2711950](https://github.com/KRoperUK/dimplex-controller-py/commit/2711950bed05378f09fae064a75c84aec4c054da))
* safe schedule read/write helpers for timer periods ([b373360](https://github.com/KRoperUK/dimplex-controller-py/commit/b3733607143270bb4874d6a0e94626864baaac2b)), closes [#50](https://github.com/KRoperUK/dimplex-controller-py/issues/50)
* schedule helpers for timer periods ([#58](https://github.com/KRoperUK/dimplex-controller-py/issues/58)) ([b373360](https://github.com/KRoperUK/dimplex-controller-py/commit/b3733607143270bb4874d6a0e94626864baaac2b))


### Bug Fixes

* keep T1 and T2 energy registers separate ([#62](https://github.com/KRoperUK/dimplex-controller-py/issues/62)) ([d5436f4](https://github.com/KRoperUK/dimplex-controller-py/commit/d5436f4d877a31e4e906b5004e7c3fa6859ffcf9))


### Documentation

* compatibility matrix and power/setback research ([#61](https://github.com/KRoperUK/dimplex-controller-py/issues/61)) ([8aec41d](https://github.com/KRoperUK/dimplex-controller-py/commit/8aec41d7c76b030a9f923ad52eb4952945aee4ac))
* HA compatibility matrix and power/setback research notes ([8aec41d](https://github.com/KRoperUK/dimplex-controller-py/commit/8aec41d7c76b030a9f923ad52eb4952945aee4ac)), closes [#54](https://github.com/KRoperUK/dimplex-controller-py/issues/54)

## [0.9.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.8.0...v0.9.0) (2026-07-13)


### Features

* structured auth errors and raise AuthManager coverage ([#45](https://github.com/KRoperUK/dimplex-controller-py/issues/45)) ([c737cfe](https://github.com/KRoperUK/dimplex-controller-py/commit/c737cfe1054e4f3f5d923520906e7eb316aba845))

## [0.8.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.7.0...v0.8.0) (2026-07-13)


### Features

* product catalogue API, auth coverage, and dotenv hygiene ([812eb20](https://github.com/KRoperUK/dimplex-controller-py/commit/812eb200085726926390c92f76afc92b7dc70590))
* product catalogue API, auth coverage, dotenv hygiene ([#43](https://github.com/KRoperUK/dimplex-controller-py/issues/43)) ([812eb20](https://github.com/KRoperUK/dimplex-controller-py/commit/812eb200085726926390c92f76afc92b7dc70590))

## [0.7.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.6.1...v0.7.0) (2026-07-13)


### Features

* energy summaries, control helpers, and public token surface ([#41](https://github.com/KRoperUK/dimplex-controller-py/issues/41)) ([9b56840](https://github.com/KRoperUK/dimplex-controller-py/commit/9b56840ce0e5c42555435e33de64cf4e003e20ea))

## [0.6.1](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.6.0...v0.6.1) (2026-07-12)


### Bug Fixes

* handle ST energy telemetry and required report payload ([#31](https://github.com/KRoperUK/dimplex-controller-py/issues/31)) ([7a3714b](https://github.com/KRoperUK/dimplex-controller-py/commit/7a3714bcf5d601f11b858f004e21dd049159ff36))

## [0.6.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.5.0...v0.6.0) (2026-07-09)


### Features

* extend models and telemetry for additional sensor data ([#30](https://github.com/KRoperUK/dimplex-controller-py/issues/30)) ([daf92dc](https://github.com/KRoperUK/dimplex-controller-py/commit/daf92dc16fe19cf3cedd78e7b4e257c4bf56c5a6))


### Documentation

* overhaul README and add comprehensive documentation ([#28](https://github.com/KRoperUK/dimplex-controller-py/issues/28)) ([b998615](https://github.com/KRoperUK/dimplex-controller-py/commit/b998615766702ab53b9a53b99357f446e5444b31))

## [0.5.0](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.4.1...v0.5.0) (2026-07-09)


### Features

* add TsiEnergyReport endpoint + telemetry parser ([#16](https://github.com/KRoperUK/dimplex-controller-py/issues/16)) ([c125f19](https://github.com/KRoperUK/dimplex-controller-py/commit/c125f190bbafa337262707d9d7bbf00fd5f12900))
* initial ([#1](https://github.com/KRoperUK/dimplex-controller-py/issues/1)) ([074baac](https://github.com/KRoperUK/dimplex-controller-py/commit/074baac298688997d807a4f6e577a894639ac61c))
* release ([#6](https://github.com/KRoperUK/dimplex-controller-py/issues/6)) ([265dc4d](https://github.com/KRoperUK/dimplex-controller-py/commit/265dc4dbd8ed3d11103365bb0767c2fb325e0482))
* robust headless B2C login ([#13](https://github.com/KRoperUK/dimplex-controller-py/issues/13)) ([a7d5064](https://github.com/KRoperUK/dimplex-controller-py/commit/a7d506466bf9177b1f850bb53678479a2c74f030))
* robust headless B2C login with proper cookie handling ([a7d5064](https://github.com/KRoperUK/dimplex-controller-py/commit/a7d506466bf9177b1f850bb53678479a2c74f030))


### Bug Fixes

* parse T1/TS energy telemetry keys from Dimplex cloud API ([#22](https://github.com/KRoperUK/dimplex-controller-py/issues/22)) ([4af7472](https://github.com/KRoperUK/dimplex-controller-py/commit/4af74722b6a7a350c0626ca2aa0841153d3d3abe))
* prettier ignore changelog ([#9](https://github.com/KRoperUK/dimplex-controller-py/issues/9)) ([d91ac64](https://github.com/KRoperUK/dimplex-controller-py/commit/d91ac64651c14c1ee53e627795e7563d120f47b7))
* PyPI publish workflow — use release/v1, verbose logging, correct env URL ([#24](https://github.com/KRoperUK/dimplex-controller-py/issues/24)) ([db472e9](https://github.com/KRoperUK/dimplex-controller-py/commit/db472e9c7697c2af97b56d3b65756023cd50eae8))
* regenerate poetry.lock for yanked virtualenv ([#11](https://github.com/KRoperUK/dimplex-controller-py/issues/11)) ([93ca460](https://github.com/KRoperUK/dimplex-controller-py/commit/93ca460c654fce40366edd6f50b4db7bec36acdd))
* regenerate poetry.lock to resolve yanked virtualenv 20.37.0 ([93ca460](https://github.com/KRoperUK/dimplex-controller-py/commit/93ca460c654fce40366edd6f50b4db7bec36acdd))
* remove unused imports causing ruff lint failure ([#14](https://github.com/KRoperUK/dimplex-controller-py/issues/14)) ([7e97c30](https://github.com/KRoperUK/dimplex-controller-py/commit/7e97c30a4169e7379718bcebb355ad42e79e474c))
* ruff format ([#15](https://github.com/KRoperUK/dimplex-controller-py/issues/15)) ([ea24ad8](https://github.com/KRoperUK/dimplex-controller-py/commit/ea24ad8da60e13929bd6db33078057fdf3f39e11))
* use release/v1 tag and correct pypi environment URL ([db472e9](https://github.com/KRoperUK/dimplex-controller-py/commit/db472e9c7697c2af97b56d3b65756023cd50eae8))


### Documentation

* add readme badges ([#4](https://github.com/KRoperUK/dimplex-controller-py/issues/4)) ([fc82d23](https://github.com/KRoperUK/dimplex-controller-py/commit/fc82d23da54176f35e35fb8e24270ddc3446ba97))

## [0.4.1](https://github.com/KRoperUK/dimplex-controller-py/compare/v0.4.0...v0.4.1) (2026-07-09)


### Bug Fixes

* parse T1/TS energy telemetry keys from Dimplex cloud API ([#22](https://github.com/KRoperUK/dimplex-controller-py/issues/22)) ([4af7472](https://github.com/KRoperUK/dimplex-controller-py/commit/4af74722b6a7a350c0626ca2aa0841153d3d3abe))

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
