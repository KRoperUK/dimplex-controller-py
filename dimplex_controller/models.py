from datetime import datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field


class Appliance(BaseModel):
    ApplianceId: str
    ApplianceType: str
    ApplianceModel: Optional[str] = None
    ZoneId: str
    FriendlyName: str
    ZoneName: str
    Icon: Optional[str] = None
    IconColor: Optional[str] = None
    InstallationDate: Optional[datetime] = None
    HasConnectivity: Optional[bool] = None


class Zone(BaseModel):
    ZoneId: str
    ZoneName: str
    HubId: str
    ZoneType: str
    Appliances: List[Appliance] = Field(default_factory=list)


class Hub(BaseModel):
    HubId: str
    Name: Optional[str] = Field(None, alias="HubName")
    FriendlyName: Optional[str] = None


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
    TimerPeriods: List[TimerPeriod] = Field(default_factory=list)


class UserContext(BaseModel):
    Id: str
    EmailAddress: Optional[str] = None
    Name: Optional[str] = None


class ApplianceStatus(BaseModel):
    """Represents the real-time status of an appliance as returned by GetApplianceOverview."""

    HubId: str
    ApplianceId: str
    ZoneId: str
    StatusTwo: Optional[int] = None
    ApplianceModes: Optional[int] = None
    RoomTemperature: Optional[float] = None
    ActiveSetPointTemperature: Optional[int] = None
    NormalTemperature: Optional[float] = None
    AwayDateTime: Optional[str] = None
    AwayTemperature: Optional[float] = None
    BoostDuration: Optional[int] = None
    BoostTemperature: Optional[float] = None
    OpenWindowEnabled: Optional[bool] = None
    EcoStartEnabled: Optional[bool] = None
    SetbackEnabled: Optional[bool] = None
    SetbackEnabledInStatusFrame: Optional[bool] = None
    SetbackTemperature: Optional[float] = None
    ComfortStatus: Optional[bool] = None
    AvailableHotWater: Optional[float] = None
    LockStatus: Optional[int] = None
    ErrorCode: Optional[str] = None
    WarningCode: Optional[str] = None


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
