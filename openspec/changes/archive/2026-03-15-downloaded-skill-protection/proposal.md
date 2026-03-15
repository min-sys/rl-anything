Related: #29

## Why

プラグイン由来のダウンロードスキル（openspec-verify-change 等）がエージェントによって直接編集されてしまう問題がある。また、知見の保存先スキルを選択する際に、直前の会話コンテキスト（使用中スキル）ではなくキーワードマッチに引きずられ、誤ったスキルにルーティングされる。これにより、プラグイン更新時に変更が上書きで消失するリスクと、知見が不適切な場所に蓄積される問題が発生している。(#29)

## What Changes

- プラグイン由来スキルの変更保護メカニズムを追加。`installed_plugins.json` + パスベース判定で origin を検出し、保護対象スキルへの編集を検知した場合に警告とローカル代替先を提案
- reflect の知見ルーティングに「直前使用スキル」コンテキストを導入。キーワードマッチより会話コンテキスト（corrections の `last_skill` フィールド等）を優先するロジックを追加
- SKILL.md frontmatter に `source` フィールドを追加し、plugin install 時に自動付与する仕組みを検討

## Capabilities

### New Capabilities
- `downloaded-skill-guard`: プラグイン由来スキルの変更保護 — origin 判定、編集警告、ローカル代替先提案
- `context-aware-knowledge-routing`: 知見ルーティングの精度向上 — 直前使用スキルコンテキスト優先、キーワードバイアス軽減

### Modified Capabilities
- `reflect`: 知見保存先のルーティングロジックに使用コンテキスト優先を追加

## Impact

- `scripts/reflect_utils.py`: suggest_claude_file() にコンテキスト優先ロジック追加
- `skills/audit/scripts/audit.py`: classify_artifact_origin() の拡張（既存インフラ活用）
- `scripts/lib/frontmatter.py`: source フィールド対応（parse/update は既に汎用）
- `skills/discover/scripts/discover.py`: プラグインスキル保護状態の表示
- 新規: downloaded skill guard モジュール（origin 判定 + 警告生成）
