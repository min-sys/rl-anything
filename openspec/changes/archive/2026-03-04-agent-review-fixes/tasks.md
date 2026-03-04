<!-- Phase 依存関係: Phase 1 は先行必須。Phase 2/3/4 は Phase 1 完了後に並列実行可能。Phase 5 は Phase 1-4 全完了後。 -->

## 1. scripts/ 二重管理の解消

- [x] 1.1 `scripts/discover.py` を削除し、テスト・SKILL.md 内の参照を `skills/discover/scripts/discover.py` に修正
- [x] 1.2 `scripts/evolve.py` を削除し、テスト・SKILL.md 内の参照を `skills/evolve/scripts/evolve.py` に修正
- [x] 1.3 `scripts/audit.py` を削除し、テスト・SKILL.md 内の参照を `skills/audit/scripts/audit.py` に修正
- [x] 1.4 `scripts/aggregate_runs.py` を削除し、テスト・SKILL.md 内の参照を `skills/audit/scripts/aggregate_runs.py` に修正
- [x] 1.5 `scripts/fitness_evolution.py` を削除し、テスト・SKILL.md 内の参照を `skills/evolve-fitness/scripts/fitness_evolution.py` に修正
- [x] 1.6 テスト内の `importlib.util.spec_from_file_location` workaround を整理し、全テストが通ることを確認

## 2. ファイルパーミッション強化
<!-- Phase 1 完了後、Phase 3/4 と並列実行可能 -->

- [x] 2.1 `ensure_data_dir()` にディレクトリパーミッション `700` 設定を追加
- [x] 2.2 `append_jsonl()` に新規ファイル作成時のパーミッション `600` 設定を追加
- [x] 2.3 パーミッション設定のテストを追加

## 3. LLM 入力サニタイズ
<!-- Phase 1 完了後、Phase 2/4 と並列実行可能 -->

- [x] 3.1 `sanitize_message()` 関数を作成（500文字切り詰め、制御文字除去、XML タグ除去）
- [x] 3.2 `semantic_detector.py` の `ANALYSIS_PROMPT` 生成前に `sanitize_message()` を適用
- [x] 3.3 サニタイズのテストを追加（長文、制御文字、XML タグの各ケース）

## 4. corrections 偽陽性フィードバック機構
<!-- Phase 1 完了後、Phase 2/3 と並列実行可能 -->

- [x] 4.1 `false_positives.jsonl` の読み書きユーティリティを `common.py` に追加
- [x] 4.2 `detect_correction()` に偽陽性フィルタリングを追加（message hash で照合）
- [x] 4.3 `reflect` スキルに偽陽性マーク機能を追加（AskUserQuestion で「偽陽性」選択肢）
- [x] 4.4 180日超エントリの自動クリーンアップを `reflect` 実行時に追加
- [x] 4.5 偽陽性フィードバック機構のテストを追加

## 5. README / CLAUDE.md 更新
<!-- Phase 1-4 全完了後 -->

- [x] 5.1 README.md の evolve フロー記述を7フェーズに更新
- [x] 5.2 README.md に Before/After チュートリアルセクションを追加
- [x] 5.3 README.md と CLAUDE.md の整合性を確認・修正
- [x] 5.4 CHANGELOG.md に破壊的変更（scripts/ 削除）を記載
