## 1. 検出エンジン実装

- [x] 1.1 `scripts/lib/hardcoded_detector.py` を作成 — 正規表現パターン定義（AWS ARN, Slack ID, API キー, サービス URL, 長数値 ID）
- [x] 1.2 `detect_hardcoded_values(file_path, extra_patterns, extra_allowlist)` 関数を実装 — ファイル走査 + パターンマッチ + 結果リスト返却。`extra_patterns` / `extra_allowlist` はオプショナル（D7 準拠）
- [x] 1.3 許容パターン除外ロジックを実装 — プレースホルダ、ダミー値、localhost URL、バージョン番号、算術式、タイムスタンプのフィルタリング。インライン抑制コメント `<!-- rl-allow: hardcoded -->` を含む行のスキップ（D5 準拠）
- [x] 1.4 `compute_confidence_score(pattern_type)` を実装 — D6 の定義テーブルに基づき pattern_type 別デフォルト confidence_score を返却。検出結果に `confidence_score` フィールドを付与
- [x] 1.5 ファイル読み込みエラーハンドリングを実装 — パーミッション不足・バイナリファイル・非 UTF-8 エンコーディング時は空リストを返却し例外を伝播させない

## 2. audit 統合

- [x] 2.1 `audit.py` の `collect_issues()` に `detect_hardcoded_values()` 呼び出しを追加 — skill/rule ファイルを走査し `type: "hardcoded_value"` の issue を統合
- [x] 2.2 `generate_report()` に「Hardcoded Values」警告セクションを追加 — 検出0件時はセクション省略

## 3. テスト

- [x] 3.1 `scripts/lib/tests/test_hardcoded_detector.py` を作成 — 各パターンの検出テスト + 許容パターンの除外テスト + インライン抑制テスト + エラーハンドリングテスト + confidence_score テスト + extra_patterns/extra_allowlist テスト
- [x] 3.2 `skills/audit/scripts/tests/test_collect_issues.py` に hardcoded_value 統合テストを追加

## 4. remediation 分類確認

- [x] 4.1 `remediation.py` の `classify_issues()` が `hardcoded_value` タイプを `proposable` に分類することを確認（必要なら分類ルールを追加）。confidence_score が低い検出（< 0.5）は `info` に分類する分岐を追加
