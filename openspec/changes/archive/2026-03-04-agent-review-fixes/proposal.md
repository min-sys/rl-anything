## Why

ambiguous-intent-resolver と updater-senior-engineer による多角的レビューで、rl-anything v0.12.0 の品質・運用性・セキュリティに関する5つの優先改善項目が特定された。プラグインの信頼性とオンボーディング体験を向上させるために対応する。

## What Changes

- README.md の evolve フロー記述を実装（7フェーズ）に合わせて更新
- `scripts/` と `skills/*/scripts/` の二重管理を解消（5ファイル: discover, evolve, audit, aggregate_runs, fitness_evolution）
- Before/After を体感できるクイックスタートチュートリアルを README に追加
- corrections の偽陽性を報告できるフィードバック機構を追加
- LLM 入力サニタイズ方針を明確化し、corrections.jsonl のパーミッション設定を追加

## Capabilities

### New Capabilities
- `correction-false-positive`: corrections の偽陽性をユーザーが報告・除外できる機構
- `input-sanitization`: LLM に渡す corrections データのサニタイズとファイルパーミッション強化

### Modified Capabilities
- `readme-update`: evolve フロー記述の実装同期 + Before/After チュートリアル追加
- `correction-detection`: 偽陽性フィードバックの受け入れ対応

## Impact

- `scripts/` 直下の5ファイル削除、`skills/*/scripts/` に一本化
- `hooks/common.py`: パーミッション設定追加、偽陽性フィルター拡張
- `README.md`: evolve フロー・チュートリアルセクション追加
- テスト: 二重管理解消に伴う import パス修正
