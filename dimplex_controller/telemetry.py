"""Telemetry parsing for the Dimplex Reports API.

The response from ``POST /Reports/GetTsiEnergyReportDataForHub`` contains
``ApplianceTelemetryData``: a dict keyed by appliance id, with one list of
``telemetry points`` per appliance. The shape of each point is not documented
and varies between firmware versions, so we normalise whatever the cloud
sends into ``(timestamp, value)`` tuples.

Real-world payloads have been observed using ``TS`` (Unix-epoch timestamp)
with either ``T1`` or ``ST`` as the energy value key. Some appliances also
report a secondary register ``T2`` on the same point.

**T1 and T2 must stay separate.** They are believed to be tariff periods
(e.g. peak / off-peak), not dual samples of the same meter. Never sum T1+T2
into a single "total energy" figure, and never fall back from T1 parsing to
T2 values (or vice versa).

Important cloud semantics (live-verified):

* With ``IncludePreviousPeriod=true`` the cloud often returns **the full
  available daily history** (from first telem / install), not just the
  ``StartDate``→``EndDate`` window.
* With ``IncludePreviousPeriod=false`` and idle heaters, lists may be empty.
* Points are typically **one kWh sample per calendar day**, not a continuous
  cumulative counter.

Use :func:`summarise_energy` for the two product totals **per register**:

* ``daily`` — kWh for the local calendar day (from local midnight)
* ``lifetime`` — sum of all parsed points for that register only
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone, tzinfo
from typing import Any, Literal

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

# Primary energy register (T1 / single-register appliances). Intentionally
# excludes ``t2`` so peak/off-peak series are never mixed.
VALUE_KEY_T1 = (
    "t1",
    "st",  # Observed on QRAD050F / QRAD075F energy reports (see dimplex-controller-hass #27).
    "value",
    "kwh",
    "energy",
    "consumption",
    "energykwh",
    "amount",
    "v",
)

# Secondary energy register (T2) observed for some Quantum appliances.
# Points may contain both ``T1`` and ``T2`` in the same payload — parse each
# with its own key list; do not combine.
VALUE_KEY_T2 = (
    "t2",
    "value2",
    "kwh2",
    "energy2",
)

# Backwards-compatible alias for the primary register key list.
_DEFAULT_VALUE_KEYS = VALUE_KEY_T1

EnergyMode = Literal["daily", "lifetime", "window"]
TelemetryPoint = tuple[datetime | None, float]


@dataclass(frozen=True, slots=True)
class EnergySummary:
    """Aggregated energy for a set of telemetry points.

    Attributes:
        total_kwh: Sum of point values in kWh.
        point_count: Number of points included in the total.
        start: Earliest timestamp among included points (or day start for daily).
        end: Latest timestamp among included points (or None).
        mode: Aggregation mode used to produce this summary.
    """

    total_kwh: float
    point_count: int
    start: datetime | None
    end: datetime | None
    mode: EnergyMode


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


def _iter_items(point: Any, value_keys: tuple[str, ...]) -> Iterable[tuple[str, Any]] | None:
    """Yield ``(key, value)`` pairs from a dict-like ``point``.

    Returns ``None`` for non-dict points so the caller can fall through to the
    list / scalar branches.
    """
    if not isinstance(point, dict):
        return None
    lower = {str(k).lower(): v for k, v in point.items()}
    return ((k, lower.get(k)) for k in (*_DEFAULT_TIMESTAMP_KEYS, *value_keys))


def parse_telemetry_points(
    points: Any,
    *,
    value_keys: tuple[str, ...] | None = None,
) -> list[TelemetryPoint]:
    """Normalise a list of telemetry points into ``(timestamp, value)`` pairs.

    Each entry in ``points`` may be:

    * a ``dict`` with one of the recognised timestamp/value keys
    * a 2-element ``[timestamp, value]`` list or tuple
    * a bare scalar (treated as a cumulative value at an unknown timestamp)

    ``value_keys`` overrides the value-key priority list. Defaults to
    :data:`VALUE_KEY_T1` (primary register only). Use :data:`VALUE_KEY_T2` to
    extract the secondary register. T1 and T2 must be parsed separately —
    never pass a key list that mixes both if you need tariff-accurate totals.

    Unparseable entries are silently skipped. The order of the input list is
    preserved.
    """
    if not isinstance(points, list):
        return []

    value_key_order = value_keys if value_keys is not None else VALUE_KEY_T1
    timestamp_keys = _DEFAULT_TIMESTAMP_KEYS

    out: list[TelemetryPoint] = []
    for point in points:
        ts: datetime | None = None
        value: float | None = None

        items = _iter_items(point, value_key_order)
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


def _ensure_aware(ts: datetime, default_tz: tzinfo) -> datetime:
    """Return ``ts`` with a timezone; naive datetimes are assumed ``default_tz``."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=default_tz)
    return ts


