## Context

rl-anything は Claude Code のスキル/ルールを遺伝的アルゴリズムで最適化する plugin。現在、評価関数は組み込み2種（`default`: LLM汎用評価、`skill_quality`: ルールベース構造チェック）とプロジェクト固有関数（手動作成）の3パターン。atlas-breeaders では手動で `narrative_fitness.py` を作成済みだが、docs-platform・ooishi-kun 等への展開時に毎回手動作成が必要で導入障壁が高い。

## Goals / Non-Goals

**Goals:**
- `/generate-fitness` スキル実行で、インストール先PJの特性を分析し fitness 関数を自動生成
- 生成された関数は既存の `--fitness {name}` でそのまま利用可能
- LEARN-Opt パターン（自然言語記述からメトリクスを自律設計）を採用

**Non-Goals:**
- 既存の `default` / `skill_quality` 関数の変更
- fitness 関数自体の進化的最適化（将来スコープ）
- DSPy / EvoAgentX 等の外部フレームワーク統合

## Decisions

### 1. 2段階パイプライン（分析→生成）

**選択**: analyze-project.py（ルールベース分析）→ Claude CLI で fitness 関数コード生成

**代替案**:
- A) 全工程を LLM に任せる → 分析結果が不安定、再現性が低い
- B) 全工程をルールベースにする → ドメインの多様性に対応困難

**理由**: 分析フェーズはプロジェクト構成ファイルの読み取り+キーワードマッチで十分確定的。生成フェーズは criteria に基づくPythonコード生成なので LLM が適切。

### 2. analyze-project.py はルールベース（LLM不使用）

**選択**: CLAUDE.md 等のキーワード頻度分析でドメイン推定

**代替案**: LLM に CLAUDE.md を渡してドメイン判定 → 遅い・コスト高・オフラインで動かない

**理由**: rl-scorer エージェントが既にドメイン自動判定ロジックを持っており、同様のアプローチで十分。rules/ や skills/ のファイル名・内容からの keyword extraction で高精度に推定可能。

### 3. 生成は Claude CLI (`claude -p`) + テンプレート

**選択**: fitness-template.py をスケルトンとして Claude CLI に渡し、criteria に基づいて穴埋め

**代替案**: Jinja2 テンプレートで変数置換 → 評価ロジックの自然言語→コード変換が困難

**理由**: 既存の optimize.py が同じパターン（`claude -p --model sonnet`）を使用しており、依存追加なし。テンプレートで構造を固定し、LLM はロジック部分のみ生成するため品質が安定。

### 4. 生成先は `scripts/rl/fitness/{domain}.py`

**選択**: ドメイン名をファイル名に使用（例: `documentation.py`, `bot.py`, `game.py`）

**理由**: 既存の `--fitness {name}` が `scripts/rl/fitness/{name}.py` を検索する仕組みと完全互換。ユーザーは `--fitness documentation` で即利用可能。

### 5. 運用知見（pitfalls.md）の取り込み

**選択**: analyze-project.py の分析対象に `references/pitfalls.md` を追加。存在する場合のみ anti_patterns に取り込む（オプショナル）

**代替案**: pitfalls.md 連携を独立した change として設計 → スコープが膨らみ、pitfalls.md がないプロジェクトでの graceful degradation 設計が複雑化

**理由**: pitfalls.md は skill-evolve 等で蓄積される「実行中に発見した失敗パターン」の記録。これを fitness 関数の anti_patterns に自動反映すれば、「ランタイム知見 → 評価基準 → スキル文面改善」のフィードバックループが成立する。疎結合な設計（ファイルがあれば読む、なければスキップ）により、pitfalls.md を手動で書いているプロジェクトにも同じ恩恵がある

### 6. ドメイン推定の共有化方針

**選択**: generate-fitness-skill の project-analyzer と rl-scorer エージェント（agents/rl-scorer.md）はいずれもドメイン推定（game/documentation/bot/general）を行う。現時点では独立実装とし、将来的に共通モジュールへの統合を検討する

**理由**: rl-scorer は LLM ベース（CLAUDE.md を読んで推定）、project-analyzer はルールベース（キーワード頻度）でアプローチが異なる。統合には両者のインターフェース統一が必要で、現段階では各機能の安定化を優先する

**将来計画**: 両者のドメイン分類が安定した後、`lib/domain-detector.py` として共通化を検討

## Risks / Trade-offs

- **[ドメイン誤判定]** → CLAUDE.md の内容が薄い場合、汎用 (`general`) にフォールバック。生成後にユーザーが手動調整可能
- **[生成コードの品質]** → テンプレートで構造を固定し、LLM は評価ロジック部分のみ生成。生成後に `--dry-run` で動作確認を促す
- **[Claude CLI 未インストール]** → analyze-project.py は動作する。生成フェーズのみ失敗し、分析結果JSONを出力して手動生成を案内
