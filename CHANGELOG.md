# Changelog

All notable changes to this project will be documented in this file.

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
