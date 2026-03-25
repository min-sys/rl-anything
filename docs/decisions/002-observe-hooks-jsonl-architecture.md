# ADR-002: Observe Hooks JSONL Architecture

Date: 2026-03-02
Status: Accepted

## Context

rl-anything は `/optimize` と `/rl-loop` による既存スキルの改善のみを提供していた。環境全体（skills / rules / memory / CLAUDE.md）のライフサイクル管理がなく、スキルの発見・淘汰・肥大化制御・フィードバック収集は手動に頼っていた。「発見 -> 生成 -> 最適化 -> 淘汰」の全ライフサイクルを管理し、使えば使うほど環境が賢くなる自律進化エンジンへの拡張が必要だった。

## Decision

- **観測は async hooks + JSONL 追記のみ**: PostToolUse / Stop / PreCompact / SessionStart の async hooks で regex + 集計のみ実行。LLM 呼び出しなし、コストゼロ。Homunculus v1->v2 の知見から Hook 観測は 100% 信頼、スキル観測は 50-80%
- **構造的制約はコードで強制**: 生成/更新パイプラインで行数バリデーション（SKILL.md 500行、rules 3行、memory 120行）。プロンプトでの制約は32世代実験で2回失敗したため不採用
- **淘汰はアーカイブ方式（削除しない）**: `.claude/rl-anything/archive/` に退避し、復元コマンドを用意。30日ルール。直接削除は誤判断時の回復コストが高い
- **Global スコープは Usage Registry で安全管理**: global スキル使用時にプロジェクトパスも記録し、Prune は全プロジェクトの使用データを参照して判断
- **Discover の閾値は 5+ クラスタでスキル候補、3+ でルール候補**: 複数回検出を必須とし過学習を防止。3行ルールが抽象化を強制
- **段階的実装（8ステップ）**: Observe -> Audit/Report -> Prune -> Discover -> Evolve統合 -> Optimize拡張 -> Fitness進化 -> Bloat制御。各ステップが前のステップのデータに依存
- **フィードバックは GitHub Issue 経由**: gh CLI で Issue 作成。プレビュー必須。スキル内容/パスを含めない

## Alternatives Considered

- **セッション終了時に LLM でサマリ生成**: コスト発生 + UX 影響があるため不採用
- **プロンプトで「膨張するな」と指示**: 32世代実験で2回失敗。コードによる行数制限が安定
- **直接削除方式**: 誤判断時の回復コストが高い。全成熟ツールのコンセンサスとしてアーカイブ方式を採用
- **Global は一切 Prune しない**: 際限なく増加するため不採用
- **現プロジェクトのデータのみで判断**: 他PJで使用中のスキルを誤淘汰するリスク
- **1回の検出でもスキル候補生成**: 過度に一般化するリスク

リスクとして、モデル崩壊は全変更に人間レビューで軽減、過学習は複数回検出閾値で軽減、観測コスト爆発は async hook + LLM 呼び出しなしで軽減、Goodhart's Law は adversarial probe と Pareto ベース選択で軽減する。

## Consequences

**良い影響:**
- LLM コストゼロの観測基盤により、使用状況・エラー・セッション情報を自動蓄積する仕組みが確立
- Observe -> Discover -> Optimize -> Prune -> Report の全ライフサイクルを `/evolve` ワンコマンドで実行可能に
- コードによる構造的制約で環境の肥大化を確実に防止
- アーカイブ方式により安全な淘汰を実現

**悪い影響:**
- JSONL ファイルが蓄積し続けるためストレージ管理が必要
- Usage Registry の append-only 設計によりファイルロックなしで運用するが、破損時は再集計が必要
- 段階的実装のため全機能が揃うまでに時間がかかる
