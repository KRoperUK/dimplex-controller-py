"""Dimplex Controller Client.

Unofficial async Python client for the Glen Dimplex Heating & Ventilation
(GDHV) cloud API. Not affiliated with, endorsed by, or supported by Dimplex
or the Glen Dimplex Group: the protocol was recovered by reverse-engineering
the official Dimplex Control Android app, so Dimplex may change or withdraw
it without notice. See :class:`~dimplex_controller.client.DimplexControl` for the entry
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
from .const import (
    AWAY_TEMP_MAX,
    AWAY_TEMP_MIN,
    DEFAULT_AWAY_TEMPERATURE,
    DEFAULT_BOOST_TEMPERATURE,
    FROST_TEMPERATURE,
    MODE_TEMP_MAX,
    MODE_TEMP_MIN,
    NO_SETPOINT_SENTINEL,
    NULL_DATETIME,
)
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
    ApplianceModeStatus,
    ApplianceStatus,
    AutomaticProvisioning,
    Hub,
    HygieneFrequency,
    ProductModel,
    ScheduleProfile,
    SetbackStatus,
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
    "ApplianceModeStatus",
    "HygieneFrequency",
    "ScheduleProfile",
    "SetbackStatus",
    "TimerMode",
    "TimerModeSettings",
    "TimerPeriod",
    "AutomaticProvisioning",
    "ProductModel",
    "TsiEnergyReport",
    "DEFAULT_AWAY_TEMPERATURE",
    "DEFAULT_BOOST_TEMPERATURE",
    "AWAY_TEMP_MIN",
    "AWAY_TEMP_MAX",
    "FROST_TEMPERATURE",
    "MODE_TEMP_MIN",
    "MODE_TEMP_MAX",
    "NO_SETPOINT_SENTINEL",
    "NULL_DATETIME",
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
