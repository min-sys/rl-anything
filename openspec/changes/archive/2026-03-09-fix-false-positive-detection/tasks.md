Closes: #23

## 1. パス抽出 FP 修正 (stale_ref)

- [x] 1.1 `_extract_paths_outside_codeblocks()` に数値のみセグメント除外フィルタを追加（`429/500/503` 等）
- [x] 1.2 stale_ref 判定にファイル位置基準の相対パス解決を追加（参照元ファイルの親ディレクトリ基準）
- [x] 1.3 プロジェクトルートに存在しないトップレベルディレクトリへの参照を stale_ref 候補から除外
- [x] 1.4 `test_path_extraction.py` に数値パターン・ファイル位置基準解決・外部参照のテストケースを追加

## 2. orphan_rule 廃止

- [x] 2.1 `diagnose_rules()` から orphan_rule 検出ロジックを削除
- [x] 2.2 `coherence.py:score_efficiency()` の orphan_rules カウントを廃止
- [x] 2.3 `test_layer_diagnose.py` から orphan_rule 関連テストを削除または更新

## 3. stale_rule ファイル位置基準解決

- [x] 3.1 `diagnose_rules()` の stale_rule 判定にファイル位置基準の相対パス解決を追加（D2 と同じロジック）
- [x] 3.2 `test_layer_diagnose.py` に stale_rule のファイル位置基準解決テストケースを追加

## 4. claudemd_missing_section FP 修正

- [x] 4.1 `diagnose_claudemd()` のセクション名正規表現を `^#{1,3}\s+.*[Ss]kills?\b` に拡張
- [x] 4.2 日本語パターンも `.*スキル` に拡張
- [x] 4.3 `test_layer_diagnose.py` に prefix 付きセクション名（`Key Skills` 等）のテストケースを追加

## 5. line_limit 種別分離

- [x] 5.1 `line_limit.py` に `MAX_PROJECT_RULE_LINES = 5` と `CLAUDEMD_WARNING_LINES = 300` を追加
- [x] 5.2 `check_line_limit()` にグローバル/プロジェクトルールの判定ロジックを追加（`str(Path.home())` チェック）
- [x] 5.3 audit.py の LIMITS dict と `collect_issues()` で CLAUDE.md の制限違反を除外（warning のみに変更）
- [x] 5.4 `line_limit.py` と `test_collect_issues.py` にプロジェクト/グローバルルール区別のテストケースを追加

## 6. ロードマップ

- [x] 6.1 roadmap.md に orphan_rule → telemetry ベース unused_rule 移行ロードマップを記載

## 7. 統合テスト・検証

- [x] 7.1 全テストスイートを実行し regression がないことを確認
- [x] 7.2 実際の evolve 実行で #23 の4パターンの FP が解消されていることを確認
