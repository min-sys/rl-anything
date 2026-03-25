## Why

evolve/discover はテレメトリベースでスキル候補の検出や既存スキルの適性評価を行うが、**description の trigger 精度**（正しいクエリで発火するか、誤ったクエリで発火しないか）を定量計測する手段がない。結果として「新スキルを作るべきか」「既存の description を更新すべきか」「スキルを分割/マージすべきか」の判断が曖昧になっている。skill-creator v2 が eval/benchmark/description optimizer を提供しているため、rl-anything はテレメトリから eval set を自動生成し、skill-creator と補完関係を築くことで、スキルライフサイクル全体の品質を自動管理できる。

## What Changes

- **trigger eval set 自動生成**: sessions.jsonl + usage.jsonl の実プロンプトデータから、skill-creator 互換の `evals.json`（should_trigger / should_not_trigger クエリセット）を自動生成する
- **skill triage 判定エンジン**: テレメトリ + trigger eval 結果を統合し、各スキルに対して CREATE / UPDATE / SPLIT / MERGE / OK の5択アクション判定を行う
- **evolve 統合**: evolve の Diagnose ステージに triage 結果を統合し、description 品質問題を remediation 候補として出力する
- **skill-creator 連携提案**: UPDATE 判定時に `/skill-creator` での description 最適化を提案（生成済み evals.json パスを含む）

## Capabilities

### New Capabilities
- `trigger-eval-generator`: テレメトリデータから skill-creator 互換 evals.json を自動生成する機能
- `skill-triage`: trigger eval 結果 + テレメトリ + skill_evolve 評価を統合し、CREATE/UPDATE/SPLIT/MERGE/OK のアクション判定を行う機能

### Modified Capabilities
- `diagnose-stage`: triage 結果を issue として取り込み、remediation パイプラインに流す
- `missed-skill-detection`: trigger eval 結果で missed skill の精度を補強する

## Impact

- **新規ファイル**: `scripts/lib/trigger_eval_generator.py`, `scripts/lib/skill_triage.py`
- **変更ファイル**: `skills/evolve/scripts/evolve.py`（Diagnose ステージ）, `skills/discover/scripts/discover.py`（missed skill 強化）, `scripts/lib/issue_schema.py`（新 issue type 追加）
- **依存**: skill-creator プラグイン（evals.json フォーマット互換。実行時依存ではなくフォーマット互換のみ）
- **テレメトリ**: sessions.jsonl に十分なデータ（5セッション以上）が必要。データ不足時は graceful degradation
