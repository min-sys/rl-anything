## Context

rl-anything の observe hook は全プロジェクトのテレメトリを `~/.claude/rl-anything/usage.jsonl` に一括記録する。discover/audit はこのファイルを全行パースし Python で集計するが、プロジェクト識別子がないため全 PJ のデータが混在し、無関係なスキル候補が提案される。

現状のアーキテクチャ:
- Write: observe hook → JSONL append（依存なし、高速）
- Read: discover/audit → `load_jsonl()` + Python Counter で手動集計

## Goals / Non-Goals

**Goals:**
- discover/audit の結果をプロジェクト単位で正確にフィルタリングする
- 読み込み層の集計ロジックを SQL に置き換え、コードを簡素化する
- 既存 JSONL データ（project フィールドなし）との後方互換性を維持する

**Non-Goals:**
- JSONL ストレージ自体の置き換え（書き込みは JSONL append を維持）
- 古いデータの自動マイグレーション（project=NULL として扱う）
- Parquet アーカイブ（将来の拡張として残す）

## Decisions

### 1. ハイブリッドアーキテクチャ（JSONL write + DuckDB read）

**選択**: observe hook は JSONL append を維持し、読み込み側のみ DuckDB を導入する。

**理由**:
- observe hook は全ツール呼び出しのたびに発火する（1セッション数十〜数百回）。`import duckdb` の起動コスト (~100-200ms) を毎回払うのは体感に影響する
- DuckDB は single-writer 制約がある。複数セッション同時実行で書き込み競合が発生する
- JSONL append は OS レベルでアトミック、依存ゼロ、並行安全

**却下した代替案**:
- DuckDB only: hook の遅延 + single-writer 問題
- SQLite: 分析クエリの柔軟性で DuckDB に劣る。JSONL 直接読みができない
- JSONL + project フィールドのみ: 読み込み側の集計コードが引き続き複雑

### 2. project フィールドの値

**選択**: `CLAUDE_PROJECT_DIR` 環境変数の末尾ディレクトリ名（`common.project_name_from_dir()` を使用）。

**理由**:
- `CLAUDE_PROJECT_DIR` は Claude Code が hook 実行時に設定する環境変数で、既に `usage-registry.jsonl` の記録に使用実績がある
- フルパスではなく末尾ディレクトリ名を使うことで、ユーザー名やパス構造に依存しない

### 3. DuckDB クエリ層の配置

**選択**: `scripts/lib/telemetry_query.py` に共通クエリ関数を配置する。

**理由**:
- discover, audit, analyze が同じ JSONL を読むため、クエリロジックの重複を避ける
- `scripts/lib/` には既に `agent_classifier.py`, `line_limit.py` 等の共通モジュールがある

### 4. 既存データの扱い

**選択**: `project IS NULL` のレコードは「不明」として扱い、project フィルタ指定時はデフォルトで除外する。`--include-unknown` フラグで含める選択肢を残す。

**理由**:
- 既存データの大半は backfill 由来で、project 情報がない
- 混入を防ぐには除外がデフォルトであるべき
- 全体統計を見たいケース（audit の global 集計）のためにフラグを用意する

### 5. analyze.py の既存 session ベースフィルタとの関係

**選択**: 新方式（usage.jsonl の `project` フィールドで直接フィルタ）と既存方式（sessions.jsonl → `get_project_session_ids()` → session_id ベースフィルタ）は共存する。analyze.py は当面既存方式を維持し、discover/audit は新方式に移行する。

**理由**:
- analyze.py の session ベースフィルタはワークフロー分析に特化しており、session 単位の紐付けが必要。project フィールドだけでは代替できない
- discover/audit は session 単位の紐付けが不要で、project フィールドによる直接フィルタが適切
- 将来的に analyze.py も telemetry_query.py 経由に移行可能だが、本 change のスコープ外とする

### 6. DuckDB の corrupt JSONL 行ハンドリング

**選択**: `read_json_auto(ignore_errors=true)` を使用し、不正な JSON 行はサイレントにスキップする。

**理由**:
- observe hook のクラッシュ等で不完全な行が発生し得る
- 分析用途では一部行の欠落よりクエリ全体の失敗の方が深刻
- エラー行の有無はクエリ結果に影響しないため、ログ出力も不要

## Risks / Trade-offs

- **duckdb 依存の追加 (~80MB)**: rl-anything は既に scipy に依存しており、サイズ増加は許容範囲。read 側のみなので hook には影響なし → hook の requirements.txt には追加しない
- **DuckDB の JSONL パース性能**: 1万行程度なら `read_json_auto()` で十分高速。将来的に 10万行超になった場合は Parquet アーカイブを検討
- **project 名の衝突**: 異なるパス配下の同名ディレクトリは同一 project として扱われる。rl-anything の利用形態では実質的に問題にならない
