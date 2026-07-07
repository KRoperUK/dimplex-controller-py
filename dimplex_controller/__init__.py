"""Dimplex Controller Client."""

from .client import DimplexControl
from .exceptions import DimplexApiError, DimplexAuthError, DimplexConnectionError, DimplexError
from .models import Appliance, ApplianceModeSettings, ApplianceStatus, Hub, TsiEnergyReport, Zone
from .telemetry import parse_telemetry_points

__all__ = [
    "DimplexControl",
    "Hub",
    "Zone",
    "Appliance",
    "ApplianceStatus",
    "ApplianceModeSettings",
    "TsiEnergyReport",
    "parse_telemetry_points",
    "DimplexError",
    "DimplexApiError",
    "DimplexAuthError",
    "DimplexConnectionError",
]
