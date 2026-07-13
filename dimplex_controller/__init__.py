"""Dimplex Controller Client."""

from .auth import TokenBundle
from .client import DimplexControl
from .exceptions import (
    DimplexApiError,
    DimplexAuthError,
    DimplexAuthInvalidCredentialsError,
    DimplexAuthInvalidGrantError,
    DimplexAuthParseError,
    DimplexAuthTransientError,
    DimplexConnectionError,
    DimplexError,
)
from .models import (
    Appliance,
    ApplianceModeFlag,
    ApplianceModeSettings,
    ApplianceStatus,
    AutomaticProvisioning,
    Hub,
    ProductModel,
    TimerMode,
    TimerModeSettings,
    TimerPeriod,
    TsiEnergyReport,
    Zone,
)
from .telemetry import (
    VALUE_KEY_T1,
    VALUE_KEY_T2,
    EnergySummary,
    filter_telemetry_points,
    parse_telemetry_points,
    summarise_energy,
)

__all__ = [
    "DimplexControl",
    "TokenBundle",
    "Hub",
    "Zone",
    "Appliance",
    "ApplianceStatus",
    "ApplianceModeSettings",
    "ApplianceModeFlag",
    "TimerMode",
    "TimerModeSettings",
    "TimerPeriod",
    "AutomaticProvisioning",
    "ProductModel",
    "TsiEnergyReport",
    "parse_telemetry_points",
    "filter_telemetry_points",
    "summarise_energy",
    "EnergySummary",
    "VALUE_KEY_T1",
    "VALUE_KEY_T2",
    "DimplexError",
    "DimplexApiError",
    "DimplexAuthError",
    "DimplexAuthInvalidGrantError",
    "DimplexAuthInvalidCredentialsError",
    "DimplexAuthParseError",
    "DimplexAuthTransientError",
    "DimplexConnectionError",
]
