# Configuration

This page covers configuration options for `dimplex-controller-py`, including environment variables, token management and customisation.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DIMPLEX_TOKENS_FILE` | `dimplex_tokens.json` | Path to the JSON file where tokens are persisted. |

Set the variable before running your script:

```bash
export DIMPLEX_TOKENS_FILE="/secure/location/tokens.json"
python my_script.py
```

Or set it inline:

```bash
DIMPLEX_TOKENS_FILE="./tokens.json" python my_script.py
```

## Token management

### Automatic persistence

By default, `DimplexControl` looks for `dimplex_tokens.json` in the current working directory. If found, it loads the refresh token automatically.

### Manual token loading

Pass tokens directly if you manage storage yourself:

```python
client = DimplexControl(
    session,
    refresh_token="your-refresh-token",
    access_token="your-access-token",
    expires_at=1750000000,
)
```

### Custom token file

Specify an explicit path:

```python
client = DimplexControl(
    session,
    refresh_token="your-refresh-token",
    token_file="/secure/location/tokens.json",
)
```

### Token expiry

Access tokens expire after a short period (typically one hour). `DimplexControl` automatically refreshes them using the refresh token before they expire.

Refresh tokens themselves typically last 90 days. When a refresh token expires, you must re-run the authentication flow (`demo.py`) to obtain a new one.

## Proxy support

`aiohttp.ClientSession` accepts standard proxy arguments. Pass a proxy when constructing the session:

```python
from aiohttp import ClientSession

async with ClientSession(proxy="http://proxy.local:8080") as session:
    client = DimplexControl(session, refresh_token="...")
```

## SSL verification

If you need to disable SSL verification (for example, when intercepting traffic with Charles Proxy during development), pass `verify_ssl=False`:

```python
async with ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
    client = DimplexControl(session, refresh_token="...")
```

> **Warning:** Do not disable SSL verification in production.

## Timeout configuration

`aiohttp` default timeouts apply unless overridden. To increase the total timeout:

```python
from aiohttp import ClientTimeout, ClientSession

timeout = ClientTimeout(total=30)
async with ClientSession(timeout=timeout) as session:
    client = DimplexControl(session, refresh_token="...")
```

## API base URL

The base URL is defined in [`dimplex_controller/const.py`](https://github.com/KRoperUK/dimplex-controller-py/blob/main/dimplex_controller/const.py). It is not currently configurable at runtime.

If Dimplex changes their API endpoint, update the constant and submit a pull request.
