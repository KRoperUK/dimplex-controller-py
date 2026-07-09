# Troubleshooting

This page helps you diagnose and resolve common issues with `dimplex-controller-py`.

## Authentication issues

### I cannot log in

**Symptom:** `demo.py` fails, or `DimplexAuthError` is raised immediately.

**Possible causes:**
- Your Dimplex account credentials are incorrect.
- You have MFA enabled and the browser flow is not completing.
- The Azure B2C tenant has been updated by GDHV.

**Steps to resolve:**
1. Verify your credentials work in the official Dimplex Control app.
2. If MFA is enabled, ensure you complete the MFA challenge in the browser before copying the redirect URL.
3. Delete `dimplex_tokens.json` and re-run `demo.py` from scratch.

### Tokens keep expiring

**Symptom:** You are repeatedly asked to re-authenticate.

**Possible causes:**
- The refresh token has expired (Azure B2C refresh tokens typically last 90 days).
- The token file is being deleted or overwritten between runs.

**Steps to resolve:**
1. Check the file modification time of `dimplex_tokens.json`. If it is old, re-authenticate.
2. Ensure your script does not pass a stale `access_token` or `expires_at` value when constructing `DimplexControl`.

## Network issues

### `DimplexConnectionError`

**Symptom:** The library raises `DimplexConnectionError`.

**Possible causes:**
- No internet access.
- A firewall or proxy is blocking HTTPS traffic.
- DNS cannot resolve the GDHV API host.

**Steps to resolve:**
1. Confirm you can reach the internet from the same machine.
2. If behind a corporate proxy, pass the proxy to `aiohttp.ClientSession`.
3. Test DNS resolution: `nslookup api.gdhv.io` (or the endpoint shown in `const.py`).
4. If using Charles Proxy or similar, ensure SSL proxying is configured correctly.

### SSL certificate errors

**Symptom:** `aiohttp.ClientConnectorCertificateError` or similar.

**Possible causes:**
- SSL inspection is enabled on your network.
- Your system clock is out of sync.

**Steps to resolve:**
1. Ensure your system clock is accurate (check with `date` on Linux/macOS).
2. If using an intercepting proxy, you may need to pass the proxy's root certificate to `aiohttp` or disable verification temporarily for debugging:

```python
import aiohttp
from aiohttp import TCPConnector

async with aiohttp.ClientSession(connector=TCPConnector(verify_ssl=False)) as session:
    client = DimplexControl(session, refresh_token="...")
```

> **Warning:** Disabling SSL verification is for debugging only. Do not use it in production.

## Data issues

### No Hubs found

**Symptom:** `get_hubs()` returns an empty list.

**Possible causes:**
- Your account has no appliances registered.
- The GDHV API has changed its discovery endpoint.

**Steps to resolve:**
1. Confirm the official Dimplex Control app shows your appliances.
2. Check the API response by enabling debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. Open an issue with the debug output if the endpoint appears broken.

### Missing fields in `ApplianceStatus`

**Symptom:** Some expected fields (e.g. `RoomTemperature`) are `None` or missing.

**Possible causes:**
- Your appliance firmware is older and does not report those fields.
- The API response schema has changed.

**Steps to resolve:**
1. Compare the JSON response from the API with the `ApplianceStatus` model fields.
2. If new fields are present, update the model and submit a PR.

### Empty energy report

**Symptom:** `get_tsi_energy_report()` returns a report with no telemetry data.

**Possible causes:**
- Your appliances are not metered (only QRAD-style radiators report energy).
- The report window has no data (common in warmer months).

**Steps to resolve:**
1. Confirm your appliances support energy metering.
2. In summer, expect `unavailable` or empty data — this is correct behaviour, not a bug.

## Library issues

### Import errors

**Symptom:** `ModuleNotFoundError: No module named 'dimplex_controller'`.

**Possible causes:**
- The package is not installed.
- You are running from the wrong directory or virtual environment.

**Steps to resolve:**
1. Install the package: `pip install dimplex-controller`.
2. If developing locally, install in editable mode: `pip install -e .`.
3. Ensure your Python interpreter is the one with the package installed.

### Async errors

**Symptom:** `RuntimeError: Event loop is closed` or similar async errors.

**Possible causes:**
- You are calling async methods from a synchronous context without running an event loop.
- Multiple event loops are being created in the same thread.

**Steps to resolve:**
1. Always use `asyncio.run(main())` as the entry point.
2. Do not nest `asyncio.run()` calls.
3. In Jupyter notebooks, use the existing event loop:

```python
import nest_asyncio
nest_asyncio.apply()
```

### `mypy` or `ruff` errors when developing

**Symptom:** Linting or type-checking fails after pulling changes.

**Possible causes:**
- Dependencies are out of date.
- Pre-commit hooks are stale.

**Steps to resolve:**
1. Reinstall dependencies: `poetry install` or `pip install -e ".[dev]"`.
2. Update pre-commit hooks: `pre-commit autoupdate`.
3. Run checks manually: `ruff check dimplex_controller tests && ruff format --check dimplex_controller tests && mypy && pytest`.

## Still stuck?

If you cannot resolve your issue, please [open a GitHub issue](https://github.com/KRoperUK/dimplex-controller-py/issues) with:

1. Your Python version (`python --version`).
2. The `dimplex-controller` version (`pip show dimplex-controller`).
3. The full traceback or error message.
4. A minimal reproduction script if possible.
