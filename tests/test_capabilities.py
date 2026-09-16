"""Tests for appliance capability derivation."""

from dimplex_controller.capabilities import ApplianceCapabilities, capabilities_for
from dimplex_controller.models import Appliance, ApplianceStatus, ProductModel


def test_default_capabilities_enable_common_controls():
    """Without metadata, expose known cloud control paths."""
    caps = capabilities_for()
    assert caps.boost is True
    assert caps.away is True
    assert caps.advance is True
    assert caps.open_window is True
    assert "boost" in caps.climate_presets()
    # SetSetbackTemperature and SetApplianceSetpointTemperature both exist.
    assert caps.setback_write is True
    assert caps.setpoint_write is True
    # The app's mode carousels are 7–30 °C.
    assert caps.min_temp == 7.0
    assert caps.max_temp == 30.0
    # Away is the exception, with its own narrower ceiling.
    assert caps.away_min_temp == 7.0
    assert caps.away_max_temp == 18.0
    assert caps.frost_temp == 7.0


def test_as_dict_includes_away_bounds():
    """The Away bounds travel with the serialised capability snapshot."""
    data = ApplianceCapabilities().as_dict()
    assert data["away_min_temp"] == 7.0
    assert data["away_max_temp"] == 18.0
    # The general carousel range is untouched.
    assert data["min_temp"] == 7.0
    assert data["max_temp"] == 30.0


def test_quantum_storage_from_type_name():
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Quantum",
        ApplianceModel="QM100RF",
        ZoneId="z1",
        FriendlyName="Hall",
        ZoneName="Hall",
    )
    caps = capabilities_for(appliance)
    assert caps.storage is True
    assert caps.energy_meter is True
    assert caps.climate is True


def test_storage_from_provisioning():
    appliance = Appliance(
        ApplianceId="a1",
        ApplianceType="Heater",
        ApplianceModel="X",
        ZoneId="z1",
        FriendlyName="Room",
        ZoneName="Room",
        ProductModelExtensions={
            "AUTOMATIC_PROVISIONING": '{"ratedPower":1.5,"chargeCapacity":12.0}',
        },
    )
    caps = capabilities_for(appliance)
    assert caps.storage is True
    assert caps.energy_meter is True


def test_status_marks_features_and_hot_water():
    status = ApplianceStatus(
        HubId="h1",
        ApplianceId="a1",
        ZoneId="z1",
        BoostDuration=30,
        OpenWindowEnabled=False,
        EcoStartEnabled=True,
        AvailableHotWater=45.0,
        RoomTemperature=None,
        ActiveSetPointTemperature=None,
    )
    caps = capabilities_for(status=status)
    assert caps.boost is True
    assert caps.open_window is True
    assert caps.eco_start is True
    assert caps.hot_water is True


def test_product_catalogue_type_name():
    product = ProductModel(ProductModelName="Something", ProductTypeName="Hot Water Cylinder")
    caps = capabilities_for(product=product)
    assert caps.hot_water is True
    assert caps.climate is False
    assert caps.hygiene is True
    # No comfort schedule to advance into on a cylinder.
    assert caps.advance is False


def test_heat_pump_cylinder_detected():
    product = ProductModel(ProductModelName="ASHW Cylinder 210", ProductTypeName="HeatPumpHWC")
    caps = capabilities_for(product=product)
    assert caps.heat_pump is True
    assert caps.hot_water is True


def test_as_dict_includes_presets():
    caps = ApplianceCapabilities(boost=False, away=True, eco_start=False)
    data = caps.as_dict()
    assert data["boost"] is False
    assert data["climate_presets"] == ["comfort", "away"]
