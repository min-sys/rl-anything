Related: #21

## 1. 共通基盤 + coherence アダプター

- [x] 1.1 `scripts/lib/layer_diagnose.py` を作成し、共通の issue フォーマットヘルパーと `diagnose_all_layers()` エントリポイントを実装する
- [x] 1.2 coherence.py の `compute_coherence_score()` を呼び出し、details dict を issue フォーマットに変換するアダプター関数を `layer_diagnose.py` に実装する（coherence.py 自体は変更しない）
- [x] 1.3 `scripts/lib/layer_diagnose.py` のユニットテストを `scripts/tests/test_layer_diagnose.py` に作成する

## 2. Rules 診断

- [x] 2.1 `diagnose_rules()` を実装する — 孤立ルール検出（`orphan_rule`、coherence details + スキル参照チェック補完）、陳腐化ルール検出（`stale_rule`）。閾値はモジュール定数または coherence.py THRESHOLDS から参照
- [x] 2.2 Rules 診断のテストを追加する（孤立/陳腐化/coherence 補完/正常の各シナリオ）

## 3. Memory 診断

- [x] 3.1 `diagnose_memory()` を実装する — 陳腐化エントリ検出（`stale_memory`、既存 `stale_ref` 未カバーパターンに限定）、重複セクション検出（`memory_duplicate`）。閾値はモジュール定数から参照
- [x] 3.2 Memory 診断のテストを追加する（陳腐化/重複/stale_ref 重複排除/正常の各シナリオ）

## 4. Hooks 診断

- [x] 4.1 `diagnose_hooks()` を実装する — settings.json の hooks 設定存在チェック（`hooks_unconfigured`）、設定なし時の空リスト返却
- [x] 4.2 Hooks 診断のテストを追加する（設定あり/設定なし/settings.json 不存在の各シナリオ）

## 5. CLAUDE.md 診断

- [x] 5.1 `diagnose_claudemd()` を実装する — 幻影参照検出（`claudemd_phantom_ref`）、セクション欠落検出（`claudemd_missing_section`）
- [x] 5.2 CLAUDE.md 診断のテストを追加する（幻影参照/プラグインスキル除外/セクション欠落/正常の各シナリオ）

## 6. audit collect_issues() 拡張

- [x] 6.1 `audit.collect_issues()` に `layer_diagnose.diagnose_all_layers()` の呼び出しを追加する
- [x] 6.2 collect_issues() の既存テストが通ることを確認し、新レイヤーの issue が含まれるテストを追加する

## 7. remediation 拡張

- [x] 7.1 `remediation.py` の `compute_confidence_score()` に新 issue type（`orphan_rule`, `stale_rule`, `stale_memory`, `memory_duplicate`, `hooks_unconfigured`, `claudemd_phantom_ref`, `claudemd_missing_section`）の分岐を追加する
- [x] 7.2 `remediation.py` の `generate_rationale()` に新 issue type のテンプレートを追加する
- [x] 7.3 remediation の既存テストに新 issue type のテストケースを追加する

## 8. evolve パイプライン統合

- [x] 8.1 `evolve.py` の Diagnose ステージに `layer_diagnose` フェーズを追加し、結果を `phases["layer_diagnose"]` に格納する
- [x] 8.2 `evolve/SKILL.md` の Diagnose ステージ手順にレイヤー別診断結果の表示・対話フローを追加する

## 9. 統合テスト・動作確認

- [x] 9.1 全テスト実行（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）でリグレッションがないことを確認する
- [x] 9.2 `evolve.py --dry-run --project-dir .` を実行し、全レイヤーの診断結果が出力されることを確認する
