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

Because Azure AD B2C does not support fully headless password login without a browser, you must complete a one-time interactive authentication.

Run the demo script:

```bash
python demo.py
```

You will see:

1. A URL printed to the terminal.
2. Open that URL in your browser.
3. Log in with your Dimplex credentials.
4. After signing in, you will be redirected to a `msal...://auth/` page that fails to load (this is expected).
5. Copy the full redirect URL from the browser address bar (it contains `?code=...`).
6. Paste it back into the terminal.

The script exchanges the code for tokens and writes them to `dimplex_tokens.json` in the current working directory.

> **Tip:** Add `dimplex_tokens.json` to your `.gitignore` so you do not accidentally commit tokens.

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
