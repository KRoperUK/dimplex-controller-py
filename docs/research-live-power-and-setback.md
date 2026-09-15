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

**Resolved (2026-09, APK 2.26.0 decompilation — see [decompiled-api-reference.md](decompiled-api-reference.md)):**

- **Frost** is a mode bit, not a timer mode: `SetApplianceMode` with
  `ApplianceModes = FrostProtect (32)`, `Status = 1`, `Temperature = 7`. This is
  also how the app turns a heater **off**. Implemented as
  `set_frost_protect()` / `turn_off()`. `set_mode(..., TimerMode.FROST_PROTECTION)`
  writes the schedule editor instead and returns **403 on Quantum**.
- **Setback** has a dedicated RPC after all:
  `POST /RemoteControl/SetSetbackTemperature` with
  `{ HubId, ApplianceIds[], Status: EStatus, Temperature: byte }`. Implemented as
  `set_setback_temperature()`; the capability matrix now reports
  `setback_write=True`. **Not yet validated on live hardware.**

**Readable today:**

- `ApplianceStatus.SetbackEnabled`, `SetbackEnabledInStatusFrame`, `SetbackTemperature`

**Remaining capture work:** confirm `SetSetbackTemperature` end-to-end on a live
appliance, and whether `EStatus.DSMMode` / `LocalFrequencyControlActive` are
accepted outside a DSM deployment.

## Capture checklist

1. Toggle setback / frost in the official app with MITM recording.
2. Note endpoint, method, JSON body (redact tokens).
3. Open a follow-up implementation PR with client methods + tests.
