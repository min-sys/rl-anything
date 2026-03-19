Related: #34

## Context

issue #34 のフィードバックで、ワークフロースキル（verify, archive 等）が汎用ステップのみで構成されているため、プロジェクト固有のチェック（例: インフラデプロイ確認）が漏れるパターンが報告された。

現状の `evolve-skill` はスキル単体の自己進化パターン（Pre-flight, pitfalls.md, Failure-triggered Learning）を注入するが、**ワークフロー全体を分析して不足チェックポイントを特定する**機能は持っていない。`verification_catalog` はプロジェクト全体の検証パターンを検出するが、特定スキルへのチェックポイント注入提案は行わない。

## Goals / Non-Goals

**Goals:**
- テレメトリからワークフロースキルの失敗・修正パターンを分析し、不足チェックポイントを特定する
- ドメイン固有チェックポイントテンプレート（インフラデプロイ、データマイグレーション等）を提供する
- evolve-skill / discover / evolve パイプラインに統合し、提案→承認→注入のフローを実現する

**Non-Goals:**
- チェックポイントの自動注入（人間承認必須）
- 既存の verification_catalog の置き換え（補完関係）
- ワークフロースキル以外のスキルへのチェックポイント提案

## Decisions

### D1: 新モジュール `scripts/lib/workflow_checkpoint.py` に集約

**決定**: チェックポイント検出エンジンとテンプレートカタログを1モジュールに集約する。
**理由**: verification_catalog.py はプロジェクト全体の検証ニーズ検出用で、スキル単位のチェックポイント注入とは責務が異なる。skill_evolve.py に追加すると肥大化する。独立モジュールにして evolve-skill / discover / remediation から呼び出す。
**代替案**: verification_catalog.py を拡張 → 責務の混在で保守性低下

### D2: ワークフロースキル判定ロジック

**決定**: SKILL.md の frontmatter `type: workflow` を第1候補とし、未宣言の場合はヒューリスティクスでフォールバック判定する。
**判定ロジック**:
1. **frontmatter 優先**: SKILL.md frontmatter に `type: workflow` が存在すれば即 True
2. **ヒューリスティクスフォールバック**（frontmatter なしの場合）:
   - 基準A: `Step`/`Phase`/`ステップ`/`フェーズ` キーワードが numbered list 内に存在
   - 基準B: numbered markdown list（`1.` `2.` `3.`...）が3項目以上存在
   - 基準C: `Input`/`Output`/`入力`/`出力` キーワードが存在
   - 判定: 基準A+B の両方が成立で True、または基準A のみで numbered list 5項目以上で True
3. **evolve-skill 連携**: `type: workflow` frontmatter 未宣言のワークフロースキルには frontmatter 追加を提案可能

**理由**: frontmatter 宣言により誤判定を回避し、ヒューリスティクスは後方互換のフォールバックとして機能する。
**代替案**:
- ヒューリスティクスのみ → false positive/negative が高く、非ワークフロースキルの誤判定リスク
- frontmatter 必須 → 既存スキルが全て未対応のため、導入初期に機能しない

### D3: チェックポイントテンプレートカタログの構造

**決定**: `CHECKPOINT_CATALOG` を Python dict のリストとして定義。各エントリに `id`, `category`, `description`, `detection_fn`, `applicability`, `template` を持つ。verification_catalog と同じ `detection_fn` パターンを採用し、`_CHECKPOINT_DETECTION_DISPATCH` dict で関数解決する。
**フィールド**:
- `id`: 一意識別子（kebab-case）
- `category`: カテゴリ名
- `description`: チェックポイントの説明
- `detection_fn`: テレメトリ照合用の検出関数名（`detect_infra_deploy_gap()` 等）
- `applicability`: 適用条件の判定関数名（None=常時適用）
- `template`: SKILL.md に注入するステップテンプレート

**カテゴリ**:
- `infra_deploy`: インフラ変更のデプロイ確認（IaC プロジェクトゲート付き、`detect_infra_deploy_gap()`）
- `data_migration`: DB スキーマ変更のマイグレーション確認（`detect_data_migration_gap()`）
- `external_api`: 外部 API 影響のロールバック確認（`detect_external_api_gap()`）
- `secret_rotation`: シークレット/認証情報変更の確認（`detect_secret_rotation_gap()`）

**理由**: verification_catalog と同じ `detection_fn` インターフェースにすることで、将来的な統合や拡張が容易。キーワードリストではなく関数にすることで、カテゴリごとに異なる検出ロジック（重み付け、複合条件等）を実装できる。
**代替案**: YAML/JSON 外部ファイル → 起動コスト増、テスト複雑化

### D4: evolve-skill への統合方法

**決定**: `assess_single_skill()` の結果に `workflow_checkpoints` フィールドを追加。ワークフロースキル判定が True の場合のみチェックポイント検出を実行し、提案リストを返す。
**理由**: 既存の5軸スコアリングとは独立した補助情報として提供。スコアリング自体は変更しない。
**代替案**: 6軸目としてスコアリングに組み込む → チェックポイント有無がスコアに影響し、非ワークフロースキルが不利になる

### D5: discover への統合方法

**決定**: `run_discover()` の結果に `workflow_checkpoint_gaps` フィールドを追加。全ワークフロースキルを走査し、不足チェックポイントを一覧化する。
**理由**: 既存の verification_needs と並列のレポートセクションとして、evolve レポートの Step 10 で表示。
**代替案**: verification_needs に統合 → スキル単位 vs プロジェクト単位の区別が曖昧になる

### D6: remediation との統合

**決定**: issue_schema に `WORKFLOW_CHECKPOINT_CANDIDATE` 定数を追加。remediation の FIX_DISPATCH / VERIFY_DISPATCH に対応ハンドラを登録。fix アクションはスキルの SKILL.md にチェックポイントステップを追記する proposable 提案。
**理由**: 既存の remediation パイプラインに乗せることで、confidence-based 分類と人間承認フローを再利用できる。
**代替案**: evolve-skill 専用の適用フロー → remediation との二重管理

## Risks / Trade-offs

- **[ワークフロー判定の精度]** → ヒューリスティクスのため false positive/negative が発生しうる。初期は保守的に判定し、テレメトリで精度を改善する
- **[テンプレートカタログの網羅性]** → 初期は4カテゴリ。ユーザーフィードバックとテレメトリで拡張する。カスタムテンプレート追加は将来課題
- **[SKILL.md 編集とプラグイン保護]** → skill_origin.py の保護チェックを経由し、プラグインスキルへの直接編集は proposable に降格する（既存の remediation パターンと同じ）
