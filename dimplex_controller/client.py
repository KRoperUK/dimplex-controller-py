from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from .auth import AuthManager, TokenBundle, TokenListener
from .capabilities import ApplianceCapabilities, capabilities_for
from .const import (
    BASE_URL,
    HEADER_APP_NAME,
    HEADER_APP_VERSION,
    HEADER_DEVICE_MANUFACTURER,
    HEADER_DEVICE_MODEL,
    HEADER_DEVICE_OS,
    HEADER_DEVICE_VERSION,
    HEADER_USER_AGENT,
    HTTP_OK,
)
from .exceptions import DimplexApiError, DimplexConnectionError
from .models import (
    Appliance,
    ApplianceModeFlag,
    ApplianceModeSettings,
    ApplianceStatus,
    Hub,
    ProductModel,
    TimerMode,
    TimerModeSettings,
    TimerPeriod,
    TsiEnergyReport,
    UserContext,
    Zone,
)

_LOGGER = logging.getLogger(__name__)

# Default lookback when the caller does not pin a start date. The energy
# endpoint is paginated server-side; with IncludePreviousPeriod the cloud
# often returns the full history regardless, so this mainly bounds the
# "current window" half of the request.
DEFAULT_TSI_REPORT_DAYS = 30
DEFAULT_TSI_INTERVAL = "01:00:00"

# Default boost length when the caller does not specify one (minutes).
DEFAULT_BOOST_MINUTES = 60

# HTTP retry policy (see ``DimplexControl`` constructor).
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 0.5
DEFAULT_RETRY_MAX_DELAY = 8.0
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Default total request timeout in seconds. Without this aiohttp falls back to a
# 5-minute default, which can hang a caller (e.g. a Home Assistant coordinator
# poll) on a stalled connection. Callers may override per-client.
DEFAULT_TIMEOUT = 30.0


def _coerce_timeout(timeout: float | aiohttp.ClientTimeout | None) -> aiohttp.ClientTimeout | None:
    """Normalise a timeout value into an :class:`aiohttp.ClientTimeout`.

    ``None`` disables the client-level timeout (aiohttp defaults apply); a
    number is treated as the total request timeout in seconds.
    """
    if timeout is None:
        return None
    if isinstance(timeout, aiohttp.ClientTimeout):
        return timeout
    return aiohttp.ClientTimeout(total=float(timeout))


