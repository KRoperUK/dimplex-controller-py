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

Mode writes go through `POST /RemoteControl/SetApplianceMode` with one
`EApplianceModes` bit targeted at a time. See
[`decompiled-api-reference.md`](decompiled-api-reference.md) for the ground-truth
payload shapes.

| Method | Returns | Description |
|--------|---------|-------------|
| `set_appliance_setpoint_temperature(hub_id, appliance_ids, temperature)` | `None` | **Preferred setpoint path.** Dedicated endpoint; applies immediately and leaves the schedule untouched. |
| `set_boost(hub_id, appliance_ids, *, temperature=21.0, duration_minutes=60, enable=True)` | `None` | Timed Boost (`ApplianceModes=2`, `Time` = minutes). |
| `clear_boost(hub_id, appliance_ids, *, temperature=21.0)` | `None` | Disable Boost (convenience wrapper). |
| `set_away(hub_id, appliance_ids, *, temperature=7.0, enable=True, until=None, number_of_days=0)` | `None` | Away setback (`ApplianceModes=4`). `until` is the away-until datetime sent in `Date`; 7–30 °C, defaults to the 7 °C anti-freeze floor. |
| `clear_away(hub_id, appliance_ids, *, temperature=7.0)` | `None` | Disable Away (convenience wrapper). |
| `set_frost_protect(hub_id, appliance_ids, *, enable=True, temperature=7.0)` | `None` | Engage/clear frost protection (`ApplianceModes=32`). |
| `turn_off(hub_id, appliance_ids)` | `None` | Turn off the way the app does — frost protection at 7 °C. |
| `set_advance(hub_id, appliance_ids, *, enable=True, temperature=None)` | `None` | Advance to the next schedule period (`ApplianceModes=16`); sends the `255` sentinel when no temperature is given. |
| `set_manual(hub_id, appliance_ids, *, temperature, enable=True)` | `None` | Hold a manual setpoint (`ApplianceModes=128`). |
| `set_eco_mode(hub_id, appliance_ids, *, temperature, enable=True)` | `None` | Engage Eco mode (`ApplianceModes=64`). Not the same as `set_eco_start`. |
| `set_setback_temperature(hub_id, appliance_ids, *, temperature, status=SetbackStatus.ACTIVE)` | `None` | Write the setback temperature. **Untested.** |
| `set_eco_start(hub_id, appliance_ids, enable)` | `None` | Toggle the EcoStart pre-heat setting. |
| `set_open_window_detection(hub_id, appliance_ids, enable)` | `None` | Toggle Open Window Detection. |
| `set_period_setpoint(hub_id, appliance_id, *, day_of_week, start_time, temperature, end_time=None)` | `TimerModeSettings` | Update one timer period's setpoint without clobbering others. |
| `update_period(hub_id, appliance_id, period, *, match_start_time=None)` | `TimerModeSettings` | Replace one timer period matched by day + start time. |
| `copy_schedule_to_appliances(hub_id, from_appliance_id, appliance_ids, *, timer_mode=0)` | `None` | Copy one appliance's schedule onto others. |
| `set_mode(hub_id, appliance_id, mode)` | `None` | Rewrite `TimerMode` via the schedule editor. **Quantum returns HTTP 403** — use `turn_off` / `set_appliance_setpoint_temperature` instead. |
| `set_target_temperature(hub_id, appliance_id, temp)` | `None` | **Deprecated.** Rewrites all period setpoints via `SetTimerMode`; 403 on Quantum. |
| `set_mode_flag(hub_id, appliance_ids, mode, *, enable=True, temperature=None, minutes=0, until=None, ...)` | `None` | Low-level: engage/clear any single mode bit. |
| `set_appliance_mode(hub_id, appliance_ids, mode_settings)` | `None` | Lowest-level: send a full `ApplianceModeSettings` payload. |

### Methods — hot-water cylinders

All confirmed present in APK 2.26.0 but **untested** — no cylinder hardware is
available. `heat_pump=True` targets an ASHW (heat-pump) cylinder.

| Method | Description |
|--------|-------------|
| `set_hot_water_mode(hub_id, appliance_ids, mode, *, enable=True, temperature=None, heat_pump=False)` | Set a cylinder mode. |
| `set_hot_water_boost_temperature(hub_id, appliance_ids, temperature, *, enable=True)` | Cylinder Boost temperature. |
| `set_hot_water_normal_temperature(hub_id, appliance_ids, temperature, *, enable=True)` | Cylinder Normal temperature. |
| `set_hot_water_hygiene(hub_id, appliance_ids, *, temperature, frequency=HygieneFrequency.WEEKLY, enable=True, heat_pump=False)` | Anti-legionella cycle. |
| `get_heat_pump_hot_water_schedule(hub_id, appliance_id)` | Read an ASHW cylinder's schedule. |
| `set_heat_pump_hot_water_schedule(settings)` | Write an ASHW cylinder's schedule periods. |

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

