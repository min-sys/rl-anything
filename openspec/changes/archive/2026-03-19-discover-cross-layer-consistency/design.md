## Context

discover は verification_catalog.py 経由で「プロジェクト特性に応じた検証ルール提案」を行う仕組みを持つ。現在 3 エントリ（data-contract / side-effect / evidence-before-claims）が登録されており、各エントリは `applicability: "conditional"` + `detection_fn` でプロジェクトスキャンを行い、該当時のみルール提案する。

issue #32 では「コード↔IaC 間の整合性ミス」を検出するパターンの追加が提案されている。このパターンは AWS/IaC プロジェクト固有であり、全プロジェクトに適用すべきではない。

## Goals / Non-Goals

**Goals:**
- AWS プロジェクト判定ゲートを verification_catalog の applicability 機構に組み込む
- `os.environ.get()` / `process.env.` 参照と IaC 定義の突合検出
- `boto3.client()` / AWS SDK 使用と IAM 権限定義の突合検出
- 既存の discover → evolve → remediation データフローに自然統合

**Non-Goals:**
- IaC ファイルの構文解析（CDK TypeScript のASTパース等）は行わない
- 環境変数名とIaC定義値の厳密マッチング（LLM判断に委ねる）
- Terraform / Pulumi 等 AWS 以外の IaC はスコープ外
- Terraform HCL / Pulumi 等の個別パーサー実装
- remediation での自動修正（提案のみ）

## Decisions

### D1: verification_catalog への統合（vs RECOMMENDED_ARTIFACTS）

**選択**: verification_catalog に新エントリとして追加

**理由**: RECOMMENDED_ARTIFACTS は「全プロジェクト共通の推奨ルール/フック」で、ファイル存在チェックのみ。verification_catalog は `applicability: "conditional"` + `detection_fn` による条件付き検出を持ち、プロジェクト依存の検出パターンに適合する。

**代替案**: RECOMMENDED_ARTIFACTS に `applicability_gate` フィールドを追加 → 既存構造の変更が不要だが、RECOMMENDED_ARTIFACTS の責務（汎用推奨）と矛盾する。

### D2: IaC プロジェクト判定方式

**選択**: ファイル/ディレクトリ存在チェックベース

**判定対象**:
| マーカー | AWS IaC タイプ |
|---------|---------------|
| `cdk.json` | AWS CDK |
| `serverless.yml` / `serverless.yaml` | Serverless Framework |
| `sam-template.yaml` / `template.yaml` + `AWSTemplateFormatVersion` | AWS SAM |
| `*.template.json` / `*.template.yaml` + `AWSTemplateFormatVersion` | CloudFormation |

**理由**: LLM 不要、高速、false positive が低い。テレメトリ依存も不要。

**代替案**: テレメトリから `cdk deploy` / `terraform apply` 使用を検出 → データ蓄積が必要で初回検出に弱い。

### D3: 検出パターンの粒度

**選択**: 2カテゴリ（env-var-mismatch / iam-permission-gap）を1エントリにまとめる

**理由**: 両方とも「クロスレイヤー整合性」という同一の検証知見であり、ルールテンプレートも1つで十分。検出関数内で 2 パターンを走査し、evidence に分類を含める。

**代替案**: env-var と iam-permission を別エントリに分離 → カタログが肥大化し、同一プロジェクトで2件の類似ルール提案になるため不採用。

### D4: 検出ロジックの深さ

**選択**: コード側のパターン検出のみ（IaC 側は LLM エスカレーション用プロンプトで対応）

**理由**: IaC 定義ファイルのフォーマットは CDK(TypeScript/Python) / Terraform(HCL) / SAM(YAML) 等多岐にわたり、正確なパースは cost 対 benefit が悪い。コード側で `os.environ.get("NEW_VAR")` や `boto3.client("dynamodb")` を検出し、「IaC 定義と突合すべき」というルール提案を出す方がシンプルで汎用的。既存の `_iter_source_files()` / `_is_test_file()` を再利用し、ファイル走査・テストファイル除外は新規実装しない。

## Risks / Trade-offs

- **[False Positive]** `os.environ.get()` は IaC 以外でも一般的 → IaC プロジェクト判定ゲートで緩和。さらに `detection_fn` 内で閾値（MIN_PATTERNS）を設けることで、少数の参照では発火しない
- **[検出漏れ]** CDK の `environment: { VAR: value }` と コードの `os.environ["VAR"]` の名前一致は判定しない → llm_escalation_prompt に「変数名の突合確認」を含め、LLM 判断に委ねる
- **[IaC タイプ未対応]** Terraform / Pulumi 等の非 AWS IaC はスコープ外。将来の拡張はマーカー追加で可能
