from __future__ import annotations

import json
from datetime import datetime, time
from enum import IntEnum, IntFlag
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimerMode(IntEnum):
    """Observed timer / operation mode values for ``TimerModeSettings.TimerMode``.

    Exact product names vary by appliance firmware; these are the values used
    by the Dimplex Control mobile client and reverse-engineered traffic.
    """

    USER_TIMER = 0
    MANUAL = 1
    FROST_PROTECTION = 2
    OFF = 3


class ApplianceModeFlag(IntFlag):
    """Bit flags for ``ApplianceStatus.ApplianceModes`` / mode write payloads.

    Only bits confirmed in traffic or the official app docs are named.
    ``BOOST`` (16) is used by the mobile app for boost mode.
    ``AWAY`` (32) is inferred from status frame pairing with Away* fields —
    treat as best-effort until more captures confirm it for every model.
    """

    NONE = 0
    BOOST = 16
    AWAY = 32


class AutomaticProvisioning(BaseModel):
    """Parsed contents of ``ProductModelExtensions.AUTOMATIC_PROVISIONING``.

    The cloud stores this as a JSON string; :class:`Appliance` decodes it
    automatically so callers can read the heater's electrical characteristics.

    Observed units (from product catalogue / live Quantum payloads):

    * power ratings — kW
    * charge capacity — kWh
    * charge element resistance — ohms
    """

    model_config = ConfigDict(populate_by_name=True)

    bottom_element_power_rating: float | None = Field(None, alias="bottomElementPowerRating")
    top_element_power_rating: float | None = Field(None, alias="topElementPowerRating")
    rated_power: float | None = Field(None, alias="ratedPower")
    charge_capacity: float | None = Field(None, alias="chargeCapacity")
    charge_element_resistance: float | None = Field(None, alias="chargeElementResistance")
    power_offset: float | None = Field(None, alias="powerOffset")


class ProductModel(BaseModel):
    """A row from ``GET /Appliances/GetProductModels``."""

    model_config = ConfigDict(populate_by_name=True)

    ProductModelId: str | None = None
    ProductTypeId: str | None = None
    ProductModelName: str | None = None
    ProductTypeName: str | None = None
    ProductModelExtensions: dict[str, str] | None = None

    @field_validator("ProductModelExtensions", mode="before")
    @classmethod
    def _coerce_extensions(cls, value: Any) -> dict[str, str] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in value.items()}
        return None  # unexpected type; Pydantic will reject

    @property
    def automatic_provisioning(self) -> AutomaticProvisioning | None:
        """Return decoded AUTOMATIC_PROVISIONING, if present."""
        raw = (self.ProductModelExtensions or {}).get("AUTOMATIC_PROVISIONING")
        if not raw:
            return None
        try:
            return AutomaticProvisioning.model_validate_json(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            return None


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
    SecurityCode: str | None = None
    LastTelemDate: datetime | None = None
    SeriesIdentifier: str | None = None
    FirmwareVersion: str | None = None
    ProductModelExtensions: dict[str, str] | None = None

    @field_validator("ProductModelExtensions", mode="before")
    @classmethod
    def _coerce_provisioning_extensions(cls, value: Any) -> dict[str, str] | None:
        """Keep the raw extension dict but normalise string values to strings."""
        if value is None:
            return None
        if isinstance(value, dict):
            return {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in value.items()}
        return None  # unexpected type; Pydantic will reject

    @property
    def automatic_provisioning(self) -> AutomaticProvisioning | None:
        """Return the decoded AUTOMATIC_PROVISIONING payload, if present."""
        raw = (self.ProductModelExtensions or {}).get("AUTOMATIC_PROVISIONING")
        if not raw:
            return None
        try:
            return AutomaticProvisioning.model_validate_json(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            return None


class Zone(BaseModel):
    ZoneId: str
    ZoneName: str
    HubId: str
    ZoneType: str
    RoomType: str | None = None
    AppName: str | None = None
    Icon: str | None = None
    IconColor: str | None = None
    Appliances: list[Appliance] = Field(default_factory=list)


class Hub(BaseModel):
    HubId: str
    Name: str | None = Field(None, alias="HubName")
    FriendlyName: str | None = None
    SecurityCode: str | None = None
    AddressLine1: str | None = None
    AddressLine2: str | None = None
    TownCity: str | None = None
    Postcode: str | None = None
    County: str | None = None
    Country: str | None = None
    Latitude: float | None = None
    Longitude: float | None = None
    HubRegistrationDate: datetime | None = None
    InstallationDate: datetime | None = None
    LastTelemDate: datetime | None = None
    TimeZoneId: int | None = None
    TimeZoneName: str | None = None
    NumberOfZones: int | None = None
    NumberOfAppliances: int | None = None
    IsServiceModeEnabled: bool | None = None
    FirmwareVersion: str | None = None
    ConnectionState: int | None = None
    HubType: str | None = None
    BluetoothName: str | None = None
    PrimaryUserEmail: str | None = None
    IsDefault: bool | None = None
    RoleName: str | None = None


class TimerPeriod(BaseModel):
    DayOfWeek: int
    StartTime: str  # Kept as str for easy JSON serialization
    EndTime: str
    Temperature: float

    @property
    def start_time_obj(self) -> time | None:
        """Parse StartTime as a time object (None if malformed)."""
        try:
            return datetime.strptime(self.StartTime, "%H:%M:%S").time()
        except (ValueError, TypeError):
            return None

    @property
    def end_time_obj(self) -> time | None:
        """Parse EndTime as a time object (None if malformed)."""
        try:
            return datetime.strptime(self.EndTime, "%H:%M:%S").time()
        except (ValueError, TypeError):
            return None


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
    ActiveSetPointTemperature: float | None = None
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

    @property
    def mode_flags(self) -> ApplianceModeFlag:
        """Return ``ApplianceModes`` as a typed flag set."""
        if self.ApplianceModes is None:
            return ApplianceModeFlag.NONE
        return ApplianceModeFlag(self.ApplianceModes)

    @property
    def is_boost_active(self) -> bool:
        """True when boost duration is set or the boost mode bit is present."""
        if self.BoostDuration is not None and self.BoostDuration > 0:
            return True
        return bool(self.mode_flags & ApplianceModeFlag.BOOST)

    @property
    def is_away_active(self) -> bool:
        """True when away fields indicate an active away session."""
        if self.AwayDateTime and self.AwayDateTime not in ("", "0001-01-01T00:00:00"):
            return True
        return bool(self.mode_flags & ApplianceModeFlag.AWAY)


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


class TsiEnergyReport(BaseModel):
    """Response from `POST /Reports/GetTsiEnergyReportDataForHub`.

    The cloud returns one telemetry bucket per appliance registered to the hub.
    Each bucket is a list of points whose individual shape is undocumented and
    appears to vary by firmware; entries are normalised by
    :func:`dimplex_controller.telemetry.parse_telemetry_points` so callers do
    not have to know the wire format.
    """

    HubId: str
    ApplianceTelemetryData: dict[str, list] = Field(default_factory=dict)


# `TsiReportType` integer values understood by the API. We do not know the
# canonical mapping; these are observed in traffic captures.
TSI_REPORT_TYPE_ENERGY = 1
