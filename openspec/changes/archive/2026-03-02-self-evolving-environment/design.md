## Context

rl-anything は Claude Code plugin として遺伝的アルゴリズムベースのスキル最適化を提供している。
現状は `/optimize` と `/rl-loop` による既存スキルの改善のみ。

環境全体（skills / rules / memory / CLAUDE.md）のライフサイクル管理がなく、
スキルの発見・淘汰・肥大化制御・フィードバック収集は手動に頼っている。

既存コンポーネント:
- `genetic-prompt-optimizer` — LLM でバリエーションを生成し、適応度関数で評価して進化
- `rl-loop-orchestrator` — ベースライン取得→バリエーション生成→評価→人間確認のループ統合
- `rl-scorer` エージェント — 技術品質 + ドメイン品質 + 構造品質の3軸で採点
- `generate-fitness` — プロジェクト分析から評価関数を自動生成

## Goals / Non-Goals

**Goals:**
- 環境の全ライフサイクル（Observe → Discover → Optimize → Prune → Report）を管理
- 観測はコストゼロ（async hooks、LLM 呼び出しなし）
- 全変更は人間承認が必要（自動適用なし）
- コードによる構造的制約で肥大化を防止
- 評価関数の自己改善（score-acceptance 相関追跡）
- Global/Project スコープの最適化提案（Usage Registry）

**Non-Goals:**
- Claude Code 本体の機能変更やパッチ
- 他ユーザーの環境への自動同期
- 完全自律的な環境変更（人間承認を省略しない）
- claude-reflect への依存（センサーとして利用するが必須にしない）
- GEPA による fitness prompt 自体の自動最適化（将来検討）

## Decisions

### 1. 観測は async hooks + JSONL 追記のみ

**選択**: PostToolUse / Stop / PreCompact / SessionStart の async hooks で、
regex + 集計のみ実行。LLM 呼び出しなし。

**代替案**: セッション終了時に LLM でサマリ生成 → コスト発生 + UX 影響あり
**根拠**: Homunculus v1→v2 の知見。Hook 観測は 100% 信頼、スキル観測は 50-80%。
コスト管理と UX 影響ゼロを両立。

注: state checkpoint（PreCompact hook）は JSON シリアライズのみ（10-100ms 程度）。LLM 呼び出しなしの意味でコストゼロ。

### 2. 構造的制約はコードで強制

**選択**: 生成/更新パイプラインで行数バリデーション（SKILL.md 500行、rules 3行、memory 120行）

**代替案**: プロンプトで「膨張するな」と指示 → 32世代実験で2回失敗
**根拠**: コード強制なら32世代安定。プロンプトでの制約は信頼できない。

### 3. 淘汰はアーカイブ方式（削除しない）

**選択**: `.claude/rl-anything/archive/` に退避。復元コマンドあり。30日ルール。

**代替案**: 直接削除 → 誤判断時の回復コストが高い
**根拠**: 全成熟ツール（claude-reflect、32世代実験）のコンセンサス。

### 4. Global スコープは Usage Registry で安全管理

**選択**: global スキル使用時にプロジェクトパスも記録。
Prune は全プロジェクトの使用データを参照して判断。

**代替案A**: global は一切 Prune しない → 際限なく増加
**代替案B**: 現プロジェクトのデータのみで判断 → 他PJで使用中のスキルを誤淘汰
**根拠**: コンテキストコスト（30-50 tokens/skill）は軽微だが、evolve の判断精度が重要。

### 5. フィードバックは GitHub Issue 経由

**選択**: gh CLI で Issue 作成。プレビュー必須。スキル内容/パスを含めない。

**代替案**: ローカルファイル保存のみ → 開発者へのフィードバックが届かない
**根拠**: プライバシー保護（送信前プレビュー）と開発者連携の両立。gh 未認証時はローカル保存にフォールバック。

### 6. Discover の閾値は 5+ クラスタでスキル候補、3+ でルール候補

**選択**: 複数回検出を必須とし、過学習を防止

**代替案**: 1回の検出でも候補生成 → 過度に一般化するリスク
**根拠**: Homunculus、claude-reflect 共通の閾値。3行ルールが抽象化を強制。

### 7. 段階的実装（8ステップ）

**選択**: Observe → Audit/Report → Prune → Discover → Evolve統合 → Optimize拡張 → Fitness進化 → Bloat制御

**根拠**: 各ステップが前のステップのデータに依存。観測データなしに発見・淘汰はできない。

## Risks / Trade-offs

| リスク | 緩和策 |
|--------|--------|
| ルール肥大化 | コードで行数制限を強制。evolve 時に自動チェック |
| モデル崩壊（自己生成データで品質退化） | 全変更に人間レビュー。自動適用は行わない |
| 過学習（1回の失敗から過度に一般化） | 複数回検出（3-5回）の閾値。3行ルールが抽象化を強制 |
| 観測コスト爆発 | async hook + LLM 呼び出しなし。JSONL 追記のみ |
| claude-reflect 依存 | 入力ソースの1つとして利用。未インストールでも動作 |
| 淘汰の誤判断 | アーカイブ方式（復元可能）。30日ルール。Usage Registry で cross-PJ 参照 |
| Goodhart's Law（スコアゲーミング） | adversarial probe、Pareto ベース選択、score 一貫性追跡 |
| Global skill の誤 Prune | Usage Registry でプロジェクト横断の使用データを参照 |
| Usage Registry 破損 | append-only JSONL 形式で書き込み。ファイルロック不使用（各PJが独立実行のため衝突リスクは低い）。破損時は再集計可能 |
| Discover の振動（reject → 再生成ループ） | 同一パターンのルール候補が2回 reject されたら、抑制リストに追加。3回目以降は提案しない |
