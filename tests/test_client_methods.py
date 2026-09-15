"""Coverage for previously untested public client methods."""

from __future__ import annotations

from datetime import datetime, timezone

import aiohttp
import pytest

from dimplex_controller.client import DimplexControl
from dimplex_controller.const import NO_SETPOINT_SENTINEL, NULL_DATETIME
from dimplex_controller.models import (
    ApplianceModeFlag,
    HygieneFrequency,
    SetbackStatus,
    TimerMode,
    TimerPeriod,
    Zone,
)

HOST = "mobileapi.gdhv-iot.com"

_TIMER_BODY = (
    '{"HubId":"hub-1","ApplianceId":"a-1","TimerMode":1,'
    '"TimerPeriods":[{"DayOfWeek":1,"StartTime":"06:00:00",'
    '"EndTime":"09:00:00","Temperature":18.0},'
    '{"DayOfWeek":1,"StartTime":"17:00:00","EndTime":"22:00:00","Temperature":20.0}]}'
)


def _authed(session: aiohttp.ClientSession) -> DimplexControl:
    client = DimplexControl(session, refresh_token="fake_refresh")
    client.auth._access_token = "fake_access"
    client.auth._expires_at = 9999999999
    return client


def _json(aresponses, body: str = "{}"):
    return aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body=body)


@pytest.mark.asyncio
async def test_get_zone(aresponses):
    """get_zone posts HubId+ZoneId and parses a Zone."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(
            aresponses,
            '{"ZoneId":"z1","ZoneName":"Living Room","HubId":"hub-1","ZoneType":"Heating","Appliances":[]}',
        )

    aresponses.add(HOST, "/api/Zones/GetZone", "POST", handler)

    async with aiohttp.ClientSession() as session:
        zone = await _authed(session).get_zone("hub-1", "z1")

    assert isinstance(zone, Zone)
    assert zone.ZoneId == "z1"
    assert captured["body"] == {"HubId": "hub-1", "ZoneId": "z1"}


@pytest.mark.asyncio
async def test_set_mode_reads_then_writes(aresponses):
    """set_mode reads current settings, changes TimerMode, and writes it back."""
    captured: dict = {}

    aresponses.add(HOST, "/api/RemoteControl/GetTimerModeDetailsForAppliance", "POST", _json(aresponses, _TIMER_BODY))

    async def set_handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetTimerMode", "POST", set_handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).set_mode("hub-1", "a-1", TimerMode.MANUAL)

    settings = captured["body"]["TimerModeSettings"]
    assert settings["TimerMode"] == int(TimerMode.MANUAL)
    # Periods are preserved, not clobbered.
    assert len(settings["TimerPeriods"]) == 2


@pytest.mark.asyncio
async def test_update_period_replaces_matched(aresponses):
    """update_period swaps the period matched by day + start time."""
    captured: dict = {}

    aresponses.add(HOST, "/api/RemoteControl/GetTimerModeDetailsForAppliance", "POST", _json(aresponses, _TIMER_BODY))

    async def set_handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetTimerMode", "POST", set_handler)

    new_period = TimerPeriod(DayOfWeek=1, StartTime="06:00:00", EndTime="10:00:00", Temperature=19.5)

    async with aiohttp.ClientSession() as session:
        result = await _authed(session).update_period("hub-1", "a-1", new_period)

    periods = captured["body"]["TimerModeSettings"]["TimerPeriods"]
    assert periods[0]["EndTime"] == "10:00:00"
    assert periods[0]["Temperature"] == 19.5
    assert periods[1]["Temperature"] == 20.0  # sibling untouched
    assert result.TimerPeriods[0].Temperature == 19.5


@pytest.mark.asyncio
async def test_update_period_missing_raises(aresponses):
    """update_period raises when no period matches the key."""
    aresponses.add(HOST, "/api/RemoteControl/GetTimerModeDetailsForAppliance", "POST", _json(aresponses, _TIMER_BODY))

    missing = TimerPeriod(DayOfWeek=5, StartTime="03:00:00", EndTime="04:00:00", Temperature=15.0)

    async with aiohttp.ClientSession() as session:
        with pytest.raises(ValueError, match="No timer period"):
            await _authed(session).update_period("hub-1", "a-1", missing)


@pytest.mark.asyncio
async def test_set_target_temperature_installs_full_week_when_empty(aresponses):
    """With no existing periods, a full-week manual schedule is installed."""
    captured: dict = {}

    aresponses.add(
        HOST,
        "/api/RemoteControl/GetTimerModeDetailsForAppliance",
        "POST",
        _json(aresponses, '{"HubId":"hub-1","ApplianceId":"a-1","TimerMode":0,"TimerPeriods":[]}'),
    )

    async def set_handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetTimerMode", "POST", set_handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).set_target_temperature("hub-1", "a-1", 20.0)

    settings = captured["body"]["TimerModeSettings"]
    assert settings["TimerMode"] == int(TimerMode.MANUAL)
    assert len(settings["TimerPeriods"]) == 7
    assert {p["DayOfWeek"] for p in settings["TimerPeriods"]} == set(range(7))
    assert all(p["Temperature"] == 20.0 for p in settings["TimerPeriods"])


@pytest.mark.asyncio
async def test_set_away_and_clear_away(aresponses):
    """set_away enables Away (modes=4, status=1); clear_away disables it."""
    bodies: list[dict] = []

    async def handler(request):
        bodies.append(await request.json())
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)
    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_away("hub-1", ["a-1"], temperature=12.0, number_of_days=3)
        await client.clear_away("hub-1", ["a-1"])

    assert bodies[0]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.AWAY) == 4
    assert bodies[0]["Settings"]["Status"] == 1
    assert bodies[0]["Settings"]["Temperature"] == 12
    assert bodies[0]["Settings"]["NumberOfDays"] == 3
    # number_of_days is translated into the Date the app actually sends.
    assert bodies[0]["Settings"]["Date"] != NULL_DATETIME
    assert bodies[1]["Settings"]["Status"] == 0
    assert bodies[1]["Settings"]["NumberOfDays"] == 0
    assert bodies[1]["Settings"]["Date"] == NULL_DATETIME


@pytest.mark.asyncio
async def test_set_away_accepts_explicit_until(aresponses):
    """An explicit away-until datetime is serialised into Date."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    until = datetime(2026, 12, 24, 9, 30, tzinfo=timezone.utc)
    async with aiohttp.ClientSession() as session:
        await _authed(session).set_away("hub-1", ["a-1"], temperature=18.0, until=until)

    # Naive .NET DateTime — no offset suffix.
    assert captured["body"]["Settings"]["Date"] == "2026-12-24T09:30:00"
    assert captured["body"]["Settings"]["Temperature"] == 18


