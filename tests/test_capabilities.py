"""Tests for appliance capability derivation."""

from dimplex_controller.capabilities import ApplianceCapabilities, capabilities_for
from dimplex_controller.models import Appliance, ApplianceStatus, ProductModel


def test_default_capabilities_enable_common_controls():
    """Without metadata, expose known cloud control paths."""
    caps = capabilities_for()
    assert caps.boost is True
    assert caps.away is True
    assert caps.open_window is True
    assert "boost" in caps.climate_presets()
    assert caps.setback_write is False


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


def test_as_dict_includes_presets():
    caps = ApplianceCapabilities(boost=False, away=True, eco_start=False)
    data = caps.as_dict()
    assert data["boost"] is False
    assert data["climate_presets"] == ["comfort", "away"]
