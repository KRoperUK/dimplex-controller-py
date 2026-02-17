import aiohttp
import pytest

from dimplex_controller.client import DimplexControl
from dimplex_controller.exceptions import DimplexApiError
from dimplex_controller.models import ApplianceStatus, Hub, Zone


@pytest.mark.asyncio
async def test_get_hubs(aresponses):
    """Test getting hubs."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='[{"HubId": "123", "HubName": "Test Hub", "FriendlyName": "My Hub"}]',
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        hubs = await client.get_hubs()
        assert len(hubs) == 1
        assert hubs[0].HubId == "123"
        assert hubs[0].Name == "Test Hub"
        assert isinstance(hubs[0], Hub)


@pytest.mark.asyncio
async def test_get_hubs_empty(aresponses):
    """Test getting hubs when none exist."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body="[]",
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        hubs = await client.get_hubs()
        assert len(hubs) == 0


@pytest.mark.asyncio
async def test_get_hub_zones(aresponses):
    """Test getting zones for a hub."""
    zone_body = (
        '[{"ZoneId": "z1", "ZoneName": "Living Room", ' '"HubId": "123", "ZoneType": "Heating", "Appliances": []}]'
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Zones/GetZonesAndAppliancesForHubId",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=zone_body,
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        zones = await client.get_hub_zones("123")
        assert len(zones) == 1
        assert zones[0].ZoneId == "z1"
        assert zones[0].ZoneName == "Living Room"
        assert isinstance(zones[0], Zone)


@pytest.mark.asyncio
async def test_get_appliance_overview(aresponses):
    """Test getting appliance status."""
    appliance_body = (
        '[{"HubId": "123", "ApplianceId": "a1", '
        '"ZoneId": "z1", "RoomTemperature": 22.5, '
        '"ActiveSetPointTemperature": 21}]'
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetApplianceOverview",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=appliance_body,
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        statuses = await client.get_appliance_overview("123", ["a1"])
        assert len(statuses) == 1
        assert statuses[0].ApplianceId == "a1"
        assert statuses[0].RoomTemperature == 22.5
        assert isinstance(statuses[0], ApplianceStatus)


@pytest.mark.asyncio
async def test_get_user_context(aresponses):
    """Test getting user context."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Identity/GetUserContext",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"Id": "user123", "EmailAddress": "test@example.com", "Name": "Test User"}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        context = await client.get_user_context()
        assert context.Id == "user123"
        assert context.EmailAddress == "test@example.com"
        assert context.Name == "Test User"


@pytest.mark.asyncio
async def test_api_error(aresponses):
    """Test API error handling."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=500,
            body="Internal Server Error",
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        with pytest.raises(DimplexApiError) as excinfo:
            await client.get_hubs()
        assert excinfo.value.status == 500


@pytest.mark.asyncio
async def test_is_authenticated(aresponses):
    """Test is_authenticated property."""
    async with aiohttp.ClientSession() as session:
        # Without tokens
        client = DimplexControl(session)
        assert not client.is_authenticated

        # With tokens
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        assert client.is_authenticated
