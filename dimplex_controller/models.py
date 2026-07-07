from datetime import datetime, time

from pydantic import BaseModel, Field


class Appliance(BaseModel):
    ApplianceId: str
    ApplianceType: str
    ApplianceModel: str | None = None
    ZoneId: str
    FriendlyName: str
    ZoneName: str
    Icon: str | None = None
    IconColor: str | None = None
    InstallationDate: datetime | None = None
    HasConnectivity: bool | None = None


class Zone(BaseModel):
    ZoneId: str
    ZoneName: str
    HubId: str
    ZoneType: str
    Appliances: list[Appliance] = Field(default_factory=list)


class Hub(BaseModel):
    HubId: str
    Name: str | None = Field(None, alias="HubName")
    FriendlyName: str | None = None


class TimerPeriod(BaseModel):
    DayOfWeek: int
    StartTime: str  # Kept as str for easy JSON serialization
    EndTime: str
    Temperature: float

    @property
    def start_time_obj(self) -> time:
        return datetime.strptime(self.StartTime, "%H:%M:%S").time()

    @property
    def end_time_obj(self) -> time:
        return datetime.strptime(self.EndTime, "%H:%M:%S").time()


class TimerModeSettings(BaseModel):
    HubId: str
    ApplianceId: str
    TimerMode: int
    TimerPeriods: list[TimerPeriod] = Field(default_factory=list)


class UserContext(BaseModel):
    Id: str
    EmailAddress: str | None = None
    Name: str | None = None


class ApplianceStatus(BaseModel):
    """Represents the real-time status of an appliance as returned by GetApplianceOverview."""

    HubId: str
    ApplianceId: str
    ZoneId: str
    StatusTwo: int | None = None
    ApplianceModes: int | None = None
    RoomTemperature: float | None = None
    ActiveSetPointTemperature: int | None = None
    NormalTemperature: float | None = None
    AwayDateTime: str | None = None
    AwayTemperature: float | None = None
    BoostDuration: int | None = None
    BoostTemperature: float | None = None
    OpenWindowEnabled: bool | None = None
    EcoStartEnabled: bool | None = None
    SetbackEnabled: bool | None = None
    SetbackEnabledInStatusFrame: bool | None = None
    SetbackTemperature: float | None = None
    ComfortStatus: bool | None = None
    AvailableHotWater: float | None = None
    LockStatus: int | None = None
    ErrorCode: str | None = None
    WarningCode: str | None = None


class ApplianceModeSettings(BaseModel):
    """Settings used to control appliance modes like Boost or Away."""

    ApplianceModes: int
    Status: int
    Temperature: float = 23.0
    Time: int = 0
    Date: str = "0001-01-01T00:00:00"
    StatusTwo: int = 0
    NumberOfDays: int = 0
    Frequency: int = 0
