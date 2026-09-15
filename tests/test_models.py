"""Tests for data models."""

from dimplex_controller.const import NO_SETPOINT_SENTINEL
from dimplex_controller.models import (
    Appliance,
    ApplianceModeFlag,
    ApplianceModeSettings,
    ApplianceStatus,
    Hub,
    HygieneFrequency,
    SetbackStatus,
    TimerModeSettings,
    TimerPeriod,
    UserContext,
    Zone,
)


def _status(**kwargs) -> ApplianceStatus:
    return ApplianceStatus(HubId="h1", ApplianceId="a1", ZoneId="z1", **kwargs)


def test_appliance_mode_flag_values_match_the_app():
    """EApplianceModes values recovered from Dimplex Control APK 2.26.0."""
    assert int(ApplianceModeFlag.TIMER_MODE) == 1
    assert int(ApplianceModeFlag.BOOST) == 2
    assert int(ApplianceModeFlag.AWAY) == 4
    assert int(ApplianceModeFlag.HOLIDAY) == 8
    assert int(ApplianceModeFlag.ADVANCE) == 16
    assert int(ApplianceModeFlag.FROST_PROTECT) == 32
    assert int(ApplianceModeFlag.ECO) == 64
    assert int(ApplianceModeFlag.MANUAL) == 128
    assert int(ApplianceModeFlag.HYGIENE) == 256
    assert int(ApplianceModeFlag.NORMAL) == 8192
    assert int(ApplianceModeFlag.STANDBY) == 16384


def test_supporting_enum_values():
    assert int(SetbackStatus.DSM_MODE) == 2
    assert int(HygieneFrequency.WEEKLY) == 7
    assert int(HygieneFrequency.MONTHLY) == 28


def test_boost_is_read_from_the_boost_bit_not_the_duration():
    """modes=3 is Timer+Boost; a stale duration alone must not read as boost."""
    assert _status(ApplianceModes=3, BoostDuration=30).is_boost_active is True
    assert _status(ApplianceModes=1, BoostDuration=30).is_boost_active is False
    # Advance (16) is not Boost — this was the bug behind hass#163.
    assert _status(ApplianceModes=17).is_boost_active is False
    assert _status(ApplianceModes=17).is_advance_active is True
    # No ApplianceModes reported at all: fall back to the duration.
    assert _status(BoostDuration=30).is_boost_active is True


def test_away_is_read_from_the_away_bit():
    """modes=5 is Timer+Away; FrostProtect (32) is a different mode."""
    assert _status(ApplianceModes=5).is_away_active is True
    assert _status(ApplianceModes=33).is_away_active is False
    assert _status(ApplianceModes=33).is_frost_protect_active is True
    # Stale away-until date with the bit clear must not read as away.
    assert _status(ApplianceModes=1, AwayDateTime="2026-12-24T00:00:00").is_away_active is False
    # Unknown modes: fall back to the date.
    assert _status(AwayDateTime="2026-12-24T00:00:00").is_away_active is True


def test_active_modes_names_engaged_bits():
    assert _status(ApplianceModes=3).active_modes == ["TIMER_MODE", "BOOST"]
    assert _status().active_modes == []


def test_active_setpoint_filters_the_no_setpoint_sentinel():
    assert _status(ActiveSetPointTemperature=21.0).active_setpoint_temperature == 21.0
    assert _status(ActiveSetPointTemperature=NO_SETPOINT_SENTINEL).active_setpoint_temperature is None
    assert _status().active_setpoint_temperature is None


def test_hub_model():
    """Test Hub model parsing."""
    hub = Hub(HubId="123", HubName="Test Hub", FriendlyName="My Hub")
    assert hub.HubId == "123"
    assert hub.Name == "Test Hub"
    assert hub.FriendlyName == "My Hub"


def test_hub_model_with_alias():
    """Test Hub model with HubName alias."""
    data = {"HubId": "456", "HubName": "Another Hub"}
    hub = Hub(**data)
    assert hub.HubId == "456"
    assert hub.Name == "Another Hub"


def test_appliance_model():
    """Test Appliance model parsing."""
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Radiator",
        ApplianceModel="Series 7",
        ZoneId="z1",
        FriendlyName="Living Room Heater",
        ZoneName="Living Room",
    )
    assert appliance.ApplianceId == "a1"
    assert appliance.FriendlyName == "Living Room Heater"
    assert appliance.ZoneName == "Living Room"


