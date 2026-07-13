# Dimplex Controller Python Client

[![PyPI version](https://img.shields.io/pypi/v/dimplex-controller.svg)](https://pypi.org/project/dimplex-controller/)
[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI Tests](https://github.com/KRoperUK/dimplex-controller-py/actions/workflows/tests.yml/badge.svg)](https://github.com/KRoperUK/dimplex-controller-py/actions)
[![Downloads](https://img.shields.io/pypi/dm/dimplex-controller.svg)](https://pypi.org/project/dimplex-controller/)

<p align="center">
  <strong>Async Python client for controlling Glen Dimplex Heating &amp; Ventilation (GDHV) appliances via the Dimplex cloud API.</strong>
</p>

---

## What does this do?

`dimplex-controller-py` is an asynchronous Python client that talks to the GDHV IoT cloud platform. It handles Azure B2C authentication (including automatic token refresh), discovers your Hubs, Zones and Appliances, and lets you read telemetry and send control commands — all from a script or a larger application.

It is the engine behind the [Dimplex Hub Home Assistant integration](https://github.com/KRoperUK/dimplex-controller-hass) and is published to PyPI as [`dimplex-controller`](https://pypi.org/project/dimplex-controller/).

> **Note:** This is an unofficial library and is not affiliated with or endorsed by Glen Dimplex Heating & Ventilation (GDHV). Use it at your own risk.

## Contents

- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Usage guide](#usage-guide)
  - [Authentication](#authentication)
  - [Discovery](#discovery)
  - [Reading status](#reading-status)
  - [Sending control commands](#sending-control-commands)
  - [Energy reports](#energy-reports)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Changelog](#changelog)

## Features

- **Authentication** — Azure B2C login with automatic token refresh and secure token persistence.
- **Discovery** — List Hubs, Zones and Appliances linked to your account.
- **Real-time status** — Fetch room temperature, setpoints, comfort status, boost/away modes and EcoStart state.
- **Control** — Set operation modes, activate Boost and Away, toggle EcoStart and Open Window Detection, and programme timer schedules.
- **Energy telemetry** — Pull Time Series Insights (TSI) energy reports with a robust telemetry parser that adapts to varying firmware formats.

## Installation

### From PyPI (recommended)

```bash
pip install dimplex-controller
```

### From source

```bash
git clone https://github.com/KRoperUK/dimplex-controller-py.git
cd dimplex-controller-py
pip install .
```

### Development install

```bash
git clone https://github.com/KRoperUK/dimplex-controller-py.git
cd dimplex-controller-py
pip install -e ".[dev]"
```

> **Requires:** Python 3.10 or later.

## Quick start

The library uses `asyncio` and `aiohttp`. Here is the smallest example that lists your Hubs and Zones:

```python
import asyncio
from aiohttp import ClientSession
from dimplex_controller import DimplexControl

async def main() -> None:
    async with ClientSession() as session:
        client = DimplexControl(session, refresh_token="YOUR_REFRESH_TOKEN")

        hubs = await client.get_hubs()
        for hub in hubs:
            print(f"Hub: {hub.Name}")
            zones = await client.get_hub_zones(hub.HubId)
            for zone in zones:
                print(f"  Zone: {zone.ZoneName}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Usage guide

### Authentication

Dimplex uses Azure AD B2C. You cannot log in purely programmatically with just a username and password — the library must first capture a short-lived authorisation code.

The recommended approach is to run the included demo script once:

```bash
python demo.py
```

The script walks you through opening a browser, signing in, and pasting the resulting redirect URL back into the terminal. On success, it saves a `dimplex_tokens.json` file in the current working directory.

Subsequent runs read the refresh token from that file automatically. You can also pass the refresh token directly to `DimplexControl` if you prefer to manage storage yourself.

### Discovery

```python
hubs = await client.get_hubs()
for hub in hubs:
    print(f"Hub: {hub.Name} ({hub.HubId})")
    zones = await client.get_hub_zones(hub.HubId)
    for zone in zones:
        print(f"  Zone: {zone.ZoneName} ({zone.ZoneId})")
        appliances = zone.Appliances
        for appliance in appliances:
            print(f"    Appliance: {appliance.ApplianceId}")
```

### Reading status

```python
from dimplex_controller.models import ApplianceStatus

status_list = await client.get_appliance_overview(hub_id, [appliance_id_1, appliance_id_2])

for status in status_list:
    print(f"Room temperature: {status.RoomTemperature}°C")
    print(f"Target temperature: {status.ActiveSetPointTemperature}°C")
    print(f"EcoStart enabled: {status.EcoStartEnabled}")
    print(f"Comfort status: {status.ComfortStatus}")
```

### Sending control commands

```python
from dimplex_controller.models import ApplianceModeSettings

# Enable EcoStart
await client.set_eco_start(hub_id, [appliance_id], True)

# Enable Open Window Detection
await client.set_open_window_detection(hub_id, [appliance_id], True)

# Activate Boost
await client.set_boost(hub_id, [appliance_id], temperature=25.0, duration_minutes=60)

# Set target temperature (rewrites timer period setpoints)
await client.set_target_temperature(hub_id, appliance_id, 21.5)
```

### Energy reports

```python
from dimplex_controller import parse_telemetry_points, summarise_energy

report = await client.get_tsi_energy_report(hub_id)
for appliance_id, telemetry in report.ApplianceTelemetryData.items():
    points = parse_telemetry_points(telemetry)
    daily = summarise_energy(points, mode="daily")
    lifetime = summarise_energy(points, mode="lifetime")
    print(f"{appliance_id}: today={daily.total_kwh} kWh, lifetime={lifetime.total_kwh} kWh")
```

`parse_telemetry_points` normalises firmware-varying point shapes. `summarise_energy` builds **daily** (local midnight) and **lifetime** totals. With `include_previous_period=True` the cloud often returns full history — filter client-side rather than trusting `days_back` alone.

## Configuration

| Environment variable | Purpose |
|---------------------|---------|
| `DIMPLEX_TOKENS_FILE` | Path to the JSON token store. Defaults to `dimplex_tokens.json`. |

## API reference

### `DimplexControl`

Main client class. Construct with an `aiohttp.ClientSession` and a `refresh_token`.

| Method | Description |
|--------|-------------|
| `get_hubs()` | Returns `list[Hub]`. |
| `get_hub_zones(hub_id)` | Returns `list[Zone]` for a Hub. |
| `get_zone(hub_id, zone_id)` | Returns a single `Zone`. |
| `get_appliance_overview(hub_id, appliance_ids)` | Returns `list[ApplianceStatus]`. |
| `get_user_context()` | Returns `UserContext`. |
| `get_appliance_features(hub_id, appliance_ids)` | Returns raw appliance feature data. |
| `set_mode(hub_id, appliance_ids, mode, temperature)` | Set operation mode. |
| `set_target_temperature(...)` | Placeholder for future target temperature control. |
| `set_appliance_mode(hub_id, appliance_ids, settings)` | Send full mode settings. |
| `set_eco_start(hub_id, appliance_ids, enabled)` | Toggle EcoStart. |
| `set_open_window_detection(hub_id, appliance_ids, enabled)` | Toggle Open Window Detection. |
| `get_tsi_energy_report(hub_id)` | Returns `TsiEnergyReport`. |

### Models

- **`Hub`** — Hub metadata.
- **`Zone`** — Zone metadata with linked Appliances.
- **`Appliance`** — Appliance metadata.
- **`ApplianceStatus`** — Live telemetry (room temperature, setpoints, comfort, etc.).
- **`ApplianceModeSettings`** — Payload for mode changes.
- **`TimerPeriod`** / **`TimerModeSettings`** — Timer schedule structures.
- **`UserContext`** — Authenticated user profile.
- **`TsiEnergyReport`** — Energy telemetry keyed by appliance.

### Exceptions

- **`DimplexError`** — Base exception.
- **`DimplexAuthError`** — Authentication or token errors.
- **`DimplexApiError`** — API returned a non-success status. Contains `status` and `message`.
- **`DimplexConnectionError`** — Network-level failures.

## Troubleshooting

### Authentication failures

- Verify that the refresh token in `dimplex_tokens.json` has not expired. Delete the file and re-run `demo.py` to capture a fresh one.
- Ensure your network can reach `login.microsoftonline.com` and the Dimplex API endpoints.
- If you have multi-factor authentication (MFA) enabled on your Dimplex account, the headless flow should still work because it uses a browser session you control manually.

### `DimplexAuthError`

This means the API rejected the token. Common causes:
- Token file is missing or corrupt.
- The refresh token has expired (Azure B2C refresh tokens typically last 90 days).
- The token was revoked from the Azure portal.

**Fix:** Delete `dimplex_tokens.json` and re-run the `demo.py` flow.

### `DimplexConnectionError`

The library could not reach the GDHV API. Check:
- Internet connectivity.
- DNS resolution for `api.gdhv.io` (or whatever endpoint is configured in `const.py`).
- No corporate firewall or proxy is blocking `HTTPS` traffic.

### Telemetry parsing errors

If `parse_telemetry_points` returns an empty list, the API likely returned an unexpected schema for your firmware version. Please open an issue with a redacted example of the raw response so the parser can be updated.

### Rate limiting

The GDHV cloud API has rate limits. If you hit them, back off for a few minutes before retrying. The library does not currently implement automatic retries with back-off.

## Contributing

Contributions are welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before opening a pull request.

Key points:
- Use **Conventional Commits** (`feat:`, `fix:`, `chore:`, etc.) — this drives the automated changelog and PyPI releases.
- Run `ruff check`, `ruff format --check` and `pytest` locally before pushing.
- Pre-commit hooks are available — run `pre-commit install` once.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
