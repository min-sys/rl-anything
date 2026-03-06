## 1. サマリ生成ロジック

- [x] 1.1 `optimize.py` に `_generate_summary()` メソッド追加: `history[0]["individuals"][0]["fitness"]` から baseline_score を取得し、best_score, score_delta を算出
- [x] 1.2 世代履歴（各世代の best/avg/std_dev/strategy）を summary に含める
- [x] 1.3 CoT 評価内訳（clarity, completeness, structure, practicality — cot-evaluation spec 準拠）を summary に含める（cot_reasons が None の場合は N/A フォールバック）
- [x] 1.4 `difflib.unified_diff` で diff 統計（lines_added, lines_deleted, changed_sections）を算出。changed_sections は `##` 見出し行の変更を検出
- [x] 1.5 score_delta == 0 の場合、diff_stats を空（lines_added: 0, lines_deleted: 0, changed_sections: []）で返す

## 2. 結果表示

- [x] 2.1 `run()` の戻り値に `summary` フィールドを追加
- [x] 2.2 コンソール出力フォーマットを更新（スコア推移テーブル（std_dev 列含む）、CoT 内訳、diff 統計）

## 3. SKILL.md 更新

- [x] 3.1 SKILL.md の accept/reject 確認ステップにサマリ表示手順を追加
- [x] 3.2 score_delta == 0 時に「改善なし: ベースラインからの変更はありません」と表示する手順を追加

## 4. テスト

- [x] 4.1 `_generate_summary()` のユニットテスト追加（正常系、CoT 欠落時、差分なし時、score_delta == 0 時）
- [x] 4.2 既存テストの回帰確認

関連 Issue: #7
