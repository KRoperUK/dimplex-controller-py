# Getting started

This guide covers everything you need to go from zero to controlling your Dimplex heating with `dimplex-controller-py`.

## Prerequisites

- Python 3.10 or later.
- An account on the Dimplex cloud (the same credentials you use in the official Dimplex Control app).
- Internet access — the library talks to the GDHV IoT cloud.

## Installation

Choose the installation method that suits your use case.

### End users

Install from PyPI:

```bash
pip install dimplex-controller
```

### Developers

Clone the repository and install in editable mode with dev dependencies:

```bash
git clone https://github.com/KRoperUK/dimplex-controller-py.git
cd dimplex-controller-py
pip install -e ".[dev]"
```

This installs the library plus `pytest`, `ruff`, `pre-commit`, `mypy` and `twine`.

## First run

The library supports two authentication methods:

### Headless login (recommended)

No browser needed. From a script or the CLI:

```python
import asyncio
from aiohttp import ClientSession
from dimplex_controller import DimplexControl

async def main():
    async with ClientSession() as session:
        client = DimplexControl(session)
        await client.auth.headless_login("your@email.com", "your_password")
        # Persist tokens for next time:
        tokens = client.export_tokens()
        print(tokens.as_dict())

asyncio.run(main())
```

Or via the CLI:

```bash
pip install dimplex-controller
export DIMPLEX_REFRESH_TOKEN=...  # from a previous run
dimplex login
dimplex hubs
```

### Manual browser flow (fallback)

If headless login fails (e.g. CAPTCHA or MFA changes), fall back to the browser flow:

```bash
python demo.py
```

1. A URL is printed — open it in your browser.
2. Log in with your Dimplex credentials.
3. You are redirected to `msal...://auth/` which fails to load (expected).
4. Copy the full redirect URL and paste it back.
5. Tokens are saved to `dimplex_tokens.json`.

> **Tip:** Add `dimplex_tokens.json` to `.gitignore`.

## Writing your first script

Create a file called `check_status.py`:

```python
import asyncio
from aiohttp import ClientSession
from dimplex_controller import DimplexControl

async def main() -> None:
    async with ClientSession() as session:
        client = DimplexControl(session)

        hubs = await client.get_hubs()
        if not hubs:
            print("No hubs found. Check that your account has appliances registered.")
            return

        for hub in hubs:
            print(f"Hub: {hub.Name}")
            zones = await client.get_hub_zones(hub.HubId)
            for zone in zones:
                print(f"  Zone: {zone.ZoneName}")
                for appliance in zone.Appliances:
                    print(f"    Appliance: {appliance.ApplianceId}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python check_status.py
```

If your tokens are valid, you should see your Hubs and Zones printed to the console.

## Reading live status

Extend the script to fetch live telemetry:

```python
status_list = await client.get_appliance_overview(hub_id, [appliance_id])

for status in status_list:
    print(f"Room temperature: {status.RoomTemperature}°C")
    print(f"Active set point: {status.ActiveSetPointTemperature}°C")
    print(f"EcoStart: {status.EcoStartEnabled}")
    print(f"Comfort: {status.ComfortStatus}")
```

## Sending a command

Try enabling EcoStart:

```python
from dimplex_controller import DimplexControl

async with ClientSession() as session:
    client = DimplexControl(session)
    await client.set_eco_start(hub_id, [appliance_id], True)
    print("EcoStart enabled")
```

## What next?

- Read the [configuration guide](configuration.md) for environment variables and token management options.
- Browse the [API reference](api-reference.md) for every method and model.
- Check [troubleshooting](troubleshooting.md) if you hit problems.
