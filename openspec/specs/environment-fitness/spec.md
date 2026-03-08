# environment-fitness Specification

## Purpose
Coherence Score（構造品質）と Telemetry Score（行動実績）をブレンドした統合 environment fitness スコア。テレメトリデータ充足時は行動実績を重視し、不足時は構造品質のみに安全にフォールバックする。

## Requirements
### Requirement: Environment fitness blending
`compute_environment_fitness()` SHALL blend Coherence Score and Telemetry Score into a single environment fitness.

- テレメトリデータ充足時: coherence * 0.4 + telemetry * 0.6
- テレメトリデータ不足時: coherence のみ（1.0 weight）
- 返却 dict に sources リスト（使用したスコアソース名）を含める
- Phase 2-3 追加時の拡張ポイントを設計に含める

#### Scenario: Both sources available
- **WHEN** Coherence Score = 0.8, Telemetry Score = 0.7（data_sufficiency=True）
- **THEN** overall = 0.8 * 0.4 + 0.7 * 0.6 = 0.74, sources = ["coherence", "telemetry"]

#### Scenario: Telemetry data insufficient
- **WHEN** Coherence Score = 0.8, Telemetry data_sufficiency = False
- **THEN** overall = 0.8, sources = ["coherence"]

### Requirement: Environment fitness CLI interface
`environment.py` は `--fitness` フラグでは使用しない（既存 fitness インターフェースは stdin にスキル内容を受け取るため互換性がない）。代わりに argparse ベースの CLI を提供する: `python3 environment.py <project_dir> [--days N]`。audit 統合のみが公開インターフェースとなる。

#### Scenario: CLI invocation
- **WHEN** `python3 environment.py /path/to/project --days 30` を実行する
- **THEN** stdout に JSON 形式のスコア結果（overall, sources, sub-scores）が出力される

### Requirement: Edge case handling

#### Scenario: Coherence score failure
- **WHEN** `compute_coherence_score()` が例外を発生させた場合
- **THEN** `compute_environment_fitness()` は coherence を 0.0 として扱い、telemetry データが充足していれば telemetry スコアのみで算出する（sources = ["telemetry"]）。両方失敗した場合は overall = 0.0, sources = [] を返す

#### Scenario: Empty project (no artifacts)
- **WHEN** プロジェクトディレクトリに `.claude/skills/` や `.claude/rules/` が存在しない
- **THEN** `compute_environment_fitness()` は overall = 0.0, sources = [] を返す
