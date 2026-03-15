## 1. skill_origin 共通モジュール

- [x] 1.1 `scripts/lib/skill_origin.py` を作成。`audit.py` の `_load_plugin_skill_map()` ロジックを抽出し、`classify_skill_origin(path)` → `"plugin" | "global" | "custom"` を実装。mtime ベース cache invalidation を適用（`is_reference_skill()` パターン準拠）
- [x] 1.2 `is_protected_skill(path)` を実装（plugin origin → True）
- [x] 1.3 `suggest_local_alternative(skill_name, project_root)` を実装（references/pitfalls.md パスを返す、既存ファイルの有無で追記/新規を判別）
- [x] 1.4 `generate_protection_warning(skill_name, alternative_path)` を実装（警告メッセージ生成）
- [x] 1.5 知見追加時の pitfall_manager Candidate フォーマット（`## Candidate: <title>` + context/pattern/solution）を定義
- [x] 1.6 `scripts/tests/test_skill_origin.py` にユニットテスト作成（origin判定、保護チェック、代替先提案、警告生成、graceful degradation 3パターン）

## 2. reflect ルーティング拡張

- [x] 2.1 `reflect_utils.py` の `suggest_claude_file()` に last-skill コンテキスト層を追加（always/never 層の後、frontmatter paths 層の前 — 位置6）
- [x] 2.2 last-skill 層でスキルの references/ パスを解決するロジック実装（`_resolve_skill_references_path()`）
- [x] 2.3 保護スキルの場合に `suggest_local_alternative()` 経由でローカル代替先にリダイレクトするロジック追加
- [x] 2.4 既存テスト更新 + last-skill ルーティングの新規テスト追加（キーワードバイアス軽減の検証含む）

## 3. audit.py リファクタ

- [x] 3.1 `audit.py` の `_load_plugin_skill_map()` を `skill_origin.py` の呼び出しに置換
- [x] 3.2 `classify_artifact_origin()` を `skill_origin.classify_skill_origin()` で統一
- [x] 3.3 既存 audit テストが pass することを確認

## 4. discover / remediation 統合

- [x] 4.1 `remediation.py` の fix アクションで保護スキルへの書込を検出した場合に警告 + 代替先提案を返すように修正
- [x] 4.2 `discover.py` のレポートにプラグインスキルの保護状態を表示

## 5. 定数定義

- [x] 5.1 `LAST_SKILL_CONFIDENCE = 0.88` を `reflect_utils.py` に定義

## 6. spec アーカイブ・検証・CHANGELOG

- [x] 6.1 全テスト pass 確認（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）
- [x] 6.2 新規 spec `openspec/specs/downloaded-skill-guard/spec.md` と `openspec/specs/context-aware-knowledge-routing/spec.md` をアーカイブ
- [x] 6.3 既存 spec `openspec/specs/reflect/spec.md` に delta を適用
- [x] 6.4 CHANGELOG.md に変更を追記