Helper properties:

| Property | Returns | Description |
|----------|---------|-------------|
| `mode_flags` | `ApplianceModeFlag` | `ApplianceModes` as a typed flag set. |
| `has_mode(mode)` | `bool` | True when every bit in `mode` is engaged. |
| `active_modes` | `list[str]` | Names of the engaged mode bits. |
| `active_setpoint_temperature` | `float \| None` | `ActiveSetPointTemperature` with the `255` "no setpoint" sentinel removed. |
| `is_boost_active` | `bool` | Boost bit engaged. |
| `is_away_active` | `bool` | Away bit engaged. |
| `is_frost_protect_active` | `bool` | Frost protection engaged (the app's "off"). |
| `is_advance_active` | `bool` | Advanced to the next schedule period. |
| `is_timer_active` | `bool` | Following the schedule. |
| `is_manual_active` | `bool` | Held at a manual setpoint. |
| `is_eco_active` | `bool` | Eco *mode* bit engaged (≠ `EcoStartEnabled`). |

### `ApplianceModeSettings`

Payload for `set_appliance_mode` / every `SetApplianceMode*` endpoint.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ApplianceModes` | `int` | — | Which mode the write targets (see `ApplianceModeFlag`). |
| `Status` | `int` | — | `1` engages the mode, `0` clears it. |
| `Temperature` | `int` | `23` | Target °C. Wire type is a short, so floats are rounded to whole degrees. |
| `Time` | `int` | `0` | Boost duration in minutes. |
| `Date` | `str` | `"0001-01-01T00:00:00"` | Away "away until" datetime — how the app expresses Away duration. |
| `StatusTwo` | `int` | `0` | Schedule profile (see `ScheduleProfile`). |
| `NumberOfDays` | `int` | `0` | Legacy Away duration; prefer `Date`. |
| `Frequency` | `int` | `0` | Hot-water hygiene cycle (see `HygieneFrequency`). |

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

Values for `TimerModeSettings.TimerMode`.

| Value | Name |
|-------|------|
| `0` | `USER_TIMER` |
| `1` | `MANUAL` |
| `2` | `FROST_PROTECTION` |
| `3` | `OFF` |

### `ApplianceModeFlag` (IntFlag)

`EApplianceModes`, as decompiled from Dimplex Control APK 2.26.0.

| Value | Name | Notes |
|-------|------|-------|
| `0` | `NONE` | |
| `1` | `TIMER_MODE` | Following the schedule. |
| `2` | `BOOST` | `Time` = duration in minutes. |
| `4` | `AWAY` | `Date` = away-until; temperature 7–30, defaults 7. |
| `8` | `HOLIDAY` | |
| `16` | `ADVANCE` | Jump to the next period; `255` on Quantum / Storage Heater. |
| `32` | `FROST_PROTECT` | Fixed 7 °C — how the app turns a heater off. |
| `64` | `ECO` | |
| `128` | `MANUAL` | |
| `256` | `HYGIENE` | Hot-water cylinders. |
| `512` | `STANDALONE` | |
| `1024` | `SAFE_MODE` | |
| `2048` | `SHUTDOWN` | |
| `4096` | `COMMS` | |
| `8192` | `NORMAL` | Hot-water cylinders. |
| `16384` | `STANDBY` | |

> Releases before 0.13.0 defined `BOOST = 16` and `AWAY = 32` — those are in fact
> `ADVANCE` and `FROST_PROTECT`. Callers that hard-coded 16/32 were commanding
> the wrong mode.

### `ApplianceModeStatus` (IntEnum)

`ApplianceModeSettings.Status`: `INACTIVE = 0`, `ACTIVE = 1`.

### `SetbackStatus` (IntEnum)

`EStatus`, for `set_setback_temperature`: `INACTIVE = 0`, `ACTIVE = 1`,
`DSM_MODE = 2`, `LOCAL_FREQUENCY_CONTROL_ACTIVE = 3`.

### `ScheduleProfile` (IntEnum)

`EStatusTwo`: `USER_TIMER = 0`, `HOME_ALL_DAY = 1`, `OUT_ALL_DAY = 2`.

### `HygieneFrequency` (IntEnum)

`EFrequency`: `OFF = 0`, `DAILY = 1`, `WEEKLY = 7`, `MONTHLY = 28`.

### Temperature constants

```python
from dimplex_controller import (
    MODE_TEMP_MIN,             # 7.0  — mode carousel floor
    MODE_TEMP_MAX,             # 30.0 — mode carousel ceiling
    FROST_TEMPERATURE,         # 7.0
    DEFAULT_AWAY_TEMPERATURE,  # 7.0
    DEFAULT_BOOST_TEMPERATURE, # 21.0
    NO_SETPOINT_SENTINEL,      # 255  — "following the schedule"
    NULL_DATETIME,             # "0001-01-01T00:00:00"
)
```

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
