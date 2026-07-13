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
        client = DimplexControl(session, refresh_token="fake_refresh", max_retries=0)
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


# ---------------------------------------------------------------------------
# get_tsi_energy_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tsi_energy_report(aresponses):
    """The Tsi energy report is parsed into a TsiEnergyReport model."""
    body = (
        '{"HubId":"hub-1",'
        '"ApplianceTelemetryData":{"a-1":[{"timestamp":"2026-06-01T00:00:00Z","value":0.1}],'
        '"a-2":[]}}'
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=body,
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        report = await client.get_tsi_energy_report("hub-1")

    assert report.HubId == "hub-1"
    assert set(report.ApplianceTelemetryData) == {"a-1", "a-2"}
    assert report.ApplianceTelemetryData["a-1"] == [{"timestamp": "2026-06-01T00:00:00Z", "value": 0.1}]
    assert report.ApplianceTelemetryData["a-2"] == []


@pytest.mark.asyncio
async def test_get_tsi_energy_report_no_hub(aresponses):
    """Hub id is not required — the model falls back to the response value."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"HubId":"hub-9","ApplianceTelemetryData":{}}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        report = await client.get_tsi_energy_report()

    assert report.HubId == "hub-9"
    assert report.ApplianceTelemetryData == {}


@pytest.mark.asyncio
async def test_get_tsi_energy_report_error(aresponses):
    """HTTP errors are raised as DimplexApiError."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        aresponses.Response(status=500, body="boom"),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        with pytest.raises(DimplexApiError):
            await client.get_tsi_energy_report("hub-1")


@pytest.mark.asyncio
async def test_get_tsi_energy_report_payload(aresponses):
    """The request payload includes HubId, StartDate, EndDate and report params."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"HubId":"hub-1","ApplianceTelemetryData":{}}',
        )

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        await client.get_tsi_energy_report(
            hub_id="hub-1",
            report_type=1,
            interval="00:10:00",
            start_date="2026-01-01T00:00:00Z",
            end_date="2026-07-12T23:59:59Z",
            include_previous_period=True,
        )

    assert captured["body"]["HubId"] == "hub-1"
    assert captured["body"]["TsiReportType"] == 1
    assert captured["body"]["Interval"] == "00:10:00"
    assert captured["body"]["StartDate"] == "2026-01-01T00:00:00Z"
    assert captured["body"]["EndDate"] == "2026-07-12T23:59:59Z"
    assert captured["body"]["IncludePreviousPeriod"] is True


@pytest.mark.asyncio
async def test_get_tsi_energy_report_omits_hub_id_when_none(aresponses):
    """When no hub_id is supplied, the payload does not contain a HubId key."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"HubId":"hub-9","ApplianceTelemetryData":{}}',
        )

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Reports/GetTsiEnergyReportDataForHub",
        "POST",
        handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999

        await client.get_tsi_energy_report()

    assert "HubId" not in captured["body"]
    assert "EndDate" in captured["body"]


@pytest.mark.asyncio
async def test_set_boost(aresponses):
    """Boost helper posts ApplianceModes=16 with duration in Time."""
    captured: dict = {}

    async def handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body="{}")

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetApplianceMode",
        "POST",
        handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        await client.set_boost("hub-1", ["a-1"], temperature=24.0, duration_minutes=90)

    assert captured["body"]["HubId"] == "hub-1"
    assert captured["body"]["ApplianceIds"] == ["a-1"]
    assert captured["body"]["Settings"]["ApplianceModes"] == 16
    assert captured["body"]["Settings"]["Status"] == 1
    assert captured["body"]["Settings"]["Temperature"] == 24.0
    assert captured["body"]["Settings"]["Time"] == 90


@pytest.mark.asyncio
async def test_set_target_temperature_updates_periods(aresponses):
    """Target temperature rewrites existing timer period temperatures."""
    captured: dict = {}

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetTimerModeDetailsForAppliance",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=(
                '{"HubId":"hub-1","ApplianceId":"a-1","TimerMode":1,'
                '"TimerPeriods":[{"DayOfWeek":1,"StartTime":"06:00:00",'
                '"EndTime":"09:00:00","Temperature":18.0}]}'
            ),
        ),
    )

    async def set_handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body="{}")

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetTimerMode",
        "POST",
        set_handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        await client.set_target_temperature("hub-1", "a-1", 21.5)

    periods = captured["body"]["TimerModeSettings"]["TimerPeriods"]
    assert len(periods) == 1
    assert periods[0]["Temperature"] == 21.5
    assert periods[0]["StartTime"] == "06:00:00"


