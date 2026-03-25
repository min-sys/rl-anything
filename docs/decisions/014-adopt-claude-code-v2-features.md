# ADR-014: Adopt Claude Code v2.1.x Features

Date: 2026-03-15
Status: Accepted

## Context

rl-anything は Claude Code Plugin として 13 スキル + 7 フック + 1 エージェント（rl-scorer）で構成されるが、Claude Code v2.1.x で追加された plugin/skill 向け新機能（`context: fork`、`${CLAUDE_SKILL_DIR}`、agent model 指定、skill hooks、auto-memory、worktree isolation、PostCompact、effort level 等）が未適用のまま残っており、コンテキスト効率・コスト・安全性に改善余地があった。

## Decision

- **context:fork**: evolve, audit, discover の 3 スキルに適用。大量出力がメインコンテキストを汚染するのを防止。詳細結果はファイル出力し親コンテキストから Read で参照可能にする。reflect/optimize/rl-loop 等の会話コンテキスト依存スキルは除外
- **${CLAUDE_SKILL_DIR}**: SKILL.md 内のスキルローカルファイル参照に使用。Python コードは `__file__` ベースのパス解決が既に安全なため変更不要
- **Agent model 指定戦略**: rl-scorer は sonnet（現状維持）、evolve LLM 評価は指定なし（inherit）、discover パターン検出は haiku でコスト最適化
- **auto-memory 協調**: reflect_utils.py の memory ルーティングに auto-memory 重複チェックを追加。Jaccard 類似度 0.6（セクション単位）で重複判定し、auto-memory が既にカバー済みならスキップ
- **worktree isolation**: optimize スキルの patch-apply-test サイクルを Agent tool（`isolation: "worktree"`）で隔離実行。自動クリーンアップを活用
- **PostCompact フック**: save_state.py を PostCompact としても登録。PreCompact の情報量を保護するため別キー（`post_compact_checkpoint`）に保存
- **effort level routing**: evolve の各フェーズに自然言語で effort 指示を追加（Diagnose=簡潔に、Compile=標準、Self-Evolution=慎重に）
- **memory mtime 活用**: layer_diagnose.py の stale_memory 検出にファイル mtime 参照を追加（90日以上で warning）。git 操作直後の false positive 緩和策付き
- **skill hooks**: evolve スキルに PostToolUse skill hook を追加し、remediation 後の構文チェック（regression_gate.py `--quick-check`）を自動化

## Alternatives Considered

- **context:fork を全スキルに一律適用**: 会話コンテキストに依存するスキルでは動作不良になるため却下
- **auto-memory を完全無効化**: ユーザー体験が悪化するため却下
- **rl-anything 側の memory 書き込みを廃止**: reflect の価値が減少するため却下
- **semantic embedding による重複判定**: 外部依存が増加、現時点では Jaccard で十分なため将来対応
- **optimize.py 内で git worktree を自前実装**: Agent tool の isolation 機能と重複するため却下
- **全モデルを opus/haiku に統一**: コスト過大または品質不足のため却下
- **effort level を API パラメータで直接制御**: Claude Code API に直接 effort パラメータを渡す手段がないため自然言語指示で対応

## Consequences

**良い影響:**
- evolve/audit/discover の大量出力がメインコンテキストを消費しなくなり、コンテキスト効率が大幅に改善
- ${CLAUDE_SKILL_DIR} によりテンプレートパスがポータブルになった
- optimize の worktree isolation によりパッチ適用が安全になった
- reflect と auto-memory の衝突が防止された
- Agent model 指定によるコスト最適化

**悪い影響:**
- context:fork でのスキルは AskUserQuestion が動作しないため、ユーザー承認が必要な操作は fork 復帰後にメインコンテキストで実施する必要がある
- worktree 作成に数秒のオーバーヘッドが発生（optimize は元々時間のかかる操作なので許容範囲）
- effort level の自然言語制御は厳密ではなく、効果が不十分な場合は将来の API 対応待ち
- Claude Code v2.1.0+ が必須要件となった
