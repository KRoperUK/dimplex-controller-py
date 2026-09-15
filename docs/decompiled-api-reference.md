# Decompiled API reference (Dimplex Control APK 2.26.0)

Ground-truth notes for the GDHV IoT cloud API, recovered by **decompiling the
official Android app**. Use this to verify/expand `dimplex_controller` against
what the app actually sends.

## Provenance

| | |
| --- | --- |
| App | **Dimplex Control** `com.Dimplex.DimplexControl` |
| Version | **2.26.0** (versionCode 83403) |
| Package | `.xapk` split bundle (base + `config.arm64_v8a`) |
| Framework | **.NET MAUI 9 (Xamarin)** — MonoVM + AOT |
| Assembly | `DimplexControl.dll` (5.8 MB IL) |
| How | `libassembly-store.so` → ELF `payload` section → `XABA` AssemblyStore → per-assembly `XALZ` (LZ4) → decompiled with ILSpy (`ilspycmd` 9.1) |
| Base URL | `https://mobileapi.gdhv-iot.com/api` (endpoints below are relative to this; the app prefixes them with `/api/`) |
| Auth | Azure AD B2C (MSAL, `Microsoft.Identity.Client`) — see `const.py` |

**Confirmation legend used throughout:**

- 📦 **APK 2.26.0** — behaviour is confirmed by the decompiled source of this exact app version.
- 🔬 **Live** — reconfirmed against a live **Quantum QM100RF** on 2026-09-15 (developer hardware).
- ❌ **not owned** — model-specific endpoint confirmed in the APK only; no hardware to validate.

---

## 1. Appliance mode flags — the important correction

The app's mode bitfield (`DimplexControl.Models.EApplianceModes`, `[Flags]`):

| Name | Value | | Name | Value |
| --- | --- | --- | --- | --- |
| `TimerMode` | `1` (0x01) | | `Manual` | `128` (0x80) |
| **`Boost`** | **`2` (0x02)** | | `Hygiene` | `256` (0x100) |
| **`Away`** | **`4` (0x04)** | | `Standalone` | `512` (0x200) |
| `Holiday` | `8` (0x08) | | `SafeMode` | `1024` (0x400) |
| **`Advance`** | **`16` (0x10)** | | `Shutdown` | `2048` (0x800) |
| **`FrostProtect`** | **`32` (0x20)** | | `Comms` | `4096` (0x1000) |
| `Eco` | `64` (0x40) | | `Normal` | `8192` (0x2000) |
| | | | `Standby` | `16384` (0x4000) |

> ⚠️ **`dimplex_controller` is wrong here.** `ApplianceModeFlag` uses `BOOST = 16`
> and `AWAY = 32`, but **16 is `Advance`** and **32 is `FrostProtect`**. That is
> the root cause of dimplex-controller-hass#163 (Away → Frost Protect, Boost →
> Advance). Correct values are **`Boost = 2`, `Away = 4`**. Status-frame parsing
> (`is_boost_active`/`is_away_active`) must check the same corrected bits.

Supporting enums:

```
Mode                { None,Timer,Boost,Holiday,Away,Normal,Hygiene,Mixed,Advance,Eco,Frost,Manual,Standby,HomeAllDay,OutAllDay,UserTimer,Standalone,Shutdown,SafeMode }
ApplianceModeStatus { Inactive = 0, Active = 1 }              # ApplianceModeSettings.Status
EStatus : byte      { Inactive=0, Active=1, DSMMode=2, LocalFrequencyControlActive=3 }  # setback status
EStatusTwo          { UserTimer = 0, HomeAllDay = 1, OutAllDay = 2 }
EFrequency : byte   { Off = 0, Daily = 1, Weekly = 7, Monthly = 28 }   # hygiene frequency
ApplianceTypes      { WaterHeater, Heating, QRad, Quantum, "Storage Heater", HeatPumpHWC = "ASHW Cylinder" }
```

### `SetApplianceMode` payload (`ApplianceModeSettings`)

