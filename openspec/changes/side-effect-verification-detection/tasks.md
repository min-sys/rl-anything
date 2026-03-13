Related: #27

## 1. verification_catalog への副作用検出エントリ追加

- [x] 1.1 `scripts/lib/verification_catalog.py` に `SIDE_EFFECT_MIN_PATTERNS = 3` 定数を追加（`DATA_CONTRACT_MIN_PATTERNS` とは独立）
- [x] 1.2 `scripts/lib/verification_catalog.py` に副作用検出の regex パターン定数を追加（DB操作・メッセージキュー・外部API の3カテゴリ）
- [x] 1.3 `detect_side_effect_verification(project_dir)` 検出関数を実装（3カテゴリ走査、テストファイル除外フィルタ、evidence はプレーンパスリスト、`detected_categories` を別フィールドで返却、confidence 上限 0.7、llm_escalation_prompt 生成）
- [x] 1.4 テストファイル除外: `detect_side_effect_verification` 内で `_iter_source_files()` の結果から `test_*.py`, `*_test.py`, `*.test.ts`, `*.test.tsx`, `__tests__/` 配下のファイルをフィルタ
- [x] 1.5 `_DETECTION_FN_DISPATCH` に `detect_side_effect_verification` を登録
- [x] 1.6 `VERIFICATION_CATALOG` に `side-effect-verification` エントリを追加（rule_template 3行以内、rule_filename: `verify-side-effects.md`）
- [x] 1.7 `get_rule_template()` で `side-effect-verification` が言語非依存テンプレートを返すことを確認
- [x] 1.8 `check_verification_installed()` に content-aware チェックを追加（`.claude/rules/` 内の既存ファイルに「副作用」「side effect」キーワードが含まれる場合もインストール済みと判定）

## 2. reflect_utils への corrections パターン検出追加

- [x] 2.1 `scripts/lib/reflect_utils.py` に副作用キーワード定数を追加（`_SIDE_EFFECT_KEYWORDS_JA`, `_SIDE_EFFECT_KEYWORDS_EN`, `_SIDE_EFFECT_COMPOUND_PATTERNS`）
- [x] 2.2 `detect_side_effect_correction(message)` 関数を実装（単純キーワード + 複合パターンマッチ）
- [x] 2.3 `suggest_claude_file()` に副作用 correction ルーティングを挿入（project signals の**後**、優先度3。project signals が True ならスキップ。confidence 0.85、先は `.claude/rules/verification.md`）

## 3. remediation.py のテンプレート汎用化

- [x] 3.1 `skills/evolve/scripts/remediation.py` の `_RATIONALE_TEMPLATES[VERIFICATION_RULE_CANDIDATE]` を汎用化（`"モジュール間データ変換パターン"` → `"{description}"` に変更）

## 4. テスト

- [x] 4.1 `detect_side_effect_verification` のユニットテスト（DB検出・MQ検出・API検出・閾値未満・テストファイル除外・空プロジェクト・タイムアウト・detected_categories 確認）
- [x] 4.2 `detect_side_effect_correction` のユニットテスト（日本語キーワード・英語キーワード・複合パターン・pending単体不一致・再帰単体不一致・キーワードなし）
- [x] 4.3 `suggest_claude_file` の副作用ルーティング統合テスト（優先順位確認: guardrail > project signals > 副作用 > model）
- [x] 4.4 `check_verification_installed` の content-aware テスト（ファイル名一致・キーワード一致・どちらも不一致）
- [x] 4.5 既存テスト全パス確認（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）