@pytest.mark.asyncio
async def test_get_appliance_overview_empty_list(aresponses):
    """Empty overview returns an empty list — not an error.

    Regression for dimplex-controller-py#66. The cloud returns HTTP 200 with
    an empty body when every requested appliance is offline; the client must
    surface that as a successful empty list, not raise.
    """
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetApplianceOverview",
        "POST",
        aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body="[]"),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        statuses = await client.get_appliance_overview("hub-1", ["a-1", "a-2"])

    assert statuses == []


@pytest.mark.asyncio
async def test_get_appliance_overview_empty_map(aresponses):
    """Empty overview maps every requested id to None."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetApplianceOverview",
        "POST",
        aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body="[]"),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        result = await client.get_appliance_overview_map("hub-1", ["a-1", "a-2"])

    assert result == {"a-1": None, "a-2": None}


@pytest.mark.asyncio
async def test_export_tokens():
    """Public token export does not require private attribute access."""
    async with aiohttp.ClientSession() as session:
        client = DimplexControl(
            session,
            refresh_token="r",
            access_token="a",
            expires_at=123.0,
        )
        bundle = client.export_tokens()
        assert bundle.access_token == "a"
        assert bundle.refresh_token == "r"
        assert bundle.expires_at == 123.0
        assert bundle.as_dict()["refresh_token"] == "r"


@pytest.mark.asyncio
async def test_get_product_models(aresponses):
    """Product catalogue is parsed into ProductModel rows."""
    body = (
        '[{"ProductModelId":"id-1","ProductModelName":"QM100RF","ProductTypeName":"Quantum",'
        '"ProductModelExtensions":{"AUTOMATIC_PROVISIONING":'
        '"{\\"ratedPower\\":2.22,\\"chargeCapacity\\":15.5}"}}]'
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Appliances/GetProductModels",
        "GET",
        aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body=body),
    )
    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        models = await client.get_product_models()
    assert len(models) == 1
    assert models[0].ProductModelName == "QM100RF"
    assert models[0].automatic_provisioning is not None
    assert models[0].automatic_provisioning.rated_power == 2.22


@pytest.mark.asyncio
async def test_get_retries_on_503_then_succeeds(aresponses):
    """Idempotent GET retries on 503 and returns the successful body."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(status=503, headers={"Content-Type": "text/plain"}, body="busy"),
    )
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='[{"HubId": "123", "HubName": "Test Hub"}]',
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(
            session,
            refresh_token="fake_refresh",
            max_retries=2,
            retry_base_delay=0.01,
            retry_max_delay=0.02,
        )
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        hubs = await client.get_hubs()

    assert len(hubs) == 1
    assert hubs[0].HubId == "123"


