# API cassettes (fixtures)

Committed JSON responses used by unit tests so CI does not need live cloud access.

## Capturing new fixtures

1. Prefer the official app + a MITM proxy (Charles/Proxyman), or `dimplex` CLI against a test account.
2. Save the **response body only** (not request headers with Bearer tokens).
3. Redact before commit:
   - email addresses → `user@example.com`
   - tokens / JWT / refresh codes → remove entirely
   - street addresses / postcodes → generic placeholders
   - real hub/appliance ids → stable demo ids (`hub-demo-001`, `app-1`)
4. Drop the file under `tests/fixtures/cassettes/` and load via `tests/fixtures.py`.

Never commit access or refresh tokens.
