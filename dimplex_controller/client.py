import logging
from typing import Dict, List, Optional

import aiohttp

from .auth import AuthManager
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
    ApplianceModeSettings,
    ApplianceStatus,
    Hub,
    TimerModeSettings,
    UserContext,
    Zone,
)

_LOGGER = logging.getLogger(__name__)


class DimplexControl:
    """Main client for Dimplex Control API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
        expires_at: float = 0,
    ):
        """Initialize the client."""
        token_data = {}
        if refresh_token:
            token_data["refresh_token"] = refresh_token
        if access_token:
            token_data["access_token"] = access_token
        if expires_at:
            token_data["expires_at"] = expires_at

        self._session = session
        self.auth = AuthManager(session, token_data)

    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self.auth.is_authenticated

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make an authenticated request."""
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
        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status != HTTP_OK:
                    text = await resp.text()
                    _LOGGER.error("API request failed: %s - %s", resp.status, text)
                    raise DimplexApiError(resp.status, text)

                # API might return empty body for some calls
                if resp.content_length == 0:
                    return {}
                return await resp.json()
        except aiohttp.ClientError as e:
            _LOGGER.error("Connection error during API request: %s", e)
            raise DimplexConnectionError(f"Connection error: {e}") from e

    async def get_hubs(self) -> List[Hub]:
        """Get all hubs for the user."""
        data = await self._request("GET", "/Hubs/GetUserHubs")
        # Log analysis shows list of objects
        return [Hub(**h) for h in data]

    async def get_hub_zones(self, hub_id: str) -> List[Zone]:
        """Get zones and appliances for a hub."""
        data = await self._request("GET", "/Zones/GetZonesAndAppliancesForHubId", params={"HubId": hub_id})
        return [Zone(**z) for z in data]

    async def get_zone(self, hub_id: str, zone_id: str) -> Zone:
        """Get details for a specific zone."""
        payload = {"HubId": hub_id, "ZoneId": zone_id}
        data = await self._request("POST", "/Zones/GetZone", json=payload)
        return Zone(**data)

    async def get_appliance_overview(self, hub_id: str, appliance_ids: List[str]) -> List[ApplianceStatus]:
        """Get status overview for specific appliances."""
        payload = {"HubId": hub_id, "ApplianceIds": appliance_ids}
        data = await self._request("POST", "/RemoteControl/GetApplianceOverview", json=payload)
        return [ApplianceStatus(**item) for item in data]

    async def get_user_context(self) -> UserContext:
        """Get user profile/context."""
        data = await self._request("GET", "/Identity/GetUserContext")
        return UserContext(**data)

    async def get_appliance_features(self, hub_id: str, appliance_id: str) -> TimerModeSettings:
        """Get timer details (and mode) for an appliance."""
        # In the logs, this endpoint returns current mode and timer profiles
        payload = {
            "HubId": hub_id,
            "ApplianceId": appliance_id,
            "TimerMode": 0,  # Required field in request, value doesn't seem to matter for fetching?
        }
        data = await self._request("POST", "/RemoteControl/GetTimerModeDetailsForAppliance", json=payload)
        return TimerModeSettings(**data)

    async def set_mode(self, hub_id: str, appliance_id: str, mode: int) -> None:
        """Set the operation mode.

        Modes (inferred):
        0: Manual? (User Timer?)
        1: Manual
        2: Frost Protection
        3: Off?
        """
        # We need to fetch current settings first to preserve other fields if API requires full object
        current = await self.get_appliance_features(hub_id, appliance_id)
        current.TimerMode = mode

        payload = {"TimerModeSettings": current.dict()}

        await self._request("POST", "/RemoteControl/SetTimerMode", json=payload)

    async def set_target_temperature(self, hub_id: str, appliance_id: str, temp: float) -> None:
        """Set target temperature.

        WARNING: The logs show setting temperature involves updating the 'TimerPeriods' for the current mode.
        This client might need to be smarter about which period to update (current active one).
        For now, this is a placeholder/advanced TODO.
        """
        _LOGGER.warning("set_target_temperature not fully implemented - requires complex schedule manipulation")
        pass

    async def set_appliance_mode(
        self, hub_id: str, appliance_ids: List[str], mode_settings: ApplianceModeSettings
    ) -> None:
        """Set appliance mode (Boost, Away, etc.)."""
        payload = {"Settings": mode_settings.dict(), "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetApplianceMode", json=payload)

    async def set_eco_start(self, hub_id: str, appliance_ids: List[str], enable: bool) -> None:
        """Enable/Disable EcoStart."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetEcoStart", json=payload)

    async def set_open_window_detection(self, hub_id: str, appliance_ids: List[str], enable: bool) -> None:
        """Enable/Disable Open Window Detection."""
        payload = {"Enable": enable, "HubId": hub_id, "ApplianceIds": appliance_ids}
        await self._request("POST", "/RemoteControl/SetOpenWindowDetection", json=payload)
