# Research notes: live power and frost/setback writes

Tracking issues: library #53 (live power), #52 (frost/setback writes).

## Live / instantaneous power

**Current state (2026-07):** The cloud exposes:

- Daily TSI energy history (`GetTsiEnergyReportDataForHub`) → kWh points, not watts
- Static rated power from `AUTOMATIC_PROVISIONING.ratedPower` (kW nameplate)

**Not observed:** a near-real-time wattage field on appliance overview or a dedicated power endpoint in captured mobile traffic.

**Next capture:** during a heating season with the official app open while an appliance is actively heating, filter for `Power`, `Watt`, `Consumption`, `Current` in request paths and JSON keys.

**HA interim:** estimated power diagnostic (rated_power × heating fraction) — not a real meter.

## Frost / setback write paths

**Readable today:**

- `ApplianceStatus.SetbackEnabled`, `SetbackEnabledInStatusFrame`, `SetbackTemperature`
- Timer mode `TimerMode.FROST_PROTECTION = 2` via `SetTimerMode` / `get_appliance_features`

**Write:**

- Frost: likely achievable by `set_mode(..., TimerMode.FROST_PROTECTION)` (timer mode write already implemented). Confirm against app behaviour before documenting as frost control.
- Setback enable/temperature: **no confirmed dedicated RPC** in captures. Capability matrix marks `setback_write=False` until evidence lands.

## Capture checklist

1. Toggle setback / frost in the official app with MITM recording.
2. Note endpoint, method, JSON body (redact tokens).
3. Open a follow-up implementation PR with client methods + tests.
