"""Appliance capability matrix derived from model, provisioning, and status.

Clients (Home Assistant climate, CLIs, etc.) should gate UI and control paths
with these flags rather than hard-coding product assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import AWAY_TEMP_MAX, AWAY_TEMP_MIN, FROST_TEMPERATURE, MODE_TEMP_MAX, MODE_TEMP_MIN
from .models import Appliance, ApplianceStatus, AutomaticProvisioning, ProductModel

# Default boost lengths (minutes) offered by the mobile app for most heaters.
DEFAULT_BOOST_DURATIONS: tuple[int, ...] = (30, 60, 120, 180)
DEFAULT_BOOST_MINUTES = 60


@dataclass(frozen=True)
class ApplianceCapabilities:
    """Structured capability flags for one appliance.

    Flags are best-effort: when status/product metadata is incomplete the
    library prefers enabling known cloud control paths (boost/away/OWD) so
    users are not locked out of working RPCs.

    One flag is weaker than the rest and must not be used as a gate:
    :attr:`energy_meter` is a *family hint* derived from the nameplate, so it is
    true for essentially every appliance with a rated power. When the question is
    "has this appliance ever reported energy?", ask the telemetry —
    :func:`dimplex_controller.reported_energy`, or
    :func:`dimplex_controller.summarise_energy` when the totals are wanted too
    (dimplex-controller-py#113).
    """

    boost: bool = True
    away: bool = True
    advance: bool = True
    open_window: bool = True
    eco_start: bool = True
    setback_read: bool = True
    setback_write: bool = True  # POST /RemoteControl/SetSetbackTemperature
    frost: bool = True  # ApplianceModeFlag.FROST_PROTECT (the app's "off")
    timer: bool = True
    # POST /RemoteControl/SetApplianceSetpointTemperature — the non-destructive
    # setpoint path. Preferred over rewriting the schedule via SetTimerMode,
    # which Quantum rejects with HTTP 403.
    setpoint_write: bool = True
    # Family hint, not proof of metering — see the class docstring before gating on it.
    energy_meter: bool = False
    storage: bool = False
    hot_water: bool = False
    heat_pump: bool = False
    hygiene: bool = False
    climate: bool = True
    min_temp: float = MODE_TEMP_MIN
    max_temp: float = MODE_TEMP_MAX
    # Away is the one carousel with its own bounds: it shares the 7 °C floor but
    # stops at 18 °C rather than 30 °C (dimplex-controller-py#98). Consumers
    # should gate the Away picker on these rather than on min_temp/max_temp.
    away_min_temp: float = AWAY_TEMP_MIN
    away_max_temp: float = AWAY_TEMP_MAX
    frost_temp: float = FROST_TEMPERATURE
    default_boost_minutes: int = DEFAULT_BOOST_MINUTES
    boost_durations: tuple[int, ...] = DEFAULT_BOOST_DURATIONS

    def climate_presets(self) -> list[str]:
        """Return HA-style climate preset keys supported by this appliance."""
        presets = ["comfort"]
        if self.boost:
            presets.append("boost")
        if self.away:
            presets.append("away")
        if self.eco_start:
            presets.append("eco")
        return presets

    def as_dict(self) -> dict[str, Any]:
        """JSON-serialisable snapshot (for diagnostics / logging)."""
        return {
            "boost": self.boost,
            "away": self.away,
            "advance": self.advance,
            "open_window": self.open_window,
            "eco_start": self.eco_start,
            "setback_read": self.setback_read,
            "setback_write": self.setback_write,
            "frost": self.frost,
            "timer": self.timer,
            "setpoint_write": self.setpoint_write,
            "energy_meter": self.energy_meter,
            "storage": self.storage,
            "hot_water": self.hot_water,
            "heat_pump": self.heat_pump,
            "hygiene": self.hygiene,
            "climate": self.climate,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "away_min_temp": self.away_min_temp,
            "away_max_temp": self.away_max_temp,
            "frost_temp": self.frost_temp,
            "default_boost_minutes": self.default_boost_minutes,
            "boost_durations": list(self.boost_durations),
            "climate_presets": self.climate_presets(),
        }


def _type_tokens(appliance: Appliance | None, product: ProductModel | None) -> str:
    parts: list[str] = []
    if appliance is not None:
        for attr in ("ApplianceType", "ApplianceModel", "FriendlyName"):
            value = getattr(appliance, attr, None)
            if value:
                parts.append(str(value))
    if product is not None:
        for attr in ("ProductTypeName", "ProductModelName"):
            value = getattr(product, attr, None)
            if value:
                parts.append(str(value))
    return " ".join(parts).lower()


def _provisioning(appliance: Appliance | None, product: ProductModel | None) -> AutomaticProvisioning | None:
    if appliance is not None:
        prov = appliance.automatic_provisioning
        if prov is not None:
            return prov
    if product is not None:
        return product.automatic_provisioning
    return None


def capabilities_for(
    appliance: Appliance | None = None,
    *,
    status: ApplianceStatus | None = None,
    product: ProductModel | None = None,
) -> ApplianceCapabilities:
    """Derive capability flags for an appliance.

    Sources (in roughly increasing specificity):

    * product catalogue / type name heuristics
    * ``AUTOMATIC_PROVISIONING`` (rated power, storage)
    * live overview fields (boost/away/OWD/setback/hot water)

    When a status field is present (including ``False`` / ``0``) the related
    feature is treated as supported. Missing fields leave defaults (generally
    enabled for control paths the cloud exposes generically).
    """
    tokens = _type_tokens(appliance, product)
    prov = _provisioning(appliance, product)

    storage = False
    energy_meter = False
    hot_water = False
    heat_pump = False
    if prov is not None:
        if prov.charge_capacity is not None and prov.charge_capacity > 0:
            storage = True
        if prov.rated_power is not None and prov.rated_power > 0:
            energy_meter = True  # metered family often has TSI history too

    if any(k in tokens for k in ("quantum", "storage", "qrad", "charge")):
        storage = True
        energy_meter = True
    if any(k in tokens for k in ("hot water", "hotwater", "cylinder", "dhw", "waterheater")):
        hot_water = True
    if any(k in tokens for k in ("ashw", "heat pump", "heatpump")):
        heat_pump = True
        hot_water = True

    if status is not None and status.AvailableHotWater is not None:
        hot_water = True

    # A cylinder reports its *water* target in ActiveSetPointTemperature (45 °C
    # on a live ASHW cylinder), so only a room temperature makes it room climate.
    # Without one, the room-heater features default to off — a live cylinder
    # sends null for every one of them — unless its status reports them.
    climate = not hot_water or (status is not None and status.RoomTemperature is not None)

    boost = climate
    away = climate
    advance = True
    open_window = climate
    eco_start = climate
    setback_read = climate
    frost = climate
    timer = True

    if status is not None:
        if status.BoostDuration is not None or status.BoostTemperature is not None:
            boost = True
        if status.AwayDateTime is not None or status.AwayTemperature is not None:
            away = True
        if status.OpenWindowEnabled is not None:
            open_window = True
        if status.EcoStartEnabled is not None:
            eco_start = True
        if status.SetbackEnabled is not None or status.SetbackTemperature is not None:
            setback_read = True

    # Advance only means something for a scheduled room heater; a cylinder has
    # no "next comfort period" to jump to.
    if hot_water and not climate:
        advance = False

    return ApplianceCapabilities(
        boost=boost,
        away=away,
        advance=advance,
        open_window=open_window,
        eco_start=eco_start,
        setback_read=setback_read,
        setback_write=climate,
        frost=frost,
        timer=timer,
        # The room setpoint endpoint; cylinders have their own (Set*TemperatureHwc).
        setpoint_write=climate,
        energy_meter=energy_meter,
        storage=storage,
        hot_water=hot_water,
        heat_pump=heat_pump,
        hygiene=hot_water,
        climate=climate,
    )
