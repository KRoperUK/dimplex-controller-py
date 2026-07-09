"""Telemetry parsing for the Dimplex Reports API.

The response from ``POST /Reports/GetTsiEnergyReportDataForHub`` contains
``ApplianceTelemetryData``: a dict keyed by appliance id, with one list of
``telemetry points`` per appliance. The shape of each point is not documented
and varies between firmware versions, so we normalise whatever the cloud
sends into ``(timestamp, value)`` tuples.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

# Keys the cloud has been observed using, in priority order. The first match
# wins. Case-insensitive lookup is done by lowercasing the dict before
# scanning, so callers do not have to worry about casing.
_DEFAULT_TIMESTAMP_KEYS = (
    "timestamp",
    "time",
    "ts",
    "t",
    "datetime",
    "date",
    "from",
    "start",
)
_DEFAULT_VALUE_KEYS = (
    "t1",
    "value",
    "kwh",
    "energy",
    "consumption",
    "energykwh",
    "amount",
    "v",
    # Fallback for appliances that only report the secondary register.
    "t2",
)

# Secondary energy register observed for some Quantum appliances. Points may
# contain both ``T1`` and ``T2`` in the same payload.
VALUE_KEY_T2 = (
    "t2",
    "value2",
    "kwh2",
    "energy2",
)


def _coerce_timestamp(raw: Any) -> datetime | None:
    """Best-effort conversion of ``raw`` into a ``datetime``.

    Accepts ``datetime`` instances, ISO-8601 strings, and Unix epoch numbers
    (seconds or milliseconds). Returns ``None`` if the value cannot be parsed.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, int | float):
        ts = float(raw)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _coerce_value(raw: Any) -> float | None:
    """Best-effort conversion of ``raw`` into a ``float``."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip())
        except ValueError:
            return None
    return None


def _iter_items(point: Any) -> Iterable[tuple[str, Any]] | None:
    """Yield ``(key, value)`` pairs from a dict-like ``point``.

    Returns ``None`` for non-dict points so the caller can fall through to the
    list / scalar branches.
    """
    if not isinstance(point, dict):
        return None
    lower = {str(k).lower(): v for k, v in point.items()}
    return ((k, lower.get(k)) for k in (*_DEFAULT_TIMESTAMP_KEYS, *_DEFAULT_VALUE_KEYS, *VALUE_KEY_T2))


def parse_telemetry_points(
    points: Any,
    *,
    value_keys: tuple[str, ...] | None = None,
) -> list[tuple[datetime | None, float]]:
    """Normalise a list of telemetry points into ``(timestamp, value)`` pairs.

    Each entry in ``points`` may be:

    * a ``dict`` with one of the recognised timestamp/value keys
    * a 2-element ``[timestamp, value]`` list or tuple
    * a bare scalar (treated as a cumulative value at an unknown timestamp)

    ``value_keys`` overrides the value-key priority list. Use
    :data:`VALUE_KEY_T2` to extract the secondary energy register when the
    cloud returns both ``T1`` and ``T2`` in the same payload.

    Unparseable entries are silently skipped. The order of the input list is
    preserved.
    """
    if not isinstance(points, list):
        return []

    value_key_order = value_keys if value_keys is not None else _DEFAULT_VALUE_KEYS
    timestamp_keys = _DEFAULT_TIMESTAMP_KEYS

    out: list[tuple[datetime | None, float]] = []
    for point in points:
        ts: datetime | None = None
        value: float | None = None

        items = _iter_items(point)
        if items is not None:
            for key, raw in items:
                if key in timestamp_keys and ts is None:
                    ts = _coerce_timestamp(raw)
                elif key in value_key_order and value is None:
                    value = _coerce_value(raw)
        elif isinstance(point, list | tuple) and len(point) == 2:
            ts = _coerce_timestamp(point[0])
            value = _coerce_value(point[1])
        else:
            value = _coerce_value(point)

        if value is None:
            continue
        out.append((ts, value))
    return out
