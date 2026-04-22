# TODOS

## Testing

### P0

(なし)

---

## rl-fleet

### P2

**`resolve_auto_memory_dir` の特殊文字ケーステスト追加（Phase 3 直前）**

**Priority:** P2

fleet.py の `resolve_auto_memory_dir(pj_path) -> Path` ヘルパは、PJ 絶対パスを `~/.claude/projects/<slug>/memory/` に逆引きする。`~/.claude/projects/` の命名規則は `-` 区切り絶対パスだが、PJ パスに日本語・space・記号が含まれる場合の slug 化ロジックは gstack / CC 本体依存。特殊文字ケースが未検証のまま Phase 3 rollback で snapshot / restore に失敗すると、auto-memory の書き戻し事故につながる。

**対応**: Phase 3 実装着手時に以下のテストを追加:
- `/Users/foo bar/project` (space)
- `/Users/foo/日本語パス` (multibyte)
- `/Users/foo/.hidden-dir/sub`
- シンボリックリンク経由の PJ パス

**背景**: plan-eng-review（2026-04-22, main branch, design 20260422-140954）で senior-engineer agent 相談時に検出。Phase 1/2 では `resolve_auto_memory_dir` 自体が導入されないため、Phase 3 ブランチ起票時に着手で十分。

**依存**: Phase 3 実装開始、`feat/rl-fleet-phase3` ブランチで fleet.py に `resolve_auto_memory_dir` が具体化してから

---

## philosophy-review

### P2

**corrections.jsonl concurrent write に file lock を追加**

**Priority:** P2

philosophy-review / reflect / discover が同一 corrections.jsonl に同時 append する可能性あり。Python buffered text-mode の `f.write()` は > PIPE_BUF で atomic 保証なし、partial-line 混入で JSONL 破損リスク。

**対応**: `fcntl.flock(f, LOCK_EX)` を追加、または専用 lockfile を介した atomic append。

**背景**: /review の adversarial subagent で検出 (2026-04-15, feat/philosophy-review PR #64)。現状は手動 trigger で単独実行前提なので deferred。自動 trigger を導入する段階で必須化。

---

## Completed

**pytest モジュール名衝突の修正** — 解決済み (2026-04-06, chore/release-v1.25.0)

`--import-mode=importlib` (pytest.ini) + `skills/implement/scripts/tests/conftest.py` で
`telemetry` / `test_backfill` の衝突を解消。1563 tests pass。