def _iso_utc_days_ago(days: int) -> str:
    """Return an ISO-8601 UTC timestamp ``days`` before now (no microseconds)."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class DimplexControl:
    """Main client for Dimplex Control API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: str | None = None,
        access_token: str | None = None,
        expires_at: float = 0,
        *,
        token_bundle: TokenBundle | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY,
        retry_non_idempotent: bool = False,
        timeout: float | aiohttp.ClientTimeout | None = DEFAULT_TIMEOUT,
        on_token_update: TokenListener | None = None,
    ):
        """Initialize the client.

        Prefer ``token_bundle`` for new code. The individual token kwargs remain
        supported for backwards compatibility.

        Retry policy (centralised on ``_request``):

        * **GET** (and other safe methods): retry on connection errors and
          HTTP 429/5xx with exponential backoff + jitter; honour ``Retry-After``
          when present.
        * **POST/PUT/PATCH/DELETE**: no retries by default (non-idempotent
          control calls). Set ``retry_non_idempotent=True`` to apply the same
          policy (use with care).
        * ``max_retries`` is the number of *retries* after the first attempt
          (0 disables retries).

        ``timeout`` bounds every request (API and auth). Pass a number for a
        total timeout in seconds (default 30s), an :class:`aiohttp.ClientTimeout`
        for fine-grained control, or ``None`` to fall back to aiohttp defaults.
        A timed-out request is surfaced as :class:`DimplexConnectionError` and,
        for retryable methods, retried like any other connection error.

        ``on_token_update`` is an optional callback (sync or async) invoked with
        a :class:`TokenBundle` whenever tokens are refreshed or exchanged. Use
        it to persist tokens reactively (e.g. write to a config-entry store)
        rather than polling :meth:`export_tokens` after every request.
        """
        if token_bundle is not None:
            token_data: dict[str, Any] | TokenBundle = token_bundle
        else:
            token_data = {}
            if refresh_token:
                token_data["refresh_token"] = refresh_token
            if access_token:
                token_data["access_token"] = access_token
            if expires_at:
                token_data["expires_at"] = expires_at

        self._session = session
        self._timeout = _coerce_timeout(timeout)
        self.auth = AuthManager(session, token_data, timeout=self._timeout, on_token_update=on_token_update)
        self._max_retries = max(0, int(max_retries))
        self._retry_base_delay = float(retry_base_delay)
        self._retry_max_delay = float(retry_max_delay)
        self._retry_non_idempotent = bool(retry_non_idempotent)

    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self.auth.is_authenticated

    def export_tokens(self) -> TokenBundle:
        """Return the current auth token snapshot."""
        return self.auth.export_tokens()

    def apply_tokens(self, bundle: TokenBundle | dict[str, Any]) -> None:
        """Replace in-memory auth tokens."""
        self.auth.apply_tokens(bundle)

    def _should_retry(self, method: str) -> bool:
        upper = method.upper()
        if upper in {"GET", "HEAD", "OPTIONS"}:
            return True
        return self._retry_non_idempotent

    def _backoff_seconds(self, attempt: int, retry_after: float | None = None) -> float:
        """Compute delay before the next attempt (``attempt`` is 0-based)."""
        if retry_after is not None and retry_after >= 0:
            return min(retry_after, self._retry_max_delay)
        # Exponential backoff with full jitter: U(0, min(max, base * 2^attempt))
        ceiling = min(self._retry_max_delay, self._retry_base_delay * (2**attempt))
        return random.uniform(0, ceiling)

    @staticmethod
    def _parse_retry_after(header_value: str | None) -> float | None:
        if not header_value:
            return None
        try:
            return max(0.0, float(header_value.strip()))
        except ValueError:
            return None

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Make an authenticated request with optional retry/backoff."""
        token = await self.auth.get_access_token()
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {token}",
                "app_name": HEADER_APP_NAME,
                "app_version": HEADER_APP_VERSION,
                "app_device_os": HEADER_DEVICE_OS,
                "device_version": HEADER_DEVICE_VERSION,
                "device_manufacturer": HEADER_DEVICE_MANUFACTURER,
                "device_model": HEADER_DEVICE_MODEL,
                "User-Agent": HEADER_USER_AGENT,
                "api_version": "1.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/json",
            }
        )

        url = f"{BASE_URL}{endpoint}"
        if self._timeout is not None and "timeout" not in kwargs:
            kwargs["timeout"] = self._timeout
        allow_retry = self._should_retry(method)
        attempts = self._max_retries + 1 if allow_retry else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                    if resp.status == HTTP_OK:
                        return await self._decode_ok_body(resp)

                    text = await resp.text()
                    retry_after = self._parse_retry_after(resp.headers.get("Retry-After"))
                    if allow_retry and resp.status in _RETRYABLE_STATUS and attempt + 1 < attempts:
                        delay = self._backoff_seconds(attempt, retry_after)
                        _LOGGER.warning(
                            "API %s %s failed with %s; retry %s/%s in %.2fs",
                            method,
                            endpoint,
                            resp.status,
                            attempt + 1,
                            attempts - 1,
                            delay,
                        )
                        last_error = DimplexApiError(resp.status, text)
                        await asyncio.sleep(delay)
                        continue

                    _LOGGER.error("API request failed: %s - %s", resp.status, text)
                    raise DimplexApiError(resp.status, text)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if allow_retry and attempt + 1 < attempts:
                    delay = self._backoff_seconds(attempt)
                    _LOGGER.warning(
                        "Connection error on %s %s; retry %s/%s in %.2fs: %s",
                        method,
                        endpoint,
                        attempt + 1,
                        attempts - 1,
                        delay,
                        e,
                    )
                    last_error = DimplexConnectionError(f"Connection error: {e}")
                    await asyncio.sleep(delay)
                    continue
                _LOGGER.error("Connection error during API request: %s", e)
                raise DimplexConnectionError(f"Connection error: {e}") from e

        if isinstance(last_error, DimplexApiError):
            raise last_error
        if isinstance(last_error, DimplexConnectionError):
            raise last_error
        raise DimplexConnectionError("Request failed after retries")

    @staticmethod
    async def _decode_ok_body(resp: aiohttp.ClientResponse) -> Any:
        """Decode a 2xx JSON body, tolerating empty responses.

        Some Dimplex control endpoints reply ``200 OK`` with an empty body (no
        ``Content-Length`` when chunked/compressed), so ``resp.content_length``
        alone is unreliable. Read the raw text and treat empty/whitespace as an
        empty object. A non-empty body that fails to parse is wrapped as a
        :class:`DimplexConnectionError` rather than escaping as a raw
        ``JSONDecodeError``.
        """
        text = await resp.text()
        if not text or not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise DimplexConnectionError(f"Invalid JSON in response: {exc}") from exc

    @staticmethod
    def capabilities_for(
        appliance: Appliance | None = None,
        *,
        status: ApplianceStatus | None = None,
        product: ProductModel | None = None,
    ) -> ApplianceCapabilities:
        """Return a capability matrix for an appliance (see :mod:`.capabilities`)."""
        return capabilities_for(appliance, status=status, product=product)

    async def get_hubs(self) -> list[Hub]:
        """Get all hubs for the user."""
        data = await self._request("GET", "/Hubs/GetUserHubs")
        return [Hub.model_validate(h) for h in data]

    async def get_hub_zones(self, hub_id: str) -> list[Zone]:
        """Get zones and appliances for a hub."""
        data = await self._request("GET", "/Zones/GetZonesAndAppliancesForHubId", params={"HubId": hub_id})
        return [Zone.model_validate(z) for z in data]

    async def get_zone(self, hub_id: str, zone_id: str) -> Zone:
        """Get details for a specific zone."""
        payload = {"HubId": hub_id, "ZoneId": zone_id}
        data = await self._request("POST", "/Zones/GetZone", json=payload)
        return Zone.model_validate(data)

    async def get_appliance_overview(self, hub_id: str, appliance_ids: list[str]) -> list[ApplianceStatus]:
        """Get status overview for specific appliances.

        When appliances are offline the cloud may return an empty list with
        HTTP 200. That is success — use :meth:`get_appliance_overview_map` if
        you need a stable id → status mapping.
        """
        payload = {"HubId": hub_id, "ApplianceIds": appliance_ids}
        data = await self._request("POST", "/RemoteControl/GetApplianceOverview", json=payload)
        if not data:
            return []
        return [ApplianceStatus.model_validate(item) for item in data]

    async def get_appliance_overview_map(
        self, hub_id: str, appliance_ids: list[str]
    ) -> dict[str, ApplianceStatus | None]:
        """Return a map of appliance id → status (``None`` when missing)."""
        overview = await self.get_appliance_overview(hub_id, appliance_ids)
        by_id = {status.ApplianceId: status for status in overview}
        return {appliance_id: by_id.get(appliance_id) for appliance_id in appliance_ids}

    async def get_user_context(self) -> UserContext:
        """Get user profile/context."""
        data = await self._request("GET", "/Identity/GetUserContext")
        return UserContext.model_validate(data)

    async def get_product_models(self) -> list[ProductModel]:
        """Return the cloud product catalogue (models + provisioning metadata).

        The catalogue is largely static; callers may cache the result.
        """
        data = await self._request("GET", "/Appliances/GetProductModels")
        if not data:
            return []
        return [ProductModel.model_validate(item) for item in data]

    async def get_appliance_features(self, hub_id: str, appliance_id: str) -> TimerModeSettings:
        """Get timer details (and mode) for an appliance."""
        payload = {
            "HubId": hub_id,
            "ApplianceId": appliance_id,
            "TimerMode": 0,  # Required field in request; value ignored on read
        }
        data = await self._request("POST", "/RemoteControl/GetTimerModeDetailsForAppliance", json=payload)
        return TimerModeSettings.model_validate(data)

    async def get_schedule(self, hub_id: str, appliance_id: str) -> TimerModeSettings:
        """Return the current timer mode + periods (alias of :meth:`get_appliance_features`)."""
        return await self.get_appliance_features(hub_id, appliance_id)

    async def _write_timer_settings(self, settings: TimerModeSettings) -> TimerModeSettings:
        """POST a full :class:`TimerModeSettings` payload and return it."""
        payload = {"TimerModeSettings": settings.model_dump(mode="json")}
        await self._request("POST", "/RemoteControl/SetTimerMode", json=payload)
        return settings

    async def set_mode(self, hub_id: str, appliance_id: str, mode: int | TimerMode) -> None:
        """Set the timer / operation mode.

        See :class:`~dimplex_controller.models.TimerMode` for known values.
        """
        current = await self.get_appliance_features(hub_id, appliance_id)
        current.TimerMode = int(mode)
        await self._write_timer_settings(current)

    async def set_period_setpoint(
        self,
        hub_id: str,
        appliance_id: str,
        *,
        day_of_week: int,
        start_time: str,
        temperature: float,
        end_time: str | None = None,
    ) -> TimerModeSettings:
        """Update one timer period's setpoint (and optional end) without clobbering others.

        Matches periods by ``DayOfWeek`` + ``StartTime``. Raises ``ValueError`` if
        no period matches. Prefer this over rewriting the whole schedule.
        """
        current = await self.get_appliance_features(hub_id, appliance_id)
        matched = False
        for period in current.TimerPeriods:
            if period.DayOfWeek == day_of_week and period.StartTime == start_time:
                period.Temperature = float(temperature)
                if end_time is not None:
                    period.EndTime = end_time
                matched = True
                break
        if not matched:
            raise ValueError(f"No timer period for day={day_of_week} start={start_time!r} on appliance {appliance_id}")
        return await self._write_timer_settings(current)

    async def update_period(
        self,
        hub_id: str,
        appliance_id: str,
        period: TimerPeriod,
        *,
        match_start_time: str | None = None,
    ) -> TimerModeSettings:
        """Replace a single period matched by day + start time (read-modify-write).

        ``match_start_time`` defaults to ``period.StartTime`` so callers can also
        change the period's start by passing the previous start string.
        """
        key_start = match_start_time if match_start_time is not None else period.StartTime
        current = await self.get_appliance_features(hub_id, appliance_id)
        for index, existing in enumerate(current.TimerPeriods):
            if existing.DayOfWeek == period.DayOfWeek and existing.StartTime == key_start:
                current.TimerPeriods[index] = period
                return await self._write_timer_settings(current)
        raise ValueError(f"No timer period for day={period.DayOfWeek} start={key_start!r} on appliance {appliance_id}")

    async def set_target_temperature(self, hub_id: str, appliance_id: str, temp: float) -> None:
        """Set the target / comfort temperature for an appliance.

        The Dimplex cloud stores setpoints on timer periods. This method:

        1. Loads the current timer configuration.
        2. Updates every period's temperature (preserving day/time windows).
        3. If no periods exist (common for some Quantum configs), installs a
           full-week 00:00–23:59 schedule at the requested temperature in
           manual mode so the cloud has a concrete setpoint to apply.

        This matches the reverse-engineered mobile-app approach of rewriting
        the active schedule rather than a dedicated "set temperature" RPC.

        **Note:** unlike :meth:`set_period_setpoint`, this updates *all* period
        temperatures (or installs a full-week schedule). Use the period helpers
        when only one window should change.
        """
        current = await self.get_appliance_features(hub_id, appliance_id)

        if current.TimerPeriods:
            for period in current.TimerPeriods:
                period.Temperature = float(temp)
        else:
            current.TimerMode = int(TimerMode.MANUAL)
            current.TimerPeriods = [
                TimerPeriod(
                    DayOfWeek=day,
                    StartTime="00:00:00",
                    EndTime="23:59:59",
                    Temperature=float(temp),
                )
                for day in range(7)
            ]

        await self._write_timer_settings(current)

    async def set_appliance_mode(
        self, hub_id: str, appliance_ids: list[str], mode_settings: ApplianceModeSettings
    ) -> None:
        """Set appliance mode (Boost, Away, etc.)."""
        payload = {
            "Settings": mode_settings.model_dump(mode="json"),
            "HubId": hub_id,
            "ApplianceIds": appliance_ids,
        }
        await self._request("POST", "/RemoteControl/SetApplianceMode", json=payload)

    async def set_boost(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        duration_minutes: int = DEFAULT_BOOST_MINUTES,
        enable: bool = True,
    ) -> None:
        """Enable or disable Boost for one or more appliances.

        The mobile app uses ``ApplianceModes=16`` with ``Status=1`` (on) /
        ``Status=0`` (off). ``Time`` carries the boost duration in minutes.
        """
        settings = ApplianceModeSettings(
            ApplianceModes=int(ApplianceModeFlag.BOOST),
            Status=1 if enable else 0,
            Temperature=float(temperature),
            Time=int(duration_minutes) if enable else 0,
        )
        await self.set_appliance_mode(hub_id, appliance_ids, settings)

    async def clear_boost(self, hub_id: str, appliance_ids: list[str], *, temperature: float = 21.0) -> None:
        """Disable Boost for the given appliances."""
        await self.set_boost(hub_id, appliance_ids, temperature=temperature, duration_minutes=0, enable=False)

    async def set_away(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        enable: bool = True,
        number_of_days: int = 0,
    ) -> None:
        """Enable or disable Away mode.

        Uses ``ApplianceModes=32`` (best-effort; confirmed via status-frame
        pairing with Away* fields). Prefer verifying on a live appliance
        after firmware updates.
        """
        settings = ApplianceModeSettings(
            ApplianceModes=int(ApplianceModeFlag.AWAY),
            Status=1 if enable else 0,
            Temperature=float(temperature),
            NumberOfDays=int(number_of_days) if enable else 0,
        )
        await self.set_appliance_mode(hub_id, appliance_ids, settings)

    async def clear_away(self, hub_id: str, appliance_ids: list[str], *, temperature: float = 16.0) -> None:
        """Disable Away mode for the given appliances."""
        await self.set_away(hub_id, appliance_ids, temperature=temperature, enable=False)

    async def set_eco_start(self, hub_id: str, appliance_ids: list[str], enable: bool) -> None:
        """Enable/Disable EcoStart."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetEcoStart", json=payload)

    async def set_open_window_detection(self, hub_id: str, appliance_ids: list[str], enable: bool) -> None:
        """Enable/Disable Open Window Detection."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetOpenWindowDetection", json=payload)

    async def get_tsi_energy_report(
        self,
        hub_id: str | None = None,
        report_type: int = 1,
        interval: str = DEFAULT_TSI_INTERVAL,
        start_date: str | None = None,
        end_date: str | None = None,
        include_previous_period: bool = True,
        days_back: int = DEFAULT_TSI_REPORT_DAYS,
    ) -> TsiEnergyReport:
        """Fetch the Time Series Insights energy report for a hub.

        Returns a :class:`~dimplex_controller.models.TsiEnergyReport`. Each
        per-appliance list is left as the raw payload — use
        :func:`dimplex_controller.telemetry.parse_telemetry_points` and
        :func:`dimplex_controller.telemetry.summarise_energy` to normalise
        and aggregate.

        When the hub has no metered appliances (e.g. non-QRAD heaters, or a
        quiet summer hub) the per-appliance lists come back empty; that is
        treated as success, not an error.

        Note: with ``include_previous_period=True`` (the default) the cloud
        frequently returns the **full available daily history**, not only the
        ``days_back`` window. Filter client-side for daily/lifetime totals.

        Points may include both ``T1`` (off-peak / cheaper) and ``T2``
        (peak / more expensive). Parse them with
        :data:`~dimplex_controller.telemetry.VALUE_KEY_T1` and
        :data:`~dimplex_controller.telemetry.VALUE_KEY_T2` separately —
        never sum T1+T2 into a single total.

        """
        if start_date is None:
            start_date = _iso_utc_days_ago(days_back)
        if end_date is None:
            end_date = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        payload: dict[str, Any] = {
            "TsiReportType": report_type,
            "Interval": interval,
            "StartDate": start_date,
            "EndDate": end_date,
            "IncludePreviousPeriod": include_previous_period,
        }
        if hub_id is not None:
            payload["HubId"] = hub_id

        data = await self._request("POST", "/Reports/GetTsiEnergyReportDataForHub", json=payload)
        return TsiEnergyReport(
            HubId=(hub_id or data.get("HubId", "")),
            ApplianceTelemetryData=data.get("ApplianceTelemetryData", {}) or {},
        )
