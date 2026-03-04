## Why

fix-merge-false-positives のレビュー中に発見された4件のコード品質問題が、merge 修正とはスコープが異なるため分離した。いずれも「テンプレートがそのまま残っている」「同じロジックが複数箇所にコピペされている」という DRY 違反・スタブ残留であり、保守性と信頼性を下げている。

具体的な問題:

1. **`generate_adversarial_candidates()`** (`fitness_evolution.py`): 関数名は「adversarial candidate を生成する」だが、実際にはハードコードされたテンプレート辞書を返すだけ。呼び出し元 (`evolve_fitness()`) が戻り値をそのまま結果に含めるため、ユーザーに誤解を与える
2. **`fitness-template.py` の `evaluate()` / `check_anti_patterns()`** (`skills/generate-fitness/templates/fitness-template.py`): テンプレートファイルのスタブ実装。`scores` が空のまま常に 0.5 を返し、`anti_patterns` リストも空。generate-fitness スキルがこのテンプレートをコピーして使うが、スタブのまま実行される可能性がある
3. **`jaccard_coefficient()` の共通化** (`skills/enrich/scripts/enrich.py`): enrich.py 内にローカル定義されているが、reorganize でも TF-IDF ベースの類似度計算が必要（fix-merge-false-positives で `similarity-engine` として導入予定）。目的は異なるが集合類似度の計算は共通基盤に統合すべき
4. **`_check_line_limit()` 重複** (`optimize.py` / `run-loop.py`): 同一ロジック（行数上限チェック + 警告出力）が2ファイルに独立実装されている。定数 `MAX_RULE_LINES` / `MAX_SKILL_LINES` も各ファイルで重複定義

## What Changes

- `generate_adversarial_candidates()` を削除またはリネームし、関数の意図（テンプレート提供）を正確に反映する名前・docstring に変更。戻り値の用途を明確化
- `fitness-template.py` にガード節を追加し、スタブのまま実行された場合に「未実装」エラーを stderr に出力して 0.0 を返す（黙って 0.5 を返さない）
- `jaccard_coefficient()` と `tokenize()` を `scripts/rl/similarity.py` に抽出し、enrich.py からインポートに切替。将来の TF-IDF 共通基盤への足掛かりとする
- `_check_line_limit()` と行数定数 (`MAX_RULE_LINES` / `MAX_SKILL_LINES`) を `scripts/rl/line_limit.py` に共通化し、optimize.py / run-loop.py からインポートに切替

## Capabilities

### Modified Capabilities
- `evolve-fitness`: `generate_adversarial_candidates()` のリネーム・意図明確化
- `generate-fitness`: テンプレートのスタブ検出ガードを追加（黙った 0.5 フォールバックを排除）
- `enrich`: `jaccard_coefficient()` を共通モジュールに移動（機能変更なし）
- `optimize` / `rl-loop`: `_check_line_limit()` を共通モジュールに移動（機能変更なし）

## Impact

- **変更対象ファイル**: `skills/evolve-fitness/scripts/fitness_evolution.py`, `skills/generate-fitness/templates/fitness-template.py`, `skills/enrich/scripts/enrich.py`, `skills/genetic-prompt-optimizer/scripts/optimize.py`, `skills/rl-loop-orchestrator/scripts/run-loop.py`
- **新規ファイル**: `scripts/rl/similarity.py`, `scripts/rl/line_limit.py`
- **依存関係**: なし（純粋なリファクタリング、外部ライブラリ追加不要）
- **テスト**: 既存テストの import パス更新 + 共通モジュールのユニットテスト追加
- **互換性**: 外部インターフェース変更なし。内部リファクタリングのみ
