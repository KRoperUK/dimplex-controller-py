"""Coverage for previously untested public client methods."""

from __future__ import annotations

import aiohttp
import pytest

from dimplex_controller.client import DimplexControl
from dimplex_controller.models import TimerMode, TimerPeriod, Zone

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
    """set_away enables Away (modes=32, status=1); clear_away disables it."""
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

    assert bodies[0]["Settings"]["ApplianceModes"] == 32
    assert bodies[0]["Settings"]["Status"] == 1
    assert bodies[0]["Settings"]["Temperature"] == 12.0
    assert bodies[0]["Settings"]["NumberOfDays"] == 3
    assert bodies[1]["Settings"]["Status"] == 0
    assert bodies[1]["Settings"]["NumberOfDays"] == 0


@pytest.mark.asyncio
async def test_clear_boost(aresponses):
    """clear_boost disables Boost (status=0, time=0)."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return _json(aresponses)

    aresponses.add(HOST, "/api/RemoteControl/SetApplianceMode", "POST", handler)

    async with aiohttp.ClientSession() as session:
        await _authed(session).clear_boost("hub-1", ["a-1"])

    assert captured["body"]["Settings"]["ApplianceModes"] == 16
    assert captured["body"]["Settings"]["Status"] == 0
    assert captured["body"]["Settings"]["Time"] == 0


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
