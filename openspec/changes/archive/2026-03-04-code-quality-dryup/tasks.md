## 1. 共通モジュール作成

- [x] 1.1 `scripts/lib/line_limit.py` を作成: `MAX_SKILL_LINES`, `MAX_RULE_LINES` 定数 + `check_line_limit(target_path, content) -> bool` 関数（超過時 stderr 警告）
- [x] 1.2 `scripts/lib/similarity.py` に `tokenize()` と `jaccard_coefficient()` を追加（既存 TF-IDF 関数の下に配置）
- [x] 1.3 共通モジュールのユニットテスト作成: `scripts/tests/test_line_limit.py`, `scripts/tests/test_similarity.py` に Jaccard/tokenize テスト追加

## 2. 行数制限の共通化

- [x] 2.1 `optimize.py`: `MAX_SKILL_LINES` / `MAX_RULE_LINES` のローカル定義を削除し `scripts.lib.line_limit` から import に切替。`_check_line_limit()` 内部で共通関数を呼び出すように変更
- [x] 2.2 `run-loop.py`: `MAX_SKILL_LINES` / `MAX_RULE_LINES` / `_check_line_limit()` を削除し `scripts.lib.line_limit` から import に切替
- [x] 2.3 `discover.py`: `MAX_SKILL_LINES` / `MAX_RULE_LINES` のローカル定義を削除し `scripts.lib.line_limit` から import に切替
- [x] 2.4 既存テスト（test_optimizer.py, test_run_loop.py）の import パス更新・動作確認

## 3. Jaccard 類似度の共通化

- [x] 3.1 `enrich.py`: ローカルの `tokenize()` / `jaccard_coefficient()` を削除し `scripts.lib.similarity` から import に切替
- [x] 3.2 `test_enrich.py` の TestTokenize / TestJaccardCoefficient を `scripts/tests/test_similarity.py` に移動・更新

## 4. スタブ・命名の修正

- [x] 4.1 `fitness_evolution.py`: `generate_adversarial_candidates()` を `get_adversarial_templates()` にリネーム。docstring を「テンプレート辞書の提供」に修正。呼び出し元も更新
- [x] 4.2 `fitness-template.py`: `evaluate()` の `scores` 空時フォールバックを `0.5` → stderr 警告 + `0.0` に変更

## 5. 検証

- [x] 5.1 全テスト実行: `python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`
- [x] 5.2 各 spec の Scenario を手動確認（旧関数名の残存チェック、ローカル定数の残存チェック）
