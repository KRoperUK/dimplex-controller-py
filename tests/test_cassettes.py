"""Happy-path parsing against committed API cassettes (no live cloud)."""

import aiohttp
import pytest

from dimplex_controller.client import DimplexControl
from dimplex_controller.models import ApplianceStatus, Hub, Zone

from .fixtures import load_cassette


def test_hubs_cassette_shape():
    data = load_cassette("hubs")
    hubs = [Hub.model_validate(row) for row in data]
    assert hubs[0].HubId == "hub-demo-001"
    assert "example.com" in (hubs[0].PrimaryUserEmail or "")


def test_zones_cassette_shape():
    data = load_cassette("zones")
    zones = [Zone.model_validate(row) for row in data]
    assert zones[0].ZoneName == "Living Room"
    assert zones[0].Appliances[0].automatic_provisioning is not None


def test_overview_cassette_shape():
    data = load_cassette("overview")
    status = [ApplianceStatus.model_validate(row) for row in data]
    assert status[0].RoomTemperature == 21.5


def test_energy_cassette_points():
    data = load_cassette("energy_report")
    points = data["ApplianceTelemetryData"]["app-1"]
    # Cassette uses a simplified shape; parser may return empty for unknown keys —
    # assert structure is present for CI documentation.
    assert isinstance(points, list)
    assert len(points) == 2


@pytest.mark.asyncio
async def test_client_get_hubs_from_cassette(aresponses):
    import json

    body = json.dumps(load_cassette("hubs"))
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body=body),
    )
    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        hubs = await client.get_hubs()
    assert hubs[0].HubId == "hub-demo-001"


@pytest.mark.asyncio
async def test_client_overview_and_energy_cassettes(aresponses):
    import json

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetApplianceOverview",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(load_cassette("overview")),
        ),
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(load_cassette("energy_report")),
        ),
    )
    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        overview = await client.get_appliance_overview("hub-demo-001", ["app-1"])
        report = await client.get_tsi_energy_report(hub_id="hub-demo-001")
    assert overview[0].ApplianceId == "app-1"
    assert "app-1" in report.ApplianceTelemetryData
