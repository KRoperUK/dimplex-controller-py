# Library ↔ Home Assistant compatibility

Which `dimplex-controller` PyPI versions pair with which Home Assistant integration releases.

| Integration (HACS) | Min `dimplex-controller` | Notable features |
| --- | --- | --- |
| ≤ 2.x | ≥ 0.6 | Basic hubs / sensors / switches |
| 2.x energy era | ≥ 0.7 | Daily + lifetime energy summaries, control helpers |
| 2.x / 3.0 prep | ≥ 0.8 | Product catalogue / `AUTOMATIC_PROVISIONING`, rated power |
| 3.0+ (planned) | ≥ 0.9 | Structured auth errors; capability matrix & schedule helpers when published |

## Rules of thumb

- Always pin a **floor** in `manifest.json` `requirements` (currently `dimplex-controller>=0.8.0`).
- New HA features that need library APIs should bump the floor in the same PR that uses them.
- Dev / RC integration builds may temporarily depend on unreleased library APIs from a git URL — do not ship those floors to stable HACS releases.

## Related docs

- [Home Assistant integration](https://github.com/KRoperUK/dimplex-controller-hass)
- [Getting started](getting-started.md)
- [API reference](api-reference.md)
