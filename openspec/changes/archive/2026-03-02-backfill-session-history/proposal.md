## Why

rl-anything の observe hooks は次回セッション以降のデータしか収集できない。既存の Claude Code プロジェクトには `~/.claude/projects/` 配下に数百セッション分のトランスクリプト（JSONL）が蓄積されており、これをバックフィルすれば導入直後から evolve パイプラインを回せる。

## What Changes

- セッショントランスクリプトをパースし、Skill/Agent ツール呼び出し・エラーを抽出して既存の JSONL データストア（usage.jsonl, errors.jsonl, subagents.jsonl）に書き出すバックフィルスクリプトを追加
- バックフィルデータには `source: "backfill"` タグを付与し、リアルタイム hooks データと区別可能にする
- `/rl-anything:backfill` スキルとして提供し、任意のプロジェクトで実行可能にする

## Capabilities

### New Capabilities
- `backfill`: セッショントランスクリプトから observe データを抽出し JSONL にバックフィルする

### Modified Capabilities

## Impact

- 新規ファイル: `skills/backfill/scripts/backfill.py`（トランスクリプトパーサー＋JSONL 書き出し）
- 新規ファイル: `skills/backfill/SKILL.md`（ユーザー向けスキル定義）
- 既存の evolve / discover パイプラインはデータ形式が同じため変更不要
- 対象: `~/.claude/projects/<project-dir>/*.jsonl`（全セッション履歴）
