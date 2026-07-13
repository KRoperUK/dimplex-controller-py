# API reference

Detailed reference for `dimplex-controller-py`. All public classes, methods and data models are covered here.

## `DimplexControl`

The main client class. It handles authentication, request construction, retry/backoff and error mapping.

### Constructor

```python
DimplexControl(
    session: aiohttp.ClientSession,
    refresh_token: str | None = None,
    access_token: str | None = None,
    expires_at: float = 0,
    *,
    token_bundle: TokenBundle | None = None,
    max_retries: int = 3,
    retry_base_delay: float = 0.5,
    retry_max_delay: float = 8.0,
    retry_non_idempotent: bool = False,
    timeout: float | aiohttp.ClientTimeout | None = 30.0,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `aiohttp.ClientSession` | — | An active `aiohttp` session (caller-managed). |
| `refresh_token` | `str \| None` | `None` | Azure B2C refresh token (legacy; prefer `token_bundle`). |
| `access_token` | `str \| None` | `None` | Cached access token (legacy). |
| `expires_at` | `float` | `0` | Unix timestamp when the access token expires (legacy). |
| `token_bundle` | `TokenBundle \| None` | `None` | Preferred token input for new code. |
| `max_retries` | `int` | `3` | Number of retries after the first attempt (GETs only by default). |
| `retry_base_delay` | `float` | `0.5` | Exponential backoff base in seconds. |
| `retry_max_delay` | `float` | `8.0` | Maximum backoff ceiling in seconds. |
| `retry_non_idempotent` | `bool` | `False` | Set `True` to also retry POST/PUT/PATCH/DELETE. |
| `timeout` | `float \| ClientTimeout \| None` | `30.0` | Total request timeout in seconds (or `None` for aiohttp defaults). |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `is_authenticated` | `bool` | True when a valid access token is available. |

### Methods — token lifecycle

| Method | Returns | Description |
|--------|---------|-------------|
| `export_tokens()` | `TokenBundle` | Snapshot of current auth tokens for persistence. |
| `apply_tokens(bundle)` | `None` | Replace in-memory tokens from a `TokenBundle` or dict. |

### Methods — read

| Method | Returns | Description |
|--------|---------|-------------|
| `get_hubs()` | `list[Hub]` | All Hubs linked to the account. |
| `get_hub_zones(hub_id)` | `list[Zone]` | Zones + appliances for a Hub. |
| `get_zone(hub_id, zone_id)` | `Zone` | Single Zone detail. |
| `get_appliance_overview(hub_id, appliance_ids)` | `list[ApplianceStatus]` | Live overview for specific appliances (may be `[]` when all offline). |
| `get_appliance_overview_map(hub_id, appliance_ids)` | `dict[str, ApplianceStatus \| None]` | Stable id → status mapping (missing = `None`). |
| `get_user_context()` | `UserContext` | Authenticated user profile. |
| `get_product_models()` | `list[ProductModel]` | Cloud product catalogue (cacheable). |
| `get_appliance_features(hub_id, appliance_id)` | `TimerModeSettings` | Timer mode + periods for an appliance. |
| `get_schedule(hub_id, appliance_id)` | `TimerModeSettings` | Alias of `get_appliance_features`. |
| `get_tsi_energy_report(hub_id, ...)` | `TsiEnergyReport` | Per-appliance energy telemetry for a Hub. |

### Methods — write

| Method | Returns | Description |
|--------|---------|-------------|
| `set_mode(hub_id, appliance_id, mode)` | `None` | Change the timer/operation mode (see `TimerMode`). |
| `set_target_temperature(hub_id, appliance_id, temp)` | `None` | Rewrite all timer period setpoints (or install a full-week schedule). |
| `set_period_setpoint(hub_id, appliance_id, *, day_of_week, start_time, temperature, end_time=None)` | `TimerModeSettings` | Update one timer period's setpoint without clobbering others. |
| `update_period(hub_id, appliance_id, period, *, match_start_time=None)` | `TimerModeSettings` | Replace one timer period matched by day + start time. |
| `set_boost(hub_id, appliance_ids, *, temperature, duration_minutes=60, enable=True)` | `None` | Enable or disable Boost. |
| `clear_boost(hub_id, appliance_ids, *, temperature=21.0)` | `None` | Disable Boost (convenience wrapper). |
| `set_away(hub_id, appliance_ids, *, temperature, enable=True, number_of_days=0)` | `None` | Enable or disable Away mode. |
| `clear_away(hub_id, appliance_ids, *, temperature=16.0)` | `None` | Disable Away mode (convenience wrapper). |
| `set_eco_start(hub_id, appliance_ids, enable)` | `None` | Toggle EcoStart. |
| `set_open_window_detection(hub_id, appliance_ids, enable)` | `None` | Toggle Open Window Detection. |
| `set_appliance_mode(hub_id, appliance_ids, mode_settings)` | `None` | Low-level: send a full `ApplianceModeSettings` payload. |

### Static methods

| Method | Returns | Description |
|--------|---------|-------------|
| `capabilities_for(appliance, *, status, product)` | `ApplianceCapabilities` | Derive a capability matrix for an appliance. |

---

## `AuthManager`

Handles Azure AD B2C token lifecycle. Normally accessed via `client.auth`.

| Method | Description |
|--------|-------------|
| `get_access_token()` | Returns a valid access token (refreshes if expired). |
| `refresh_tokens()` | Force-refresh tokens. |
| `exchange_code(code)` | Exchange an OAuth authorization code for tokens. |
| `headless_login(email, password)` | Interactive-free B2C login via HTTP (scrapes CSRF). |
| `get_login_url()` | Browser URL for manual authorization. |
| `export_tokens()` | `TokenBundle` snapshot. |
| `apply_tokens(bundle)` | Replace tokens. |

---

## `TokenBundle`

Frozen dataclass for serialising auth tokens.

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | `str \| None` | Short-lived access token. |
| `refresh_token` | `str \| None` | Long-lived refresh token. |
| `expires_at` | `float` | Unix timestamp of access-token expiry. |

| Method | Returns |
|--------|---------|
| `as_dict()` | `dict` suitable for JSON / config-entry storage. |
| `from_mapping(data)` | Construct from a dict. |

---

## Models

### `Hub`

| Field | Type | Description |
|-------|------|-------------|
| `HubId` | `str` | Unique Hub identifier. |
| `HubName` | `str` | Internal name. |
| `FriendlyName` | `str \| None` | User-facing name (via `Name` alias). |

### `Zone`

| Field | Type | Description |
|-------|------|-------------|
| `ZoneId` | `str` | Unique Zone identifier. |
| `ZoneName` | `str` | Zone display name. |
| `HubId` | `str` | Parent Hub. |
| `ZoneType` | `str \| None` | e.g. `"Heating"`. |
| `Appliances` | `list[Appliance]` | Appliances in this Zone. |

### `Appliance`

| Field | Type | Description |
|-------|------|-------------|
| `ApplianceId` | `str` | Unique Appliance identifier. |
| `FriendlyName` | `str \| None` | Display name. |
| `ApplianceModel` | `str \| None` | Model string. |
| `ApplianceType` | `str \| None` | e.g. `"QRAD"`. |

### `ApplianceStatus`

| Field | Type | Description |
|-------|------|-------------|
| `HubId` | `str` | Parent Hub. |
| `ApplianceId` | `str` | Appliance identifier. |
| `ZoneId` | `str` | Parent Zone. |
| `RoomTemperature` | `float \| None` | Current room temperature °C. |
| `ActiveSetPointTemperature` | `float \| None` | Active target temperature °C. |
| `NormalTemperature` | `float \| None` | Timer/comfort setpoint. |
| `ComfortStatus` | `bool \| None` | True when actively heating. |
| `EcoStartEnabled` | `bool \| None` | Whether EcoStart is on. |
| `OpenWindowEnabled` | `bool \| None` | Open Window Detection on. |
| `ApplianceModes` | `int \| None` | Mode bitmask. |
| `BoostDuration` | `int \| None` | Boost remaining minutes. |
| `BoostTemperature` | `float \| None` | Boost target. |
| `AwayDateTime` | `str \| None` | Away start (non-empty = active). |
| `AwayTemperature` | `float \| None` | Away target. |
| `SetbackEnabled` | `bool \| None` | Setback active. |
| `SetbackTemperature` | `float \| None` | Setback target. |
| `ErrorCode` | `str \| None` | Current fault code. |
| `WarningCode` | `str \| None` | Current warning code. |

Helper properties: `mode_flags` → `ApplianceModeFlag`, `is_boost_active` → `bool`, `is_away_active` → `bool`.

### `ApplianceModeSettings`

Payload for `set_appliance_mode`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ApplianceModes` | `int` | — | Bitmask (`16` = Boost, `32` = Away). |
| `Status` | `int` | — | `1` = on, `0` = off. |
| `Temperature` | `float` | `23.0` | Target temperature. |
| `Time` | `int` | `0` | Duration (Boost minutes). |
| `NumberOfDays` | `int` | `0` | Away days. |

