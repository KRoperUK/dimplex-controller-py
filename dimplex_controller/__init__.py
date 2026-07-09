"""Dimplex Controller Client."""

from .client import DimplexControl
from .exceptions import DimplexApiError, DimplexAuthError, DimplexConnectionError, DimplexError
from .models import (
    Appliance,
    ApplianceModeSettings,
    ApplianceStatus,
    AutomaticProvisioning,
    Hub,
    TsiEnergyReport,
    Zone,
)
from .telemetry import VALUE_KEY_T2, parse_telemetry_points

__all__ = [
    "DimplexControl",
    "Hub",
    "Zone",
    "Appliance",
    "ApplianceStatus",
    "ApplianceModeSettings",
    "AutomaticProvisioning",
    "TsiEnergyReport",
    "parse_telemetry_points",
    "VALUE_KEY_T2",
    "DimplexError",
    "DimplexApiError",
    "DimplexAuthError",
    "DimplexConnectionError",
]
