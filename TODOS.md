# TODOS

## Testing

### P0

(なし)

---

## Completed

**pytest モジュール名衝突の修正** — 解決済み (2026-04-06, chore/release-v1.25.0)

`--import-mode=importlib` (pytest.ini) + `skills/implement/scripts/tests/conftest.py` で
`telemetry` / `test_backfill` の衝突を解消。1563 tests pass。
