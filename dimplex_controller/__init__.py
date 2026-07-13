"""Dimplex Controller Client.

Async Python client for the Glen Dimplex Heating & Ventilation (GDHV) cloud
API. See :class:`~dimplex_controller.client.DimplexControl` for the entry
point and :meth:`DimplexControl.get_appliance_overview` for the read path
used by the Home Assistant integration.

A note on the API: ``get_appliance_overview`` may return an empty list
with HTTP 200 when the requested appliances are offline. That is a
successful poll, not an error — use ``get_appliance_overview_map`` if you
need a stable id → status mapping.
"""

from .auth import TokenBundle, TokenListener
from .capabilities import ApplianceCapabilities, capabilities_for
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
    "TokenListener",
    "ApplianceCapabilities",
    "capabilities_for",
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
