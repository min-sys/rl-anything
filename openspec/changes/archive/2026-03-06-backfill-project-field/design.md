## Context

`cross-project-telemetry-isolation` で usage.jsonl に `project` フィールドが追加された。新規レコードは自動的に `project` が付与されるが、既存の 1,922 件は `project` なし。2層リカバリにより 99.7%（1,916/1,922）のレコードに `project` を付与可能。

## Goals / Non-Goals

**Goals:**
- 既存 usage.jsonl の全レコードに `project` フィールドを付与する（マッピング可能なもの）
- マッピング不可のレコードは `project: null` を明示的に設定する
- `--dry-run` でマッピング結果のプレビュー
- バックアップによる安全なロールバック

**Non-Goals:**
- errors.jsonl のマイグレーション（現在ファイルが空）
- sessions.jsonl 自体の変更
- `project` フィールドの正確性の保証（sessions.jsonl のデータに依存）

## Decisions

### 1. 2層リカバリによる session_id → project_name マッピング

**選択**: sessions.jsonl（Tier 1）+ `~/.claude/projects/` filesystem consensus（Tier 2）の2層リカバリ。

**Tier 1 — sessions.jsonl（last-wins dedup）**:
- sessions.jsonl の各レコードから `session_id → project_name` マッピングを構築
- 同一 session_id に複数レコードがある場合は最後のレコードを採用（last-wins）
- sessions.jsonl の 40% は `project_name` が null だが、usage.jsonl の session_id 基準では 89% カバー
- 設定値: `DATA_DIR`（`hooks/common.py:11`）を参照

**Tier 2 — filesystem consensus**:
- `~/.claude/projects/` 配下の各ディレクトリ（= プロジェクト）に含まれるセッションファイルを走査
- 同ディレクトリ内の他セッションが Tier 1 で project_name を持つ場合、多数決（Counter.most_common(1)）で補完
- パスデコード不要（ハイフン曖昧性を consensus 方式で回避）
- 設定値: `CLAUDE_PROJECTS_DIR`（`skills/backfill/scripts/backfill.py:26`）と同等

**カバレッジ**: Tier 1 のみ 89.0% → Tier 2 追加で 99.7%（+10.7%）

**理由**:
- sessions.jsonl だけでは null project_name のセッションをカバーできない
- `~/.claude/projects/` のディレクトリ構造は同一プロジェクトのセッションをグループ化している
- consensus 方式ならパスのハイフンエンコーディング曖昧性を回避できる

**却下した代替案**:
- パスデコード方式: ハイフンエンコーディングの曖昧性（`matsukaze-utils` → `matsukaze/utils`?）で不正確
- usage-registry.jsonl からの紐付け: global スキルのみ記録されるため、カバレッジが低い

### 2. sessions.jsonl の重複ハンドリング

**選択**: last-wins 戦略。同一 session_id のレコードが複数存在する場合、最後に出現したレコードの `project_name` を採用する。

**理由**:
- 216 の session_id に重複あり（最大 33 回）。backfill 由来の重複が主因
- 同一 session_id は同一プロジェクトに属するため、どのレコードでも結果は同じケースが大半
- 最新レコードが最も正確な情報を持つ可能性が高い

### 3. 既に project フィールドを持つレコードの扱い

**選択**: 既存の `project` フィールドを上書きしない（スキップ）。

**理由**:
- 今回の change 実装後に記録されたレコードは正確な `project` を持つ
- マイグレーション後の再実行でも安全（冪等性）

### 4. 設定値の外出し

**選択**: `DATA_DIR` は `hooks/common.py`、`CLAUDE_PROJECTS_DIR` は `Path.home() / ".claude" / "projects"` を使用。ハードコードしない。

## Risks / Trade-offs

- **sessions.jsonl の project_name が不正確な場合**: backfill 由来のデータは元のセッションファイルパスから推定された project_name を使うため、パス構造の変更があった場合に不正確になる可能性 → 影響は限定的。discover のパターン検出に多少のノイズが入る程度
- **consensus の誤判定**: 同一ディレクトリに異なるプロジェクトのセッションが混在する可能性は極めて低い（ディレクトリ = プロジェクトの 1:1 対応）
- **バックアップファイルのサイズ**: usage.jsonl のコピーが作られる（現在 ~1,922行、数百KB程度）→ 問題なし