def test_zone_model():
    """Test Zone model parsing."""
    zone = Zone(
        ZoneId="z1",
        ZoneName="Living Room",
        HubId="123",
        ZoneType="Heating",
        Appliances=[],
    )
    assert zone.ZoneId == "z1"
    assert zone.ZoneName == "Living Room"
    assert zone.HubId == "123"
    assert len(zone.Appliances) == 0


def test_zone_model_with_appliances():
    """Test Zone model with nested appliances."""
    appliance_data = {
        "ApplianceId": "a1",
        "ApplianceType": "Radiator",
        "ZoneId": "z1",
        "FriendlyName": "Radiator",
        "ZoneName": "Living Room",
    }
    zone_data = {
        "ZoneId": "z1",
        "ZoneName": "Living Room",
        "HubId": "123",
        "ZoneType": "Heating",
        "Appliances": [appliance_data],
    }
    zone = Zone(**zone_data)
    assert len(zone.Appliances) == 1
    assert zone.Appliances[0].ApplianceId == "a1"


def test_timer_period_model():
    """Test TimerPeriod model."""
    period = TimerPeriod(
        DayOfWeek=1,
        StartTime="08:00:00",
        EndTime="22:00:00",
        Temperature=21.0,
    )
    assert period.DayOfWeek == 1
    assert period.StartTime == "08:00:00"
    assert period.Temperature == 21.0


def test_timer_period_time_properties():
    """Test TimerPeriod time property accessors."""
    period = TimerPeriod(
        DayOfWeek=1,
        StartTime="08:30:45",
        EndTime="22:15:00",
        Temperature=20.5,
    )
    start_time = period.start_time_obj
    end_time = period.end_time_obj

    assert start_time.hour == 8
    assert start_time.minute == 30
    assert start_time.second == 45
    assert end_time.hour == 22
    assert end_time.minute == 15


def test_timer_mode_settings_model():
    """Test TimerModeSettings model."""
    settings = TimerModeSettings(
        HubId="123",
        ApplianceId="a1",
        TimerMode=1,
        TimerPeriods=[],
    )
    assert settings.HubId == "123"
    assert settings.ApplianceId == "a1"
    assert settings.TimerMode == 1
    assert len(settings.TimerPeriods) == 0


def test_timer_mode_settings_with_periods():
    """Test TimerModeSettings with timer periods."""
    periods_data = [
        {"DayOfWeek": 1, "StartTime": "08:00:00", "EndTime": "22:00:00", "Temperature": 21.0},
        {"DayOfWeek": 2, "StartTime": "08:00:00", "EndTime": "22:00:00", "Temperature": 20.0},
    ]
    settings = TimerModeSettings(
        HubId="123",
        ApplianceId="a1",
        TimerMode=1,
        TimerPeriods=periods_data,
    )
    assert len(settings.TimerPeriods) == 2
    assert settings.TimerPeriods[0].Temperature == 21.0
    assert settings.TimerPeriods[1].Temperature == 20.0


def test_user_context_model():
    """Test UserContext model."""
    context = UserContext(
        Id="user123",
        EmailAddress="test@example.com",
        Name="Test User",
    )
    assert context.Id == "user123"
    assert context.EmailAddress == "test@example.com"
    assert context.Name == "Test User"


def test_user_context_optional_fields():
    """Test UserContext with optional fields."""
    context = UserContext(Id="user456")
    assert context.Id == "user456"
    assert context.EmailAddress is None
    assert context.Name is None


def test_appliance_status_model():
    """Test ApplianceStatus model with minimal fields."""
    status = ApplianceStatus(
        HubId="123",
        ApplianceId="a1",
        ZoneId="z1",
    )
    assert status.HubId == "123"
    assert status.ApplianceId == "a1"
    assert status.ZoneId == "z1"


def test_appliance_status_model_full():
    """Test ApplianceStatus model with all fields."""
    status = ApplianceStatus(
        HubId="123",
        ApplianceId="a1",
        ZoneId="z1",
        StatusTwo=1,
        ApplianceModes=2,
        RoomTemperature=22.5,
        ActiveSetPointTemperature=21,
        NormalTemperature=20.0,
        AwayTemperature=15.0,
        BoostDuration=60,
        BoostTemperature=25.0,
        OpenWindowEnabled=True,
        EcoStartEnabled=False,
        ComfortStatus=True,
    )
    assert status.RoomTemperature == 22.5
    assert status.ActiveSetPointTemperature == 21
    assert status.BoostTemperature == 25.0
    assert status.OpenWindowEnabled is True
    assert status.EcoStartEnabled is False