@pytest.mark.asyncio
async def test_clear_boost(aresponses):
    """clear_boost disables Boost (modes=2, status=0, time=0)."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).clear_boost("hub-1", ["a-1"])

    assert captured["body"]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.BOOST) == 2
    assert captured["body"]["Settings"]["Status"] == 0
    assert captured["body"]["Settings"]["Time"] == 0


@pytest.mark.asyncio
async def test_set_frost_protect_is_the_off_path(aresponses):
    """turn_off engages FrostProtect at the 7 °C floor, not SetTimerMode."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).turn_off("hub-1", ["a-1"])

    settings = captured["body"]["Settings"]
    assert settings["ApplianceModes"] == int(ApplianceModeFlag.FROST_PROTECT) == 32
    assert settings["Status"] == 1
    assert settings["Temperature"] == 7


@pytest.mark.asyncio
async def test_set_advance_defaults_to_no_setpoint_sentinel(aresponses):
    """Advance with no explicit temperature sends the 0xFF sentinel."""
    bodies: list[dict] = []

    async def handler(request):
        bodies.append(await request.json())
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)
    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_advance("hub-1", ["a-1"])
        await client.set_advance("hub-1", ["a-1"], temperature=19.0)

    assert bodies[0]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.ADVANCE) == 16
    assert bodies[0]["Settings"]["Temperature"] == NO_SETPOINT_SENTINEL
    assert bodies[1]["Settings"]["Temperature"] == 19


