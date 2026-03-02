## MODIFIED Requirements

### Requirement: hooks.json のコマンドパスは `${CLAUDE_PLUGIN_ROOT}` を使用しなければならない（MUST）
hooks.json 内の全コマンドパスで `$PLUGIN_DIR` を `${CLAUDE_PLUGIN_ROOT}` に修正しなければならない（MUST）。これは Claude Code プラグイン公式仕様への準拠である。

#### Scenario: hooks.json パス修正
- **WHEN** hooks.json が読み込まれる
- **THEN** 全コマンドが `${CLAUDE_PLUGIN_ROOT}/hooks/` プレフィックスを使用している
- **AND** `$PLUGIN_DIR` を含むコマンドが存在しない