### `TimerPeriod`

| Field | Type |
|-------|------|
| `DayOfWeek` | `int` (0=Sun … 6=Sat) |
| `StartTime` | `str` (`"HH:MM:SS"`) |
| `EndTime` | `str` (`"HH:MM:SS"`) |
| `Temperature` | `float` |

### `TimerModeSettings`

| Field | Type |
|-------|------|
| `HubId` | `str` |
| `ApplianceId` | `str` |
| `TimerMode` | `int` (see `TimerMode` enum) |
| `TimerPeriods` | `list[TimerPeriod]` |

### `TimerMode` (IntEnum)

| Value | Name |
|-------|------|
| `0` | `OFF` |
| `1` | `MANUAL` |
| `2` | `TIMER` |
| `3` | `FROST_PROTECTION` |

### `ApplianceModeFlag` (IntFlag)

| Value | Name |
|-------|------|
| `0` | `NONE` |
| `16` | `BOOST` |
| `32` | `AWAY` |

### `UserContext`

| Field | Type |
|-------|------|
| `Id` | `str` |
| `EmailAddress` | `str \| None` |
| `Name` | `str \| None` |

### `ProductModel`

Product catalogue entry with provisioning metadata (see `models.py`).

### `TsiEnergyReport`

| Field | Type |
|-------|------|
| `HubId` | `str` |
| `ApplianceTelemetryData` | `dict[str, list]` — raw per-appliance time-series. |

