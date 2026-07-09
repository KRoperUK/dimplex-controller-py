# API reference

Detailed reference for `dimplex-controller-py`. All public classes, methods and data models are covered here.

## `DimplexControl`

The main client class. It handles authentication, request construction and error mapping.

### Constructor

```python
DimplexControl(
    session: aiohttp.ClientSession,
    refresh_token: str | None = None,
    access_token: str | None = None,
    expires_at: int | None = None,
    token_file: str = "dimplex_tokens.json",
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `session` | `aiohttp.ClientSession` | An active `aiohttp` session. |
| `refresh_token` | `str \| None` | Azure B2C refresh token. If `None`, the client attempts to load from `token_file`. |
| `access_token` | `str \| None` | Optional cached access token. |
| `expires_at` | `int \| None` | Unix timestamp when the access token expires. |
| `token_file` | `str` | Path to the token persistence file. |

### Methods

#### `get_hubs() -> list[Hub]`

Returns all Hubs associated with the authenticated account.

```python
hubs = await client.get_hubs()
```

#### `get_hub_zones(hub_id: str) -> list[Zone]`

Returns all Zones for a given Hub.

```python
zones = await client.get_hub_zones("hub-123")
```

#### `get_zone(hub_id: str, zone_id: str) -> Zone`

Returns a single Zone.

```python
zone = await client.get_zone("hub-123", "zone-456")
```

#### `get_appliance_overview(hub_id: str, appliance_ids: list[str]) -> list[ApplianceStatus]`

Returns live telemetry for the specified Appliances.

```python
statuses = await client.get_appliance_overview("hub-123", ["app-1", "app-2"])
```

#### `get_user_context() -> UserContext`

Returns profile information for the authenticated user.

```python
user = await client.get_user_context()
print(user.Email)
```

#### `get_appliance_features(hub_id: str, appliance_ids: list[str]) -> dict`

Returns raw appliance feature data. This is lower-level than `get_appliance_overview`.

```python
features = await client.get_appliance_features("hub-123", ["app-1"])
```

#### `set_mode(hub_id: str, appliance_ids: list[str], mode: str, temperature: float | None = None) -> None`

Set the operation mode for Appliances. Valid modes include `Manual`, `Timer` and `FrostProtection`.

```python
await client.set_mode("hub-123", ["app-1"], "Manual", temperature=21.0)
```

#### `set_target_temperature(...) -> None`

Reserved for future use. Target temperature control is not yet exposed by the GDHV API.

#### `set_appliance_mode(hub_id: str, appliance_ids: list[str], settings: ApplianceModeSettings) -> None`

Send full mode settings. Use this for advanced modes such as Boost.

```python
from dimplex_controller.models import ApplianceModeSettings

boost = ApplianceModeSettings(ApplianceModes=16, Status=1, Temperature=25.0)
await client.set_appliance_mode("hub-123", ["app-1"], boost)
```

#### `set_eco_start(hub_id: str, appliance_ids: list[str], enabled: bool) -> None`

Toggle EcoStart.

```python
await client.set_eco_start("hub-123", ["app-1"], True)
```

#### `set_open_window_detection(hub_id: str, appliance_ids: list[str], enabled: bool) -> None`

Toggle Open Window Detection.

```python
await client.set_open_window_detection("hub-123", ["app-1"], True)
```

#### `get_tsi_energy_report(hub_id: str) -> TsiEnergyReport`

Fetch the Time Series Insights energy report for a Hub.

```python
report = await client.get_tsi_energy_report("hub-123")
for appliance_id, telemetry in report.telemetry.items():
    print(f"{appliance_id}: {telemetry}")
```

## Models

### `Hub`

| Field | Type | Description |
|-------|------|-------------|
| `HubId` | `str` | Unique Hub identifier. |
| `Name` | `str` | Human-readable name. |

### `Zone`

| Field | Type | Description |
|-------|------|-------------|
| `ZoneId` | `str` | Unique Zone identifier. |
| `ZoneName` | `str` | Human-readable name. |
| `Appliances` | `list[Appliance]` | Appliances in this Zone. |

### `Appliance`

| Field | Type | Description |
|-------|------|-------------|
| `ApplianceId` | `str` | Unique Appliance identifier. |
| `Name` | `str` | Human-readable name. |
| `Type` | `str` | Appliance type (e.g. `QRAD`). |

### `ApplianceStatus`

| Field | Type | Description |
|-------|------|-------------|
| `ApplianceId` | `str` | Appliance identifier. |
| `RoomTemperature` | `float \| None` | Current room temperature in °C. |
| `ActiveSetPointTemperature` | `float \| None` | Current target temperature in °C. |
| `ComfortStatus` | `str \| None` | Comfort mode status. |
| `EcoStartEnabled` | `bool \| None` | Whether EcoStart is active. |
| `ApplianceModes` | `int \| None` | Current mode bitmask. |
| `BoostActive` | `bool \| None` | Whether Boost is active. |
| `AwayModeActive` | `bool \| None` | Whether Away mode is active. |
| `OpenWindowDetected` | `bool \| None` | Whether an open window is detected. |

> **Note:** Field availability depends on firmware version and appliance type. Not all fields will be present for every device.

### `ApplianceModeSettings`

Payload for `set_appliance_mode`.

| Field | Type | Description |
|-------|------|-------------|
| `ApplianceModes` | `int` | Mode bitmask (e.g. `16` for Boost). |
| `Status` | `int` | Mode status (`1` = On, `0` = Off). |
| `Temperature` | `float` | Target temperature in °C. |

### `TimerPeriod` / `TimerModeSettings`

Structures for timer schedules. See `models.py` for the full field list.

### `UserContext`

| Field | Type | Description |
|-------|------|-------------|
| `UserId` | `str` | Unique user identifier. |
| `Email` | `str` | Account email address. |
| `Name` | `str \| None` | Display name. |

### `TsiEnergyReport`

| Field | Type | Description |
|-------|------|-------------|
| `hub_id` | `str` | Hub identifier. |
| `telemetry` | `dict[str, list]` | Energy data keyed by Appliance ID. |

### `parse_telemetry_points(telemetry: Any) -> list[tuple[datetime, float]]`

Normalise arbitrary telemetry response shapes into a sorted list of `(timestamp, value)` tuples.

Accepts:
- Lists of `[timestamp, value]` pairs.
- Dictionaries with variant key names.
- Bare scalar values (with the current time as the timestamp).

## Exceptions

### `DimplexError`

Base exception for all library errors.

### `DimplexAuthError`

Raised when authentication or token refresh fails.

```python
from dimplex_controller import DimplexControl, DimplexAuthError

try:
    await client.get_hubs()
except DimplexAuthError:
    print("Token expired — re-authenticate.")
```

### `DimplexApiError`

Raised when the API returns a non-success HTTP status.

| Attribute | Type | Description |
|-----------|------|-------------|
| `status` | `int` | HTTP status code. |
| `message` | `str` | Error message from the API. |

```python
from dimplex_controller import DimplexApiError

try:
    await client.get_hubs()
except DimplexApiError as e:
    print(f"API error {e.status}: {e.message}")
```

### `DimplexConnectionError`

Raised on network-level failures (DNS, connection refused, timeout, etc.).

```python
from dimplex_controller import DimplexConnectionError

try:
    await client.get_hubs()
except DimplexConnectionError:
    print("Could not reach the Dimplex cloud.")
```
