## Why

discover は現在 usage.jsonl（スキル/エージェント呼び出し）と errors.jsonl からパターンを検出しているが、
全ツール呼び出しの 31.8% を占める Bash の**中身**を分析していない。
Bash コマンドの中には「Read/Grep/Glob で代替可能な呼び出し (7.4%)」「繰り返しパターンからスキル化すべきもの (57.7%)」が埋まっており、
これを自動検出して evolve ループに乗せることで、スキル/ルールの自律改善精度が上がる。

## What Changes

- discover に**ツール利用分析フェーズ**を追加: セッション JSONL からツール呼び出しを集計し、Bash コマンドを分類（built-in 代替可能 / 繰り返しパターン / CLI 正当利用）
- 繰り返しパターンを既存の discover 候補フローに合流させ、スキル候補として出力
- built-in 代替可能パターンをルール候補として出力
- evolve が discover のツール利用分析結果を拾い、改善提案に含める

## Capabilities

### New Capabilities
- `tool-usage-analysis`: セッション JSONL からツール呼び出しパターンを抽出・分類し、スキル/ルール候補として discover に合流させる

### Modified Capabilities
- (なし — discover.py / evolve.py への追加であり、既存 spec の要件変更はない)

## Impact

- `skills/discover/scripts/discover.py`: 新しい検出関数の追加、`run_discover()` への統合
- `scripts/lib/telemetry_query.py`: セッション JSONL からツール呼び出しを抽出するクエリ関数の追加（オプション）
- `skills/evolve/SKILL.md`: discover フェーズ結果の表示にツール利用分析セクションを追加
- テスト: `skills/discover/scripts/tests/` に新規テスト追加
