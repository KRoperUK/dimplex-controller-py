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
    DEFAULT_AWAY_TEMPERATURE,
    DEFAULT_BOOST_TEMPERATURE,
    FROST_TEMPERATURE,
    HEADER_APP_NAME,
    HEADER_APP_VERSION,
    HEADER_DEVICE_MANUFACTURER,
    HEADER_DEVICE_MODEL,
    HEADER_DEVICE_OS,
    HEADER_DEVICE_VERSION,
    HEADER_USER_AGENT,
    HTTP_OK,
    NO_SETPOINT_SENTINEL,
    NULL_DATETIME,
)
from .exceptions import DimplexApiError, DimplexConnectionError
from .models import (
    Appliance,
    ApplianceModeFlag,
    ApplianceModeSettings,
    ApplianceModeStatus,
    ApplianceStatus,
    Hub,
    HygieneFrequency,
    ProductModel,
    SetbackStatus,
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


def _iso_away_until(until: datetime | str | None) -> str:
    """Normalise an Away "away until" value into the wire ``Date`` format.

    The cloud expects a naive .NET ``DateTime`` string, so aware datetimes are
    converted to UTC and the offset dropped. ``None`` yields the .NET
    ``default(DateTime)`` sentinel the app sends when no date applies.
    """
    if until is None:
        return NULL_DATETIME
    if isinstance(until, str):
        return until
    if until.tzinfo is not None:
        until = until.astimezone(timezone.utc).replace(tzinfo=None)
    return until.replace(microsecond=0).isoformat()


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
        return Zone.model_validate(data)  # type: ignore[no-any-return]

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
        return UserContext.model_validate(data)  # type: ignore[no-any-return]

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
        return TimerModeSettings.model_validate(data)  # type: ignore[no-any-return]

    async def get_schedule(self, hub_id: str, appliance_id: str) -> TimerModeSettings:
        """Return the current timer mode + periods (alias of :meth:`get_appliance_features`)."""
        return await self.get_appliance_features(hub_id, appliance_id)

    async def _write_timer_settings(self, settings: TimerModeSettings) -> TimerModeSettings:
        """POST a full :class:`TimerModeSettings` payload and return it."""
        payload = {"TimerModeSettings": settings.model_dump(mode="json")}
        await self._request("POST", "/RemoteControl/SetTimerMode", json=payload)
        return settings

    async def set_mode(self, hub_id: str, appliance_id: str, mode: int | TimerMode) -> None:
        """Set the timer / operation mode by rewriting ``TimerModeSettings``.

        See :class:`~dimplex_controller.models.TimerMode` for known values.

        .. warning::
           ``SetTimerMode`` is the *schedule editor* endpoint. Quantum (and
           likely other storage models) reject using it to change mode with
           **HTTP 403**. To turn a heater off use :meth:`set_frost_protect` /
           :meth:`turn_off`; to change the setpoint use
           :meth:`set_appliance_setpoint_temperature`.
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
        """Set the target temperature by **rewriting the timer schedule**.

        .. deprecated:: 0.13.0
           Prefer :meth:`set_appliance_setpoint_temperature`, the dedicated
           endpoint the app uses. It applies immediately, does not touch the
           stored schedule, and works on Quantum — which rejects the
           ``SetTimerMode`` write this method performs with **HTTP 403**
           (dimplex-controller-hass#149).

        Retained for models where rewriting the schedule genuinely is the
        intended mechanism. It:

        1. Loads the current timer configuration.
        2. Updates every period's temperature (preserving day/time windows).
        3. If no periods exist (common for some Quantum configs), installs a
           full-week 00:00–23:59 schedule at the requested temperature in
           manual mode so the cloud has a concrete setpoint to apply.

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
        """POST ``ApplianceModeSettings`` to ``/RemoteControl/SetApplianceMode``.

        This is the low-level escape hatch. Prefer the typed helpers
        (:meth:`set_boost`, :meth:`set_away`, :meth:`set_frost_protect`,
        :meth:`set_advance`, :meth:`set_manual`, :meth:`set_eco_mode`) which
        fill the correct fields for each mode.
        """
        payload = {
            "Settings": mode_settings.model_dump(mode="json"),
            "HubId": hub_id,
            "ApplianceIds": appliance_ids,
        }
        await self._request("POST", "/RemoteControl/SetApplianceMode", json=payload)

    async def set_mode_flag(
        self,
        hub_id: str,
        appliance_ids: list[str],
        mode: ApplianceModeFlag,
        *,
        enable: bool = True,
        temperature: float | None = None,
        minutes: int = 0,
        until: datetime | str | None = None,
        number_of_days: int = 0,
        frequency: int | HygieneFrequency = 0,
        endpoint: str = "/RemoteControl/SetApplianceMode",
    ) -> None:
        """Engage or clear a single :class:`ApplianceModeFlag`.

        Mirrors how the app builds ``ApplianceModeSettings``: only the fields
        relevant to ``mode`` are populated, and a clear (``enable=False``)
        sends ``Status=0`` with the ancillary fields zeroed.
        """
        settings = ApplianceModeSettings(
            ApplianceModes=int(mode),
            Status=int(ApplianceModeStatus.ACTIVE if enable else ApplianceModeStatus.INACTIVE),
            Temperature=int(round(temperature)) if temperature is not None else 0,
            Time=int(minutes) if enable else 0,
            Date=_iso_away_until(until) if enable else NULL_DATETIME,
            NumberOfDays=int(number_of_days) if enable else 0,
            Frequency=int(frequency) if enable else 0,
        )
        payload = {
            "Settings": settings.model_dump(mode="json"),
            "HubId": hub_id,
            "ApplianceIds": appliance_ids,
        }
        await self._request("POST", endpoint, json=payload)

    async def set_boost(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float = DEFAULT_BOOST_TEMPERATURE,
        duration_minutes: int = DEFAULT_BOOST_MINUTES,
        enable: bool = True,
    ) -> None:
        """Enable or disable timed Boost for one or more appliances.

        Sends ``ApplianceModes=2`` (:attr:`~dimplex_controller.ApplianceModeFlag.BOOST`)
        with ``Status=1`` (on) / ``Status=0`` (off); ``Time`` carries the boost
        duration in minutes and ``Temperature`` the boost target (7–30 °C).

        .. versionchanged:: 0.13.0
           Previously sent ``ApplianceModes=16``, which is **Advance** — the
           appliance advanced its schedule instead of boosting, and the
           requested duration was discarded.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.BOOST,
            enable=enable,
            temperature=temperature,
            minutes=int(duration_minutes) if enable else 0,
        )

    async def clear_boost(
        self, hub_id: str, appliance_ids: list[str], *, temperature: float = DEFAULT_BOOST_TEMPERATURE
    ) -> None:
        """Disable Boost for the given appliances."""
        await self.set_boost(hub_id, appliance_ids, temperature=temperature, duration_minutes=0, enable=False)

    async def set_away(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float = DEFAULT_AWAY_TEMPERATURE,
        enable: bool = True,
        until: datetime | str | None = None,
        number_of_days: int = 0,
    ) -> None:
        """Enable or disable Away mode.

        Sends ``ApplianceModes=4`` (:attr:`~dimplex_controller.ApplianceModeFlag.AWAY`).
        Away is a *settable* setback: the app offers 7–30 °C and defaults to the
        7 °C anti-freeze floor, so a low ``temperature`` is the normal case
        rather than a bug.

        ``until`` is the "away until" datetime the app sends in ``Date``. Pass a
        :class:`~datetime.datetime` or an ISO-8601 string. ``number_of_days`` is
        retained for backwards compatibility and, when ``until`` is omitted, is
        converted into an equivalent ``Date``.

        .. versionchanged:: 0.13.0
           Previously sent ``ApplianceModes=32``, which is **FrostProtect** —
           the appliance was pinned to the fixed 7 °C frost setpoint and the
           requested away target was ignored (dimplex-controller-hass#163).
           Away duration now travels in ``Date`` as the app does, not only in
           ``NumberOfDays``.
        """
        days = int(number_of_days)
        if until is None and days > 0:
            until = datetime.now(timezone.utc) + timedelta(days=days)
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.AWAY,
            enable=enable,
            temperature=temperature,
            until=until,
            number_of_days=days,
        )

    async def clear_away(
        self, hub_id: str, appliance_ids: list[str], *, temperature: float = DEFAULT_AWAY_TEMPERATURE
    ) -> None:
        """Disable Away mode for the given appliances."""
        await self.set_away(hub_id, appliance_ids, temperature=temperature, enable=False)

    async def set_frost_protect(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        enable: bool = True,
        temperature: float = FROST_TEMPERATURE,
    ) -> None:
        """Engage or clear frost protection (``ApplianceModes=32``, temp 7 °C).

        This is how the official app turns a heater **off**: there is no "off"
        mode, only the anti-freeze floor. Use this instead of writing
        ``TimerMode`` — Quantum rejects ``SetTimerMode`` with HTTP 403.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.FROST_PROTECT,
            enable=enable,
            temperature=temperature,
        )

    async def turn_off(self, hub_id: str, appliance_ids: list[str]) -> None:
        """Turn appliances off the way the app does — frost protection at 7 °C."""
        await self.set_frost_protect(hub_id, appliance_ids, enable=True)

    async def set_advance(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        enable: bool = True,
        temperature: float | None = None,
    ) -> None:
        """Advance to the next schedule period (``ApplianceModes=16``).

        ``temperature`` is the current/next period's setpoint. Quantum and
        Storage Heater models with no setback expect the ``255`` "no explicit
        setpoint" sentinel, which is the default when ``temperature`` is
        omitted.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.ADVANCE,
            enable=enable,
            temperature=NO_SETPOINT_SENTINEL if temperature is None else temperature,
        )

    async def set_manual(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        enable: bool = True,
    ) -> None:
        """Hold a manual setpoint (``ApplianceModes=128``, 7–30 °C)."""
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.MANUAL,
            enable=enable,
            temperature=temperature,
        )

    async def set_eco_mode(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        enable: bool = True,
    ) -> None:
        """Engage Eco mode (``ApplianceModes=64``).

        Not the same as :meth:`set_eco_start`, which toggles the EcoStart
        pre-heat *setting* rather than engaging a mode.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.ECO,
            enable=enable,
            temperature=temperature,
        )

    async def set_appliance_setpoint_temperature(
        self, hub_id: str, appliance_ids: list[str], temperature: float
    ) -> None:
        """Set the active setpoint via ``/RemoteControl/SetApplianceSetpointTemperature``.

        This is the dedicated, non-destructive setpoint endpoint the app uses:
        it applies a target immediately and leaves the stored schedule periods
        untouched. Prefer it over :meth:`set_target_temperature`, which rewrites
        the schedule and is rejected with HTTP 403 on Quantum.

        ``Temperature`` is a wire ``byte``, so the value is rounded to whole
        degrees.
        """
        payload = {
            "HubId": hub_id,
            "ApplianceIds": appliance_ids,
            "Temperature": int(round(temperature)),
        }
        await self._request("POST", "/RemoteControl/SetApplianceSetpointTemperature", json=payload)

    async def set_setback_temperature(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        status: int | SetbackStatus = SetbackStatus.ACTIVE,
    ) -> None:
        """Write the setback temperature (``/RemoteControl/SetSetbackTemperature``).

        ``status`` is an :class:`~dimplex_controller.SetbackStatus` byte —
        ``ACTIVE``/``INACTIVE`` for a plain setback, with ``DSM_MODE`` and
        ``LOCAL_FREQUENCY_CONTROL_ACTIVE`` reserved for demand-side-management
        use.

        Confirmed present in APK 2.26.0 but **not yet validated on live
        hardware**.
        """
        payload = {
            "HubId": hub_id,
            "ApplianceIds": appliance_ids,
            "Status": int(status),
            "Temperature": int(round(temperature)),
        }
        await self._request("POST", "/RemoteControl/SetSetbackTemperature", json=payload)

    async def set_eco_start(self, hub_id: str, appliance_ids: list[str], enable: bool) -> None:
        """Enable/Disable EcoStart."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetEcoStart", json=payload)

    async def set_open_window_detection(self, hub_id: str, appliance_ids: list[str], enable: bool) -> None:
        """Enable/Disable Open Window Detection."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetOpenWindowDetection", json=payload)

    # ------------------------------------------------------------------
    # Hot-water cylinders (``WaterHeater`` / heat-pump ``ASHW Cylinder``)
    #
    # These endpoints are confirmed present in Dimplex Control APK 2.26.0 but
    # are **untested against live hardware** — the maintainer owns no cylinder.
    # Treat behaviour as provisional and please report findings upstream.
    # ------------------------------------------------------------------

    async def set_hot_water_mode(
        self,
        hub_id: str,
        appliance_ids: list[str],
        mode: ApplianceModeFlag,
        *,
        enable: bool = True,
        temperature: float | None = None,
        heat_pump: bool = False,
    ) -> None:
        """Set a cylinder mode via ``SetApplianceModeHwc`` / ``…HeatPumpHwc``.

        ``heat_pump=True`` targets an ASHW (heat-pump) cylinder.

        .. warning:: Untested — APK-confirmed only.
        """
        endpoint = "/RemoteControl/SetApplianceModeHeatPumpHwc" if heat_pump else "/RemoteControl/SetApplianceModeHwc"
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            mode,
            enable=enable,
            temperature=temperature,
            endpoint=endpoint,
        )

    async def set_hot_water_boost_temperature(
        self, hub_id: str, appliance_ids: list[str], temperature: float, *, enable: bool = True
    ) -> None:
        """Set the cylinder Boost temperature (``SetBoostTemperatureHwc``).

        .. warning:: Untested — APK-confirmed only.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.BOOST,
            enable=enable,
            temperature=temperature,
            endpoint="/RemoteControl/SetBoostTemperatureHwc",
        )

    async def set_hot_water_normal_temperature(
        self, hub_id: str, appliance_ids: list[str], temperature: float, *, enable: bool = True
    ) -> None:
        """Set the cylinder Normal temperature (``SetNormalTemperatureHwc``).

        .. warning:: Untested — APK-confirmed only.
        """
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.NORMAL,
            enable=enable,
            temperature=temperature,
            endpoint="/RemoteControl/SetNormalTemperatureHwc",
        )

    async def set_hot_water_hygiene(
        self,
        hub_id: str,
        appliance_ids: list[str],
        *,
        temperature: float,
        frequency: int | HygieneFrequency = HygieneFrequency.WEEKLY,
        enable: bool = True,
        heat_pump: bool = False,
    ) -> None:
        """Configure the anti-legionella hygiene cycle.

        ``frequency`` is a :class:`~dimplex_controller.HygieneFrequency`
        (``OFF``/``DAILY``/``WEEKLY``/``MONTHLY``).

        .. warning:: Untested — APK-confirmed only.
        """
        endpoint = (
            "/RemoteControl/SetHygieneSettingsHeatPumpHwc" if heat_pump else "/RemoteControl/SetHygieneSettingsHwc"
        )
        await self.set_mode_flag(
            hub_id,
            appliance_ids,
            ApplianceModeFlag.HYGIENE,
            enable=enable,
            temperature=temperature,
            frequency=frequency,
            endpoint=endpoint,
        )

    async def get_heat_pump_hot_water_schedule(self, hub_id: str, appliance_id: str) -> TimerModeSettings:
        """Read an ASHW cylinder's schedule.

        .. warning:: Untested — APK-confirmed only.
        """
        payload = {"HubId": hub_id, "ApplianceId": appliance_id}
        data = await self._request(
            "POST",
            "/RemoteControl/ApiGetTimerModeDetailsForHeatPumpHwcAppliance",
            json=payload,
        )
        return TimerModeSettings.model_validate(data)  # type: ignore[no-any-return]

    async def set_heat_pump_hot_water_schedule(self, settings: TimerModeSettings) -> TimerModeSettings:
        """Write an ASHW cylinder's schedule periods.

        .. warning:: Untested — APK-confirmed only.
        """
        payload = {"TimerModeSettings": settings.model_dump(mode="json")}
        await self._request("POST", "/RemoteControl/UpdateHeatPumpHwcSchedulePeriods", json=payload)
        return settings

    async def copy_schedule_to_appliances(
        self,
        hub_id: str,
        from_appliance_id: str,
        appliance_ids: list[str],
        *,
        timer_mode: int | TimerMode = 0,
    ) -> None:
        """Copy one appliance's schedule onto others (``CopyScheduleToAppliances``)."""
        payload = {
            "HubId": hub_id,
            "FromApplianceId": from_appliance_id,
            "ApplianceIds": appliance_ids,
            "TimerMode": int(timer_mode),
        }
        await self._request("POST", "/RemoteControl/CopyScheduleToAppliances", json=payload)

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