@pytest.mark.asyncio
async def test_set_appliance_setpoint_temperature(aresponses):
    """The dedicated setpoint endpoint posts a rounded byte temperature."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses, "true")

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceSetpointTemperature", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).set_appliance_setpoint_temperature("hub-1", ["a-1"], 21.5)

    assert captured["body"] == {"HubId": "hub-1", "ApplianceIds": ["a-1"], "Temperature": 22}


@pytest.mark.asyncio
async def test_set_setback_temperature(aresponses):
    """Setback write posts an EStatus byte plus the temperature."""
    bodies: list[dict] = []

    async def handler(request):
        bodies.append(await request.json())
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetSetbackTemperature", "POST", handler)
    aresponses.add(HOST, "/api/RemoteControl/SetSetbackTemperature", "POST", handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_setback_temperature("hub-1", ["a-1"], temperature=16.4)
        await client.set_setback_temperature("hub-1", ["a-1"], temperature=16.0, status=SetbackStatus.INACTIVE)

    assert bodies[0] == {"HubId": "hub-1", "ApplianceIds": ["a-1"], "Status": 1, "Temperature": 16}
    assert bodies[1]["Status"] == 0


@pytest.mark.asyncio
async def test_hot_water_helpers_target_hwc_endpoints(aresponses):
    """Cylinder helpers post ApplianceModeSettings to the HWC endpoints."""
    bodies: dict[str, dict] = {}

    def handler_for(name: str):
        async def handler(request):
            bodies[name] = await request.json()
            return _json(aresponses)

        return handler

    aresponses.add(HOST, "/api/RemoteControl/SetBoostTemperatureHwc", "POST", handler_for("boost"))
    aresponses.add(HOST, "/api/RemoteControl/SetNormalTemperatureHwc", "POST", handler_for("normal"))
    aresponses.add(HOST, "/api/RemoteControl/SetHygieneSettingsHeatPumpHwc", "POST", handler_for("hygiene"))

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_hot_water_boost_temperature("hub-1", ["a-1"], 60.0)
        await client.set_hot_water_normal_temperature("hub-1", ["a-1"], 50.0)
        await client.set_hot_water_hygiene(
            "hub-1", ["a-1"], temperature=65.0, frequency=HygieneFrequency.WEEKLY, heat_pump=True
        )

    assert bodies["boost"]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.BOOST)
    assert bodies["boost"]["Settings"]["Temperature"] == 60
    assert bodies["normal"]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.NORMAL) == 8192
    assert bodies["hygiene"]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.HYGIENE) == 256
    assert bodies["hygiene"]["Settings"]["Frequency"] == 7


@pytest.mark.asyncio
async def test_copy_schedule_to_appliances(aresponses):
    """Schedule copy posts the source appliance and the targets."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/CopyScheduleToAppliances", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).copy_schedule_to_appliances("hub-1", "a-1", ["a-2", "a-3"], timer_mode=1)

    assert captured["body"] == {
        "HubId": "hub-1",
        "FromApplianceId": "a-1",
        "ApplianceIds": ["a-2", "a-3"],
        "TimerMode": 1,
    }


@pytest.mark.asyncio
async def test_set_open_window_detection(aresponses):
    """set_open_window_detection posts the Enable flag."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetOpenWindowDetection", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).set_open_window_detection("hub-1", ["a-1"], True)

    assert captured["body"] == {"Enable": True, "HubId": "hub-1", "ApplianceIds": ["a-1"]}


@pytest.mark.asyncio
async def test_get_schedule_alias(aresponses):
    """get_schedule is an alias for get_appliance_features."""
    aresponses.add(HOST, "/api/RemoteControl/GetTimerModeDetailsForAppliance", "POST", _json(aresponses, _TIMER_BODY))

    async with aiohttp.ClientSession() as session:
        schedule = await _authed(session).get_schedule("hub-1", "a-1")

    assert schedule.TimerMode == 1
    assert len(schedule.TimerPeriods) == 2


@pytest.mark.asyncio
async def test_manual_and_eco_mode_helpers(aresponses):
    """Manual (128) and Eco (64) engage via SetApplianceMode."""
    bodies: list[dict] = []

    async def handler(request):
        bodies.append(await request.json())
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)
    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_manual("hub-1", ["a-1"], temperature=20.0)
        await client.set_eco_mode("hub-1", ["a-1"], temperature=17.0)

    assert bodies[0]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.MANUAL) == 128
    assert bodies[0]["Settings"]["Temperature"] == 20
    assert bodies[1]["Settings"]["ApplianceModes"] == int(ApplianceModeFlag.ECO) == 64


@pytest.mark.asyncio
async def test_set_hot_water_mode_selects_heat_pump_endpoint(aresponses):
    """heat_pump=True routes to the ASHW cylinder endpoint."""
    seen: list[str] = []

    async def handler(request):
        seen.append(request.path)
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceModeHwc", "POST", handler)
    aresponses.add(HOST, "/api/RemoteControl/SetApplianceModeHeatPumpHwc", "POST", handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        await client.set_hot_water_mode("hub-1", ["a-1"], ApplianceModeFlag.NORMAL, temperature=50.0)
        await client.set_hot_water_mode("hub-1", ["a-1"], ApplianceModeFlag.BOOST, temperature=60.0, heat_pump=True)

    assert seen == [
        "/api/RemoteControl/SetApplianceModeHwc",
        "/api/RemoteControl/SetApplianceModeHeatPumpHwc",
    ]


@pytest.mark.asyncio
async def test_heat_pump_hot_water_schedule_round_trip(aresponses):
    """The ASHW schedule is read then written back through its own endpoints."""
    captured: dict = {}

    async def write_handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(
        HOST,
        "/api/RemoteControl/ApiGetTimerModeDetailsForHeatPumpHwcAppliance",
        "POST",
        _json(aresponses, _TIMER_BODY),
    )
    aresponses.add(HOST, "/api/RemoteControl/UpdateHeatPumpHwcSchedulePeriods", "POST", write_handler)

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        settings = await client.get_heat_pump_hot_water_schedule("hub-1", "a-1")
        settings.TimerPeriods[0].Temperature = 55.0
        await client.set_heat_pump_hot_water_schedule(settings)

    assert len(settings.TimerPeriods) == 2
    assert captured["body"]["TimerModeSettings"]["TimerPeriods"][0]["Temperature"] == 55.0
