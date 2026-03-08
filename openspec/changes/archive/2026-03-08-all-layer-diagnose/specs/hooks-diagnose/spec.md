## ADDED Requirements

### Requirement: hooks 設定の存在をチェックする
`diagnose_hooks()` は、`.claude/settings.json` に hooks 設定が存在するかどうかをチェックしなければならない（MUST）。hooks 設定が存在しない場合は `hooks_unconfigured` issue として検出する。

#### Scenario: hooks 設定がある
- **WHEN** `.claude/settings.json` に hooks 設定が存在する
- **THEN** `hooks_unconfigured` として検出されない

#### Scenario: hooks 設定がない
- **WHEN** `.claude/settings.json` に hooks 設定が存在しない
- **THEN** `{"type": "hooks_unconfigured", "file": ".claude/settings.json", "detail": {"reason": "no hooks configured"}, "source": "diagnose_hooks"}` が出力される

### Requirement: settings.json が存在しない場合は空リストを返す
`diagnose_hooks()` は、`.claude/settings.json` が存在しない場合、空のリストを返さなければならない（MUST）。

#### Scenario: settings.json が存在しない
- **WHEN** `.claude/settings.json` が存在しない
- **THEN** 空のリストを返す

### Requirement: 診断結果は統一フォーマットで出力する
`diagnose_hooks()` は `List[Dict]` を返し、各要素は `{"type": str, "file": str, "detail": dict, "source": str}` フォーマットでなければならない（MUST）。

#### Scenario: 問題がない場合
- **WHEN** hooks 設定が存在する
- **THEN** 空のリストを返す

### Non-scope（将来 change で対応）
- hook イベント別エラー率検出（`hook_error_rate`）— errors.jsonl に hook イベント名が記録されていないため実装不可
- 未使用 hook イベント検出（`unused_hook`）— sessions.jsonl に hook 実行記録がないため実装不可
- テレメトリベース診断は観測データ拡充後に別 change として対応する（[roadmap.md](../../../docs/roadmap.md) Gap 1 Ph1 `env-telemetry-score` 以降）
