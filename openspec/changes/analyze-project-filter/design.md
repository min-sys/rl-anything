## Context

`analyze.py` は `common.DATA_DIR` (`~/.claude/rl-anything/`) 配下の JSONL ファイルを全件読み込み分析する。一方 `backfill.py` は各レコードに `project_name` フィールドを付与してプロジェクト単位でデータを書き込む。この非対称性により、複数プロジェクトで backfill を実行すると分析結果にデータが混在する。

現在のデータフロー:
- `backfill.py` → sessions.jsonl に `project_name` を設定 ✅
- `backfill.py` → usage.jsonl / workflows.jsonl に `project_name` なし（session_id のみ）
- `analyze.py` → 全データを無条件に読み込み ❌

## Goals / Non-Goals

**Goals:**
- `analyze.py` がプロジェクト単位でフィルタした分析結果を出力する
- デフォルトでカレントディレクトリのプロジェクト名を使用する
- 既存の JSONL データとの後方互換性を維持する

**Non-Goals:**
- usage.jsonl / workflows.jsonl のレコードに `project_name` を追加する（sessions.jsonl 経由で session_id → project_name のマッピングが可能）
- 過去データのマイグレーション
- 複数プロジェクトの横断分析機能

## Decisions

### D1: フィルタ戦略 — sessions.jsonl の project_name を正とし session_id でフィルタ

**選択**: sessions.jsonl から対象プロジェクトの session_id セットを取得し、usage.jsonl / workflows.jsonl をその session_id セットでフィルタする。

**理由**: sessions.jsonl には既に `project_name` フィールドがある。usage.jsonl / workflows.jsonl にも `session_id` があるため、sessions.jsonl を起点にした session_id ベースのフィルタが最もシンプルで既存データとの互換性が高い。

**却下案**: usage.jsonl / workflows.jsonl に `project_name` フィールドを追加する → 既存データのマイグレーションが必要になり複雑。

### D2: プロジェクト名の取得方法 — backfill.py と同じ `project_name_from_dir()` を再利用

**選択**: `backfill.py` の `project_name_from_dir()` ロジックを `common.py` に移動し共有する。

**理由**: backfill.py が sessions.jsonl に書き込む `project_name` と一致させる必要がある。同じロジックを使うことで整合性を保証する。

**却下案**: analyze.py で独自に実装する → ロジックの二重管理になりバグの温床。

### D3: CLI インターフェース — `--project` オプション（デフォルト: カレントディレクトリ名）

**選択**: `analyze.py` に `--project <name>` 引数を追加。未指定時は `project_name_from_dir(os.getcwd())` をデフォルトとする。

**理由**: `backfill.py` の `--project-dir` と対称的な使い方になる。ディレクトリパスではなくプロジェクト名を受け取ることで、SKILL.md からの呼び出しが簡潔になる。

## Risks / Trade-offs

- **[Risk] sessions.jsonl に project_name がないレコード** →
  observe hooks（session_summary.py）はセッション終了時に project_name なしで
  sessions.jsonl に書き込む。これらのレコードは --project フィルタに一致せず、
  対応する session_id の usage/workflows データもフィルタ結果から除外される。
  これは意図的な動作であり、hook データを分析対象にするには
  backfill --force で再取り込みする必要がある。
  hooks 側で project_name を付与する改善は本変更のスコープ外とする。
- **[Risk] session_id の不一致** → usage.jsonl / workflows.jsonl に session_id がないレコードはフィルタで除外される。backfill.py が常に session_id を付与するため実質的な影響はない。