`POST /RemoteControl/SetApplianceMode` — body `{ HubId, ApplianceIds[], Settings }`:

```
ApplianceModeSettings {
  EApplianceModes ApplianceModes   # which mode (see table)
  ApplianceModeStatus Status       # 1 = engage, 0 = clear
  short  Temperature               # target °C (integer)
  short  Time                      # BOOST duration in minutes
  DateTime Date                    # AWAY "away until" datetime
  EStatusTwo StatusTwo
  byte   NumberOfDays
  byte   Frequency                 # hygiene (EFrequency)
}
```

How the app builds each action (heating appliances — QRad / Quantum / Storage Heater):

| Action | `ApplianceModes` | `Status` | Other fields |
| --- | --- | --- | --- |
| **Boost on** | `Boost` (2) | Active | `Time` = minutes, `Temperature` |
| **Boost off** | `Boost` (2) | Inactive | — |
| **Away on** | `Away` (4) | Active | `Temperature`, `Date` = away-until (uses **Date**, not NumberOfDays) |
| **Away off** | `Away` (4) | Inactive | — |
| **Advance** | `Advance` (16) | Active (start) / Inactive (cancel) | `Temperature` = current/next period; **`255` for Quantum / Storage Heater** with no setback |
| **Frost ("off")** | `FrostProtect` (32) | Active | `Temperature` = 7 |
| **Manual** | `Manual` (128) | Active | `Temperature` |
| **Eco** | `Eco` (64) | Active | `Temperature` |