---

## Telemetry helpers

```python
from dimplex_controller import parse_telemetry_points, summarise_energy
from dimplex_controller import VALUE_KEY_T1, VALUE_KEY_T2
```

### `parse_telemetry_points(points, value_keys=VALUE_KEY_T1)`

Normalise firmware-varying telemetry into `list[tuple[datetime | None, float]]`.

### `filter_telemetry_points(points, start, end)`

Filter parsed points to a time window.

### `summarise_energy(points, mode="daily", now=..., tz=...)`

Aggregate to daily/lifetime totals. Returns an `EnergySummary` with `total_kwh`, `point_count`, `start`, `end`.

---

## Exceptions

| Exception | Description |
|-----------|-------------|
| `DimplexError` | Base for all library errors. |
| `DimplexAuthError` | Auth/token errors. Has `code`, `reauth_required`, `transient`, `status`, `details`. |
| `DimplexAuthInvalidGrantError` | Refresh token / code rejected (subclass of `DimplexAuthError`). |
| `DimplexAuthInvalidCredentialsError` | Email/password rejected by B2C. |
| `DimplexAuthParseError` | Could not parse B2C HTML. |
| `DimplexAuthTransientError` | Temporary auth infra failure (retry may help). |
| `DimplexApiError` | API returned non-success. Attributes: `status`, `message`. |
| `DimplexConnectionError` | Network failures (DNS, connection, timeout). |

### `classify_oauth_token_error(status, body)`

Map a token-endpoint failure to the structured auth hierarchy.

### `oauth_error_summary(body)`

Human-readable summary of an OAuth error body (safe for logs).
