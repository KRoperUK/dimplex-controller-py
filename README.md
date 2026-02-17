# Dimplex Controller Python Client

A Python asyncio client for controlling Dimplex heating systems (GDHV IoT).

## Features

- **Authentication**: Easy login flow and automatic token refresh (Azure B2C).
- **Discovery**: List Hubs, Zones, and Appliances associated with your account.
- **Detailed Status**: Fetch real-time data including room temperature, setpoints, comfort status, and active boost settings.
- **Control**:
  - Set operation modes (Manual, Timer, Frost Protection).
  - Activate **Boost** and **Away** modes.
  - Toggle **EcoStart** and **Open Window Detection**.
  - Program heating schedules (Timer Periods).

## Installation

This project is managed with Poetry.

```bash
git clone <repo-url>
cd dimplex-controller-py
poetry install
```

## Getting Started

### 1. Initial Authentication
Due to the nature of the Azure B2C flow, you must perform the initial login manually to capture an authorization code.

Run the demo script to guide you through the process:

```bash
poetry run python demo.py
```

Follow the on-screen instructions. Once successful, a `dimplex_tokens.json` file will be created, allowing the library to authenticate automatically in the future.

### 2. Basic Usage

```python
import asyncio
import aiohttp
from dimplex_controller import DimplexControl

async def main():
    async with aiohttp.ClientSession() as session:
        # Pass tokens from dimplex_tokens.json or just the refresh_token
        client = DimplexControl(session, refresh_token="YOUR_REFRESH_TOKEN")

        # Get Hubs
        hubs = await client.get_hubs()
        for hub in hubs:
            print(f"Hub: {hub.Name}")

            # Get Zones and Appliances
            zones = await client.get_hub_zones(hub.HubId)
            for zone in zones:
                print(f"  Zone: {zone.ZoneName}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Advanced Operations

#### Get Real-time Status
```python
# Fetch status for a list of appliance IDs
status_list = await client.get_appliance_overview(hub_id, ["appliance_id_1", "appliance_id_2"])

for status in status_list:
    print(f"Temp: {status.RoomTemperature}°C, Target: {status.ActiveSetPointTemperature}°C")
    print(f"EcoStart: {status.EcoStartEnabled}")
```

#### Control Features
```python
from dimplex_controller.models import ApplianceModeSettings

# Enable EcoStart
await client.set_eco_start(hub_id, [appliance_id], True)

# Enable Open Window Detection
await client.set_open_window_detection(hub_id, [appliance_id], True)

# Activate Boost (Mode 16, Status 1 = On)
boost_settings = ApplianceModeSettings(ApplianceModes=16, Status=1, Temperature=25.0)
await client.set_appliance_mode(hub_id, [appliance_id], boost_settings)
```

## Development & API Reference

- **`openapi.yaml`**: This file contains the most complete technical specification of the API discovered so far. It includes all known endpoints, request bodies, and response schemas.
- **Traffic Logs**: If you identify new features in the mobile app, capture the traffic and add the endpoints to `openapi.yaml` and the `DimplexControl` client.

## Disclaimer

This is an unofficial library and is not affiliated with or endorsed by Glen Dimplex Heating & Ventilation (GDHV). Use it at your own risk.
