"""Tests for data models."""

from dimplex_controller.models import (
    Appliance,
    ApplianceModeSettings,
    ApplianceStatus,
    Hub,
    TimerModeSettings,
    TimerPeriod,
    UserContext,
    Zone,
)


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
    assert settings.Temperature == 24.5
    assert settings.Time == 120
    assert settings.NumberOfDays == 7
    assert settings.Frequency == 2
