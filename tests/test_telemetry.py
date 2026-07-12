"""Tests for the telemetry parser."""

from datetime import datetime, timezone

import pytest

from dimplex_controller.telemetry import VALUE_KEY_T2, parse_telemetry_points


def test_empty_and_bad_input():
    """None / non-list input yields no points."""
    assert parse_telemetry_points(None) == []
    assert parse_telemetry_points({}) == []
    assert parse_telemetry_points("nope") == []


def test_dict_with_known_keys():
    """A point dict with timestamp + value is normalised."""
    points = [
        {"timestamp": "2026-06-01T00:00:00Z", "value": 0.25},
        {"Timestamp": "2026-06-01T01:00:00Z", "Value": 0.5},
    ]
    out = parse_telemetry_points(points)
    assert len(out) == 2
    assert out[0][0] == datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert out[0][1] == 0.25
    assert out[1][0] == datetime(2026, 6, 1, 1, tzinfo=timezone.utc)
    assert out[1][1] == 0.5


def test_dict_with_alternate_keys():
    """Alternate timestamp/value keys (e.g. kWh, ts) are recognised."""
    points = [{"ts": "2026-06-01T00:00:00Z", "kWh": 1.5}]
    out = parse_telemetry_points(points)
    assert out[0][0] == datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert out[0][1] == 1.5


def test_pair_list():
    """A 2-element list is treated as (timestamp, value)."""
    out = parse_telemetry_points([["2026-06-01T00:00:00Z", 0.1]])
    assert out[0][0] == datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert out[0][1] == 0.1


def test_scalar():
    """A bare scalar becomes a value with no timestamp."""
    out = parse_telemetry_points([0.42])
    assert out == [(None, 0.42)]


def test_epoch_seconds_and_milliseconds():
    """Unix epochs in seconds and milliseconds are both accepted."""
    out = parse_telemetry_points(
        [
            {"timestamp": 1717200000, "value": 0.1},
            {"timestamp": 1717200000000, "value": 0.2},
        ]
    )
    assert out[0][0] == datetime.fromtimestamp(1717200000, tz=timezone.utc)
    assert out[1][0] == datetime.fromtimestamp(1717200000, tz=timezone.utc)


def test_bad_entries_skipped_but_partial_kept():
    """A bad timestamp keeps the value; entries with no value at all are dropped."""
    points = [
        {"timestamp": "2026-06-01T00:00:00Z", "value": 0.1},
        {"timestamp": "2026-06-01T01:00:00Z"},  # no value -> dropped
        {"value": 0.2},  # no timestamp -> (None, 0.2)
        {"timestamp": "not-a-date", "value": 0.3},  # bad ts -> (None, 0.3)
        "garbage",  # no value -> dropped
        ["only-one"],  # not 2-element -> no value -> dropped
    ]
    out = parse_telemetry_points(points)
    assert out == [
        (datetime(2026, 6, 1, tzinfo=timezone.utc), 0.1),
        (None, 0.2),
        (None, 0.3),
    ]


def test_bool_is_not_a_number():
    """``True`` / ``False`` are not silently coerced to 1.0 / 0.0."""
    out = parse_telemetry_points([{"timestamp": "2026-06-01T00:00:00Z", "value": True}])
    assert out == []


def test_string_value_coerced():
    """String values are coerced when possible."""
    out = parse_telemetry_points([{"timestamp": "2026-06-01T00:00:00Z", "value": " 0.75 "}])
    assert out[0][1] == 0.75


@pytest.mark.parametrize("bad", [None, "not-a-date", ""])
def test_bad_timestamp_yields_none(bad):
    """An unparseable timestamp becomes ``None`` (value is still kept)."""
    out = parse_telemetry_points([{"timestamp": bad, "value": 0.1}])
    assert out == [(None, 0.1)]


def test_t1_and_ts_keys():
    """Real Dimplex API points use ``TS`` for Unix-epoch timestamps and
    ``T1`` or ``ST`` for the kWh value."""
    out = parse_telemetry_points(
        [
            {"TS": 1767225600, "T1": 7.46},
            {"TS": 1767312000, "T1": 8.02},
            {"TS": 1767398400, "T1": 7.91},
        ]
    )
    assert out == [
        (datetime(2026, 1, 1, tzinfo=timezone.utc), 7.46),
        (datetime(2026, 1, 2, tzinfo=timezone.utc), 8.02),
        (datetime(2026, 1, 3, tzinfo=timezone.utc), 7.91),
    ]


def test_st_and_ts_keys():
    """QRAD050F / QRAD075F reports use ``ST`` as the energy value key."""
    out = parse_telemetry_points(
        [
            {"TS": 1783773600, "ST": 0.06},
            {"TS": 1783580400, "ST": 0.09},
            {"TS": 1783000800, "ST": 0.08},
        ]
    )
    assert out == [
        (datetime(2026, 7, 11, 12, 40, 0, tzinfo=timezone.utc), 0.06),
        (datetime(2026, 7, 9, 7, 0, 0, tzinfo=timezone.utc), 0.09),
        (datetime(2026, 7, 2, 14, 0, 0, tzinfo=timezone.utc), 0.08),
    ]


def test_t2_energy_register():
    """The secondary energy register ``T2`` can be extracted independently."""
    out = parse_telemetry_points(
        [
            {"TS": 1767225600, "T1": 7.46, "T2": 0.36},
            {"TS": 1767312000, "T1": 8.02, "T2": 0.18},
            {"TS": 1767398400, "T1": 7.91},
        ],
        value_keys=VALUE_KEY_T2,
    )
    assert out == [
        (datetime(2026, 1, 1, tzinfo=timezone.utc), 0.36),
        (datetime(2026, 1, 2, tzinfo=timezone.utc), 0.18),
    ]


def test_t2_only_points():
    """When only ``T2`` is present, default parsing falls back to it."""
    out = parse_telemetry_points(
        [
            {"TS": 1767225600, "T2": 0.36},
        ]
    )
    assert out == [(datetime(2026, 1, 1, tzinfo=timezone.utc), 0.36)]