@pytest.mark.asyncio
async def test_post_does_not_retry_by_default(aresponses):
    """Control POSTs fail immediately on 503 without a second attempt."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return aresponses.Response(status=503, headers={"Content-Type": "text/plain"}, body="busy")

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetEcoStart",
        "POST",
        handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(
            session,
            refresh_token="fake_refresh",
            max_retries=3,
            retry_base_delay=0.01,
        )
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        with pytest.raises(DimplexApiError) as exc:
            await client.set_eco_start("hub-1", ["a-1"], True)

    assert exc.value.status == 503
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_get_honours_retry_after(aresponses, monkeypatch):
    """Retry-After header is preferred over exponential backoff."""
    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr("dimplex_controller.client.asyncio.sleep", fake_sleep)

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=429,
            headers={"Content-Type": "text/plain", "Retry-After": "0.05"},
            body="rate limited",
        ),
    )
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
        client = DimplexControl(session, refresh_token="fake_refresh", max_retries=1)
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        hubs = await client.get_hubs()

    assert hubs == []
    assert slept == [0.05]


@pytest.mark.asyncio
async def test_set_period_setpoint_only_touches_matched_period(aresponses):
    """set_period_setpoint updates one period and preserves siblings."""
    get_body = {
        "HubId": "hub-1",
        "ApplianceId": "a-1",
        "TimerMode": 0,
        "TimerPeriods": [
            {"DayOfWeek": 1, "StartTime": "06:00:00", "EndTime": "09:00:00", "Temperature": 18.0},
            {"DayOfWeek": 1, "StartTime": "17:00:00", "EndTime": "22:00:00", "Temperature": 20.0},
            {"DayOfWeek": 2, "StartTime": "06:00:00", "EndTime": "09:00:00", "Temperature": 18.0},
        ],
    }
    import json

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetTimerModeDetailsForAppliance",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(get_body),
        ),
    )
    captured: dict = {}

    async def set_handler(request):
        captured["body"] = await request.json()
        return aresponses.Response(status=200, headers={"Content-Type": "application/json"}, body="{}")

    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetTimerMode",
        "POST",
        set_handler,
    )

    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        result = await client.set_period_setpoint(
            "hub-1",
            "a-1",
            day_of_week=1,
            start_time="17:00:00",
            temperature=21.5,
        )

    periods = captured["body"]["TimerModeSettings"]["TimerPeriods"]
    assert len(periods) == 3
    assert periods[0]["Temperature"] == 18.0
    assert periods[1]["Temperature"] == 21.5
    assert periods[2]["Temperature"] == 18.0
    assert result.TimerPeriods[1].Temperature == 21.5


@pytest.mark.asyncio
async def test_set_period_setpoint_missing_raises(aresponses):
    import json

    get_body = {
        "HubId": "hub-1",
        "ApplianceId": "a-1",
        "TimerMode": 1,
        "TimerPeriods": [
            {"DayOfWeek": 0, "StartTime": "00:00:00", "EndTime": "23:59:59", "Temperature": 19.0},
        ],
    }
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/GetTimerModeDetailsForAppliance",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(get_body),
        ),
    )
    async with aiohttp.ClientSession() as session:
        client = DimplexControl(session, refresh_token="fake_refresh")
        client.auth._access_token = "fake_access"
        client.auth._expires_at = 9999999999
        with pytest.raises(ValueError, match="No timer period"):
            await client.set_period_setpoint(
                "hub-1",
                "a-1",
                day_of_week=3,
                start_time="08:00:00",
                temperature=20.0,
            )


# ---------------------------------------------------------------------------
# on_token_update callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_token_update_fires_on_refresh(aresponses):
    """The on_token_update callback fires with a TokenBundle after a token refresh."""
    from dimplex_controller.auth import TokenBundle

    captured: list = []

    async def _on_update(bundle: TokenBundle):
        captured.append(bundle)

    # mock the /token endpoint (refresh)
    aresponses.add(
        "gdhvb2c.b2clogin.com",
        response=aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"access_token":"new_at","refresh_token":"new_rt","expires_in":3600}',
        ),
    )
    # mock the actual API call
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
        client = DimplexControl(session, refresh_token="old_rt", on_token_update=_on_update)
        # Force token to be expired so refresh triggers
        client.auth._expires_at = 0

        await client.get_hubs()

    assert len(captured) == 1
    assert isinstance(captured[0], TokenBundle)
    assert captured[0].access_token == "new_at"
    assert captured[0].refresh_token == "new_rt"


@pytest.mark.asyncio
async def test_on_token_update_sync_callback(aresponses):
    """A synchronous on_token_update callback also works."""
    from dimplex_controller.auth import TokenBundle

    captured: list = []

    def _on_update(bundle: TokenBundle):
        captured.append(bundle)

    aresponses.add(
        "gdhvb2c.b2clogin.com",
        response=aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"access_token":"at2","refresh_token":"rt2","expires_in":3600}',
        ),
    )
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
        client = DimplexControl(session, refresh_token="old_rt", on_token_update=_on_update)
        client.auth._expires_at = 0

        await client.get_hubs()

    assert len(captured) == 1
    assert captured[0].refresh_token == "rt2"
