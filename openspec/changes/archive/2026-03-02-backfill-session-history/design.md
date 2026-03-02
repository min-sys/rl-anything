## Context

rl-anything の observe hooks（PostToolUse, SubagentStop）は Claude Code セッション中のツール呼び出しを JSONL に記録するが、導入前のセッション履歴は対象外。Claude Code は `~/.claude/projects/<encoded-path>/*.jsonl` にセッショントランスクリプトを保存しており、`type: "assistant"` レコード内の `tool_use` ブロックから Skill/Agent 呼び出しを復元できる。

トランスクリプトのレコード構造:
```json
{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "...", "args": "..."}}]}, "uuid": "...", "timestamp": "...", "sessionId": "..."}
```

現在のプロジェクト数: 16、セッション総数: 786+

## Goals / Non-Goals

**Goals:**
- 既存セッショントランスクリプトから Skill/Agent ツール呼び出しを抽出し usage.jsonl に書き出す
- バックフィルデータに `source: "backfill"` を付与してリアルタイムデータと区別する
- べき等性を保証し、重複バックフィルを防止する
- `/rl-anything:backfill` スキルとして任意のプロジェクトで実行可能にする

**Non-Goals:**
- SubagentStop イベントのバックフィル（トランスクリプトに SubagentStop イベントデータは含まれないため不可）
- エラーの完全な復元（tool_result の is_error フラグはトランスクリプト構造では取得困難な場合がある）
- sessions.jsonl のバックフィル（セッション要約は usage データから事後計算可能）

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | `skills/backfill/scripts/backfill.py` に実装し `hooks/common.py` を再利用 | 既存の `skills/*/scripts/` パターンに準拠。`hooks/` はイベント駆動フック専用とし、CLI ツールはスキルの scripts/ に配置。`sys.path` でプラグインルートを追加し `hooks/common.py` の `append_jsonl` / `DATA_DIR` を共有 |
| 2 | プロジェクトディレクトリのエンコード規則を `claude projects` コマンドの慣例に従う | `~/.claude/projects/` のディレクトリ名は `pwd` のパスを `-` 区切りに変換した形式（例: `/Users/foo/bar` → `-Users-foo-bar`）|
| 3 | 重複防止は既存 JSONL の session_id + source=backfill をセットでチェック | 全レコードスキャンのコストはあるが、JSONL ファイルは通常数千行以下。シンプルさを優先 |
| 4 | スキルで提供（`/rl-anything:backfill`）| ユーザーが任意のタイミングで実行可能。evolve の前提条件としても使える |
| 5 | timestamp はトランスクリプトのレコード timestamp をそのまま使用 | バックフィル実行時刻ではなく、実際のツール呼び出し時刻を記録することで正確な時系列分析が可能 |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| トランスクリプト形式が Claude Code バージョンで変わる | パース失敗時はスキップしてサマリに含める。形式変更に対する堅牢性を重視 |
| 大量セッション（数百）のパースに時間がかかる | 進捗表示を含め、セッション単位で逐次処理。タイムアウトなし |
| `~/.claude/projects/` のディレクトリ名エンコード規則の変更 | 現行の `-` 区切り規則をハードコードせず、ディレクトリ一覧から部分一致で検索 |
