# ADR-011: Auto-Compression Trigger

Date: 2026-03-09
Status: Accepted

## Context

audit スキルは bloat check レポート（CLAUDE.md/MEMORY.md 行数、rules/skills 総数）を出力し、`bloat_check()` がプログラマティックに肥大化を検出できるが、検出は `/audit` 手動実行時のみだった。セッション間で bloat が進行しても気づけず、MEMORY.md 200行ハードリミット到達やルール遵守率低下が起きてから対処する後追い状態にあった。auto-evolve-trigger（ADR-010）で session_end 時のトリガーエンジンが整備済みであり、同パターンに bloat 条件を追加する。

## Decision

- **`evaluate_session_end()` 内に bloat トリガーを統合**: bloat を別関数にすると呼び出し側で結果をマージする必要があるため、既存の reasons/actions リストに追加するのが最もシンプル
- **`CLAUDE_PROJECT_DIR` 環境変数から project_dir を取得**: `evaluate_session_end()` に keyword-only パラメータ `project_dir` を追加。未設定時は bloat 評価をスキップ
- **閾値は `bloat_control.BLOAT_THRESHOLDS` を single source of truth とし、trigger_config には `enabled` のみ格納**: 閾値の DRY 違反を防止
- **全 bloat 種別で `/rl-anything:evolve` を提案**: evolve の Compile ステージが全レイヤーの問題に対応し、ユーザーが1コマンドで対処可能
- **専用 reason `"bloat"` で既存のクールダウン機構を利用**: 全 bloat サブタイプで共有し、bloat 警告の頻度を抑えてユーザー体験を優先
- **lazy import パターン**: trigger_engine.py から bloat_control.py への transitive import チェーンを回避するため、`evaluate_bloat()` 内で lazy import し ImportError 時はサイレントスキップ

## Alternatives Considered

- **bloat トリガーを `evaluate_session_end()` とは別関数にする**: 呼び出し側で結果マージが必要になるため却下。既存フローへの統合が最もシンプル
- **trigger_config に bloat 閾値も格納する**: `bloat_control.BLOAT_THRESHOLDS` との DRY 違反になるため却下
- **bloat サブタイプごとに個別の reason でクールダウン管理**: 毎セッションで別種の bloat 警告が出る可能性があり、ユーザー体験を損なうため却下
- **モジュールレベル import**: 循環 import や起動時エラーのリスクがあるため lazy import を採用

## Consequences

**良い影響:**
- MEMORY.md / CLAUDE.md / rules / skills の肥大化がセッション終了時に自動検出され、ハードリミット到達前に圧縮アクションを提案できる
- bloat_check() はファイルシステム走査のみで LLM コストゼロ、セッション終了時の追加遅延は無視できるレベル
- `enabled: false` で無効化可能、意図的に大量ルールを持つプロジェクトにも対応

**悪い影響:**
- bloat reason が全サブタイプで共有されるため、あるサブタイプで発火後に別サブタイプが閾値超過してもクールダウン内は抑制される（ユーザー体験優先の意図的なトレードオフ）
- lazy import によりテスト時の import パス制御がやや煩雑になる