def test_appliance_mode_settings_model():
    """Test ApplianceModeSettings model."""
    settings = ApplianceModeSettings(
        ApplianceModes=1,
        Status=0,
        Temperature=23.0,
    )
    assert settings.ApplianceModes == 1
    assert settings.Temperature == 23.0
    assert settings.Time == 0  # Default


def test_appliance_mode_settings_full():
    """Test ApplianceModeSettings with all parameters."""
    settings = ApplianceModeSettings(
        ApplianceModes=5,
        Status=1,
        Temperature=24.5,
        Time=120,
        NumberOfDays=7,
        Frequency=2,
    )
    assert settings.ApplianceModes == 5
    # The wire field is a short, so fractional degrees are rounded.
    assert settings.Temperature == 24
    assert settings.Time == 120
    assert settings.NumberOfDays == 7
    assert settings.Frequency == 2


def test_automatic_provisioning_parsing():
    """AUTOMATIC_PROVISIONING JSON is decoded into a typed model."""
    raw = '{"bottomElementPowerRating":"0.74","topElementPowerRating":"1.48","ratedPower":2.22}'
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Quantum",
        ZoneId="z1",
        FriendlyName="Room",
        ZoneName="Room",
        ProductModelExtensions={"AUTOMATIC_PROVISIONING": raw},
    )
    provisioning = appliance.automatic_provisioning
    assert provisioning is not None
    assert provisioning.bottom_element_power_rating == 0.74
    assert provisioning.top_element_power_rating == 1.48
    assert provisioning.rated_power == 2.22


def test_automatic_provisioning_missing():
    """Appliances without extensions return None."""
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Quantum",
        ZoneId="z1",
        FriendlyName="Room",
        ZoneName="Room",
    )
    assert appliance.automatic_provisioning is None


def test_automatic_provisioning_invalid_json():
    """Malformed extension JSON is handled gracefully."""
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Quantum",
        ZoneId="z1",
        FriendlyName="Room",
        ZoneName="Room",
        ProductModelExtensions={"AUTOMATIC_PROVISIONING": "not-json"},
    )
    assert appliance.automatic_provisioning is None


def test_appliance_with_firmware_and_telemetry():
    """Appliance parses firmware and telemetry metadata from the cloud."""
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Quantum",
        ZoneId="z1",
        FriendlyName="Room",
        ZoneName="Room",
        FirmwareVersion="6",
        SeriesIdentifier="G12",
        SecurityCode="123456",
        LastTelemDate="2026-06-12T09:45:34.89Z",
    )
    assert appliance.FirmwareVersion == "6"
    assert appliance.SeriesIdentifier == "G12"
    assert appliance.SecurityCode == "123456"
    assert appliance.LastTelemDate is not None


def test_zone_with_room_type_and_icon():
    """Zone parses optional icon and room type fields."""
    zone = Zone(
        ZoneId="z1",
        ZoneName="Living Room",
        HubId="h1",
        ZoneType="Heating",
        RoomType="Lounge",
        Icon="ic_sofa",
        IconColor="#D7324F",
    )
    assert zone.RoomType == "Lounge"
    assert zone.Icon == "ic_sofa"
    assert zone.IconColor == "#D7324F"


def test_hub_with_connection_state():
    """Hub parses the extended fields returned by GetUserHubs."""
    hub = Hub(
        HubId="h1",
        HubName="Home",
        FriendlyName="7 Example Close",
        ConnectionState=1,
        FirmwareVersion="129.12.5",
        NumberOfZones=3,
        NumberOfAppliances=3,
        IsServiceModeEnabled=False,
        LastTelemDate="2026-06-12T09:45:34.89Z",
    )
    assert hub.Name == "Home"
    assert hub.FriendlyName == "7 Example Close"
    assert hub.ConnectionState == 1
    assert hub.FirmwareVersion == "129.12.5"
    assert hub.NumberOfZones == 3
    assert hub.NumberOfAppliances == 3
    assert hub.IsServiceModeEnabled is False
    assert hub.LastTelemDate is not None


def test_timer_period_malformed_time_returns_none():
    """Malformed StartTime/EndTime strings return None instead of raising."""
    period = TimerPeriod(DayOfWeek=0, StartTime="invalid", EndTime="also-bad", Temperature=18.0)
    assert period.start_time_obj is None
    assert period.end_time_obj is None


def test_timer_period_empty_time_returns_none():
    """Empty time strings return None."""
    period = TimerPeriod(DayOfWeek=0, StartTime="", EndTime="", Temperature=18.0)
    assert period.start_time_obj is None
    assert period.end_time_obj is None