def local_midnight(now: datetime, tz: tzinfo) -> datetime:
    """Return the start of the local calendar day containing ``now``."""
    local = _ensure_aware(now, tz).astimezone(tz)
    return datetime.combine(local.date(), time.min, tzinfo=tz)


def filter_telemetry_points(
    points: Sequence[TelemetryPoint],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    on_date: date | None = None,
    tz: tzinfo = timezone.utc,
) -> list[TelemetryPoint]:
    """Filter parsed points by absolute window and/or local calendar date.

    * ``start`` / ``end`` are inclusive bounds (compared in UTC).
    * ``on_date`` keeps points whose local date (in ``tz``) equals that day.
    Points with a missing timestamp are dropped when any filter is active.
    """
    if start is None and end is None and on_date is None:
        return list(points)

    start_utc = _ensure_aware(start, tz).astimezone(timezone.utc) if start is not None else None
    end_utc = _ensure_aware(end, tz).astimezone(timezone.utc) if end is not None else None

    out: list[TelemetryPoint] = []
    for ts, value in points:
        if ts is None:
            continue
        aware = _ensure_aware(ts, timezone.utc)
        if start_utc is not None and aware < start_utc:
            continue
        if end_utc is not None and aware > end_utc:
            continue
        if on_date is not None and aware.astimezone(tz).date() != on_date:
            continue
        out.append((aware, value))
    return out


def summarise_energy(
    points: Sequence[TelemetryPoint] | Any,
    *,
    mode: EnergyMode = "lifetime",
    now: datetime | None = None,
    tz: tzinfo = timezone.utc,
    start: datetime | None = None,
    end: datetime | None = None,
    value_keys: tuple[str, ...] | None = None,
) -> EnergySummary:
    """Aggregate telemetry into a daily, lifetime, or custom-window total.

    ``points`` may be raw cloud payloads or already-parsed
    :data:`TelemetryPoint` tuples. When raw, they are passed through
    :func:`parse_telemetry_points` first.
    """
    parsed: list[TelemetryPoint]
    if (
        isinstance(points, Sequence)
        and not isinstance(points, str | bytes)
        and points
        and isinstance(points[0], tuple)
        and len(points[0]) == 2
    ):
        parsed = list(points)  # type: ignore[arg-type]
    else:
        parsed = parse_telemetry_points(points, value_keys=value_keys)

    ref_now = now if now is not None else datetime.now(timezone.utc)
    ref_now = _ensure_aware(ref_now, tz)

    if mode == "daily":
        day = ref_now.astimezone(tz).date()
        selected = filter_telemetry_points(parsed, on_date=day, tz=tz)
        day_start = local_midnight(ref_now, tz)
        timestamps = [ts for ts, _ in selected if ts is not None]
        total = sum(v for _, v in selected)
        return EnergySummary(
            total_kwh=round(total, 3),
            point_count=len(selected),
            start=day_start,
            end=max(timestamps) if timestamps else None,
            mode="daily",
        )

    # lifetime — include every parseable point; window — optional start/end filter
    selected = filter_telemetry_points(parsed, start=start, end=end, tz=tz) if mode == "window" else list(parsed)

    timestamps = [ts for ts, _ in selected if ts is not None]
    total = sum(v for _, v in selected)
    return EnergySummary(
        total_kwh=round(total, 3),
        point_count=len(selected),
        start=min(timestamps) if timestamps else None,
        end=max(timestamps) if timestamps else None,
        mode=mode,
    )
