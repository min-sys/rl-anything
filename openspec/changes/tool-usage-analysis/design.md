## Context

discover は現在、usage.jsonl（スキル/エージェント呼び出し）・errors.jsonl・sessions.jsonl・history.jsonl からパターンを検出する。
しかしセッション JSONL に記録されている**ツール呼び出し（tool_use）**の詳細は未活用。
特に Bash コマンドの中身を分析すれば、繰り返しパターン（＝スキル化候補）やルール違反（cat/grep/find → 専用ツール代替可能）を自動検出できる。

セッション JSONL は `~/.claude/projects/<project-slug>/*.jsonl` に格納されており、
backfill の `parse_transcript()` がすでにパース基盤を提供している。

## Goals / Non-Goals

**Goals:**
- セッション JSONL からツール呼び出し（tool_use）を抽出し、ツール別の利用回数を集計する
- Bash コマンドを3カテゴリに分類する: built-in 代替可能 / 繰り返しパターン（スキル化候補）/ CLI 正当利用
- 分類結果を discover の既存候補フローに合流させる（`run_discover()` の結果に含める）
- evolve が discover の結果を通じてツール利用分析を表示・改善提案に含める

**Non-Goals:**
- Bash 利用回数の削減自体を目的としない（指標であり目的ではない）
- Read/Edit/Write 等の Core I/O ツールの詳細分析（量は作業量に比例するだけ）
- セッション JSONL のリアルタイム監視（バッチ分析のみ）
- openspec 等の外部 CLI 呼び出しを「問題」として扱うこと

## Decisions

### D1: 分析ロジックの配置場所

**決定**: `scripts/lib/tool_usage_analyzer.py` に共通モジュールとして配置し、discover.py から呼び出す。

**理由**: telemetry_query.py と同層に置くことで、discover 以外（audit レポート等）からも再利用可能。
discover.py に直接書くと肥大化する（現在619行）。

**代替案**: discover.py 内に追加 → 単一ファイルが大きくなりすぎる。telemetry_query.py に追加 → 責務が異なる（telemetry_query は JSONL クエリ層、これは分析層）。

### D2: Bash コマンドの分類方式

**決定**: ルールベース分類（正規表現 + コマンド先頭語マッチ）。3カテゴリ:

| カテゴリ | 判定基準 | discover での扱い |
|----------|----------|-------------------|
| `builtin_replaceable` | cat/grep/rg/find/head/tail/wc/sed/awk → Read/Grep/Glob/Edit 代替可能 | ルール候補 |
| `repeating_pattern` | 同一コマンドパターンが閾値以上出現 | スキル候補 |
| `cli_legitimate` | git/gh/pip/npx 等の外部 CLI | info_only |

**理由**: LLM 呼び出し不要（型A パターン）で高速。コマンド先頭語ベースの分類は十分な精度が出る（会話中の分析で実証済み）。

**cat の除外パターン**: コマンド文字列に `<<`（heredoc）、`>`/`>>`（リダイレクト出力）が含まれる場合は builtin_replaceable から除外する。これらは Read 代替ではなくファイル作成/追記用途。パイプ入力（`| cat`）は Read 代替可能として検出対象に含める。

**代替案**: LLM で分類 → コスト高・遅い。完全な AST パース（bashlex 等） → 過剰。`shlex.split()` による補助的トークン分離 → シェル構文の完全パースは保証しないが、リダイレクト記号がファイル名の一部かどうかの誤判定を防げる。現段階ではシンプルな文字列マッチで十分な精度が出るため不採用とするが、誤判定が頻発した場合に導入を検討する。

### D3: セッション JSONL の読み込み方式

**決定**: backfill の `parse_transcript()` は使わず、JSONL 行読み込みには `telemetry_query._load_jsonl()` を再利用し、tool_use エントリのフィルタリングのみ独自ロジックで行う。

**理由**: parse_transcript() はワークフロー構築用の重いパーサー。ツール呼び出しの抽出だけなら、JSONL を1行ずつ読んで `message.content[].type == "tool_use"` をフィルタするだけで十分。
対象プロジェクトのセッションファイルのみをスキャンする（全プロジェクト横断は不要）。

**セッションディレクトリの解決**: discover.py の既存パターン（`CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"`）に従い、`project_root` から `project_root.name` でプロジェクト名を取得し、`~/.claude/projects/` 配下の一致するディレクトリを検索する。`extract_tool_calls()` の引数は `project_root: Optional[Path]` とし、discover.py の `run_discover(project_root=...)` と同じインターフェースに揃える。

### D4: 繰り返しパターンの検出単位

**決定**: Bash コマンドの「先頭語 + サブコマンド」でグルーピング（例: `git add`, `python3 -m pytest`, `openspec status`）。
さらに、先頭語ごとにサブカテゴリ分類を行う（例: python3 → pytest / inline-analysis / named-script）。

**理由**: 完全一致だと個別のファイルパスで分散しすぎる。先頭語だけだと粒度が粗すぎる。
2語レベルのグルーピングが最適なバランス。

**代替案**: コマンド全体のファジーマッチ（編集距離ベース） → 実装が複雑で誤マッチリスクが高く、現規模では過剰。n-gram ベースのクラスタリング → ML 依存で説明可能性が低下。

### D5: discover 結果への統合方式

**決定**: `run_discover()` の結果に `tool_usage_patterns` キーを追加。既存の behavior_patterns 等と並列。

```python
{
    "behavior_patterns": [...],
    "error_patterns": [...],
    "tool_usage_patterns": {
        "builtin_replaceable": [...],   # ルール候補
        "repeating_patterns": [...],     # スキル候補
        "cli_summary": {...},            # info_only
        "total_tool_calls": int,
        "bash_calls": int,
    }
}
```

**理由**: 既存構造を壊さず追加できる。evolve の discover フェーズ表示に自然に含められる。

**代替案**: OpenTelemetry 的な標準テレメトリ層を導入し、全テレメトリデータを統一的に処理 → 業界標準だが現プラグインの規模では過剰。将来的にテレメトリソースが増えた場合に検討する。

## Risks / Trade-offs

- **[パフォーマンス]** セッション JSONL の全スキャンは大量ファイルで遅い可能性
  → Mitigation: プロジェクトスコープでフィルタ + 前回 evolve 以降のセッションのみ対象（evolve-state.json の timestamp 利用）
- **[分類精度]** ルールベースのコマンド分類は未知のパターンを取りこぼす
  → Mitigation: `cli_legitimate` をデフォルトにし、明示的にマッチしたもののみ `builtin_replaceable` / `repeating_pattern` に分類
- **[セッション JSONL 形式変更]** Claude Code のアップデートで JSONL 形式が変わる可能性
  → Mitigation: パースエラー時は graceful にスキップ（既存の discover パターンと同じ方針）
