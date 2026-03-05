## Why

ユーザーがタスクを切り替えた際に、該当するスキルが存在するにもかかわらず手動で作業してしまう「スキル見落とし」が発生している。現状の rl-anything はこのパターンを検出できず、ユーザー自身が気づいて初めて correction が発生する。また、correction からルール/メモリを提案する reflect のスコープ判定がキーワードベースのため、global vs project-specific の配置が不正確になるケースがある。

## What Changes

- discover に「missed skill opportunities」分析を追加: usage.jsonl のプロンプトデータとスキルのトリガーワードを突合し、「スキルが存在するのに使われなかった」パターンを検出・レポートする
- reflect のスコープ判定ロジックを改善: `always/never/prefer` キーワードだけで global にルーティングするのではなく、correction の内容がプロジェクト固有かどうかを判定するロジックを追加する
- discover レポートに missed skill セクションを追加し、頻度・該当スキル・推奨アクションを表示する

## Capabilities

### New Capabilities
- `missed-skill-detection`: usage.jsonl のプロンプトとスキルのトリガーワードを突合し、使うべきだったスキルを検出する分析機能
- `scope-aware-routing`: correction のスコープ（global vs project-specific）を意味ベースで判定するルーティング改善

### Modified Capabilities
- `reflect`: スコープ判定ロジックの改善（`suggest_claude_file()` のルーティング精度向上）
- `scoped-report-filtering`: discover レポートに missed skill opportunities セクションを追加

## Impact

- `skills/discover/scripts/discover.py`: missed skill 分析ロジック追加
- `scripts/reflect_utils.py`: `suggest_claude_file()` のスコープ判定ロジック改善
- `hooks/observe.py`: 変更なし（既存の usage.jsonl 記録で十分）
- スキルのトリガーワード取得: CLAUDE.md の Skills セクションまたは `.claude/skills/*/` のメタデータを読み込む必要あり