> The **`255` (0xFF)** Advance temperature for Quantum/Storage Heater is the same
> sentinel the cloud reports for `ActiveSetPointTemperature` when idle — it means
> "no explicit setpoint, follow schedule". `dimplex-controller-hass` now filters it
> (PR #165).

**Temperature ranges (from the app's pickers, `UpdateTempRange`).** Away, Boost,
Frost, Manual and Eco all expose a **7–30 °C** carousel:

- **Away** defaults to **7 °C** — i.e. it is an anti-freeze-style setback by
  default (prevent pipes/room freezing while you're away), but the user *can*
  raise it up to 30 °C. So Away is a *settable low setpoint*, not a fixed 7 like
  Frost, and it is distinct from Frost in that Frost is always 7.
- **Boost** defaults to ~21 °C.

This matches dimplex-controller-hass#163: the reporter expected Away to accept a
target temperature (it does, 7–30), whereas the integration was sending
`FrostProtect` (fixed 7).

---

## 2. Endpoint catalogue

All under `https://mobileapi.gdhv-iot.com/api`. 82 endpoints total in the app;
the control/reporting-relevant ones are listed here. Method names are the
`DimplexControl.Services.APIService` members.

### RemoteControl — heating appliances (QRad / Quantum / Storage Heater)

| Endpoint | Method → returns | Request | 📦 |
| --- | --- | --- | --- |
| `/RemoteControl/GetApplianceOverview` | `GetApplianceOverview` → `List<ApplianceOverview>` | `{HubId, ApplianceIds[]}` | ✅ |
| `/RemoteControl/SetApplianceMode` | `SetModeForAppliances` → `bool` | `SetApplianceModeRequest` | ✅ |
| `/RemoteControl/SetApplianceSetpointTemperature` | `ApiSetApplianceSetpointTemperature` → `bool` | `{HubId, ApplianceIds[], Temperature: byte}` | ✅ |
| `/RemoteControl/SetSetbackTemperature` | `ApiSetSetbackTemperature` → void | `{HubId, ApplianceIds[], Status: EStatus, Temperature: byte}` | ✅ |
| `/RemoteControl/SetEcoStart` | `ApiSetEcoStart` → void | `{HubId, ApplianceIds[], Enable: bool}` | ✅ |
| `/RemoteControl/SetOpenWindowDetection` | `ApiSetOpenWindowDetection` → void | `{HubId, ApplianceIds[], Enable: bool}` | ✅ |
| `/RemoteControl/GetTimerModeDetailsForAppliance` | `ApiGetTimerModeDetailsForAppliance` → `ApplianceTimerModeDetails` | `{HubId, ApplianceId, TimerMode}` | ✅ |
| `/RemoteControl/SetTimerMode` | `ApiUpdateSchedulePeriods` → void | `{TimerModeSettings}` | ✅ |
| `/RemoteControl/CopyScheduleToAppliances` | `ApiCopyScheduleToAppliances` → resp | `{HubId, FromApplianceId, ApplianceIds[], TimerMode}` | ✅ |
| `/RemoteControl/GetApplianceInfo` | `GetApplianceInfo` → `ApplianceInfo` | `{HubId, ApplianceId}` | ✅ |
| `/RemoteControl/ContactAppliance` | contact/ping | — | ✅ |
| `/RemoteControl/GetServiceTestSummary` | `GetServiceTestSummary` → list | — | ✅ |

> **`SetTimerMode` is only for editing schedule *periods*** (`TimerModeSettings`),
> not for switching a heater on/off. `dimplex_controller.set_mode()` and
> `set_target_temperature()` both write `SetTimerMode`, which **Quantum rejects
> with HTTP 403** (dimplex-controller-hass#149). The app uses
> `SetApplianceSetpointTemperature` for setpoints and `SetApplianceMode`
> (FrostProtect) for "off".

### RemoteControl — hot-water cylinders (❌ not owned — APK-confirmed only)

Applies to `WaterHeater` and heat-pump `ASHW Cylinder` models. All reuse
`SetApplianceModeRequest` / `ApplianceModeSettings`.

| Endpoint | Method | Mode used | 📦 |
| --- | --- | --- | --- |
| `/RemoteControl/SetApplianceModeHwc` | `SetModeForHWAppliances` | Boost/Normal/… | ✅ |
| `/RemoteControl/SetBoostTemperatureHwc` | `SetHWBoostTemperature` | `Boost`, Temperature | ✅ |
| `/RemoteControl/SetNormalTemperatureHwc` | `SetHWNormalTemperature` | `Normal`, Temperature | ✅ |
| `/RemoteControl/SetHygieneSettingsHwc` | `SetHWHygieneSettings` | `Hygiene`, Temperature, `Frequency` | ✅ |
| `/RemoteControl/SetApplianceModeHeatPumpHwc` | `SetModeForHeatPumpHWAppliances` | — | ✅ |
| `/RemoteControl/SetHygieneSettingsHeatPumpHwc` | `SetHeatPumpHWCHygieneSettings` | `Hygiene` | ✅ |
| `/RemoteControl/ApiGetTimerModeDetailsForHeatPumpHwcAppliance` | `ApiGetTimerModeDetailsForHeatPumpHwcAppliance` → details | `{HubId, ApplianceId}` | ✅ |
| `/RemoteControl/UpdateHeatPumpHwcSchedulePeriods` | schedule edit | — | ✅ |

### Reports / profiles / structure (context)

`Reports/GetTsiEnergyReportDataForHub`, `Reports/GetEnergyUsageReportData`,
`UserHeatingProfile/*` (Get/AddOrUpdate/Apply/Rename/Delete profiles),
`Zones/*`, `Appliances/*` (incl. `GetProductModels`, `PerformAdvancedVerification`),
`Hubs/*`, `Identity/*`, `Notification/*`, `FeatureToggles/*`. All 📦 confirmed present
in 2.26.0; see the app for exact request shapes.

---

## 3. Cross-reference matrix — library vs APK 2.26.0 vs live

| Behaviour | `dimplex_controller` today | 📦 APK 2.26.0 | 🔬 Live QM100RF (2026-09-15) |
| --- | --- | --- | --- |
| **Boost flag** | ❌ `16` (= Advance) | ✅ `Boost = 2` | ✅ `modes→3`, `BoostDuration=30` applied |
| **Away flag** | ❌ `32` (= FrostProtect) | ✅ `Away = 4` | ✅ `modes→5`, `is_away` set |
| Boost duration | field ok (`Time`), wrong flag | ✅ `Time` minutes | ✅ 30 min accepted |
| Away duration | uses `NumberOfDays` | ✅ app uses `Date` (until) | ⚠️ bit set; target read 7 (see note) |
| `Status` semantics | `1`/`0` | ✅ `Active=1/Inactive=0` | ✅ engage/clear round-trips |
| **Target temperature** | ❌ rewrites schedule via `SetTimerMode` → 403 | ✅ `SetApplianceSetpointTemperature` (byte) | ✅ **200 OK**, non-destructive (schedule unchanged) |
| **"Off"** | ❌ `set_mode`→`SetTimerMode` → 403 | ✅ `SetApplianceMode` FrostProtect+Active, temp 7 | ✅ (32→frost previously observed) |
| Advance | not exposed | ✅ `Advance = 16` (255 for Quantum) | ✅ (16→advance previously observed) |
| EcoStart | ✅ correct (`SetEcoStart`) | ✅ | ✅ (prior) |
| Open-window | ✅ correct (`SetOpenWindowDetection`) | ✅ | ✅ (prior) |
| Setback write | ❌ none (`setback_write=False`) | ✅ `SetSetbackTemperature {EStatus, byte}` | — not tested |
| Schedule read | ✅ `GetTimerModeDetailsForAppliance` | ✅ | ✅ reads fine |
| Schedule write (periods) | via `SetTimerMode` (also misused for mode) | ✅ periods only | ✅ 403 when misused for mode/setpoint |
| HWC boost/normal/hygiene | ❌ missing | ✅ `Set*Hwc` endpoints | ❌ not owned |
| Heat-pump HWC | ❌ missing | ✅ `*HeatPumpHwc` endpoints | ❌ not owned |
| Energy report | ✅ `GetTsiEnergyReportDataForHub` | ✅ | ✅ (prior) |

### Live-validation notes (QM100RF, developer hardware)

- Sending `ApplianceModes=2, Status=1, Time=30, Temperature=24` set the **Boost**
  bit (`ApplianceModes → 3`) and applied `BoostDuration = 30` — the old `16` set
  Advance with duration `0`. **Confirmed the flag fix.**
- Sending `ApplianceModes=4, Status=1, Temperature=18, Date=+1d` set the **Away**
  bit (`ApplianceModes → 5`). **Confirmed the flag fix.**
- The overview `Temperature` fields still read the 7 °C frost floor during both
  tests. This is **inconclusive, not a contradiction**: (a) the app defaults Away
  to 7 °C anyway (anti-freeze setback), and Away's picker range is only 7–30; and
  (b) the room was already in the low-to-mid 20s °C with the storage heater idle
  and no charge to release, so no live target surfaces. A raised Away target
  (e.g. 18) reading back as 7 needs a cleaner retest (integer `Temperature`,
  possibly `StatusTwo`, ideally in heating season). The **flag mapping**
  (Boost=2/Away=4) is what these tests confirm — not the temperature semantics.
- `SetApplianceSetpointTemperature` returned **200 OK** and left the stored
  schedule periods unchanged — the correct, non-destructive setpoint path.
- All mode writes cleared cleanly with `Status=0`; the appliance was restored to
  its exact baseline (`ApplianceModes=1`, EcoStart on, TimerMode 0, 14 schedule
  periods unchanged).

### Summary

- **Cross-referenced against APK 2.26.0:** every row above (mode flags, payload
  shapes, and endpoint set).
- **Additionally validated live on a QM100RF:** Boost/Away flag values, the
  `Status` engage/clear semantics, `BoostDuration`, and the dedicated
  `SetApplianceSetpointTemperature` endpoint.
- **APK-only (no hardware):** all HWC / heat-pump-HWC endpoints and `SetSetbackTemperature`.
- **Open:** whether a *raised* Away target (>7) is honoured on Quantum. Away is a
  settable 7–30 setback that **defaults to 7** (anti-freeze), so the common case
  is a low setpoint by design; the question is only whether a higher chosen value
  applies. Needs a cold-room / charged retest with an integer `Temperature`.
