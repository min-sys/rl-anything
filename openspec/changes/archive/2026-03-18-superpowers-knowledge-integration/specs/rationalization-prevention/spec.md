## ADDED Requirements

### Requirement: corrections からスキップパターンを検出する
pitfall_manager.py は corrections.jsonl から「スキップ/バイパス」パターンを検出し、合理化防止テーブルの候補を生成 MUST する。

#### Scenario: スキップパターンが corrections に存在する場合
- **WHEN** corrections.jsonl に RATIONALIZATION_MIN_CORRECTIONS (3) 件以上のスキップ関連修正がある
- **THEN** スキップ理由ごとにグルーピングし、各理由に対してテレメトリデータを付与した合理化防止テーブルを dict のリストとして生成する。各 dict のキー: `excuse` (str: スキップの言い訳文), `outcome_error_rate` (float: スキップ後エラー率, テレメトリ不足時は None), `sample_count` (int: 該当 corrections 数), `telemetry_source` (str: "usage+errors" | "corrections_only")

#### Scenario: corrections が不十分な場合
- **WHEN** corrections.jsonl のスキップ関連修正が RATIONALIZATION_MIN_CORRECTIONS 未満
- **THEN** 合理化防止テーブル生成をスキップし、data_insufficient フラグを返す

### Requirement: テレメトリと突合して定量的裏付けを付与する
生成された合理化防止テーブルの各エントリは、usage.jsonl / errors.jsonl から裏付けデータを MUST 取得する。

#### Scenario: スキップ後にエラーが発生していた場合
- **WHEN** 「テストなしで進めた」スキップの後 RATIONALIZATION_OUTCOME_WINDOW_DAYS 以内にエラーが記録されている
- **THEN** テーブルに「スキップ後エラー率: N%」を付与する

#### Scenario: テレメトリデータが不足している場合
- **WHEN** 対象期間のテレメトリデータが不十分
- **THEN** テーブルは corrections ベースのみで生成し、テレメトリ列は "N/A" とする

### Requirement: evolve パイプラインに統合する
合理化防止テーブル生成は evolve の Housekeeping フェーズで pitfall_hygiene() と共に MUST 実行される。

#### Scenario: evolve 実行時に合理化テーブルが更新される
- **WHEN** evolve が Housekeeping フェーズに到達し、corrections データが十分
- **THEN** 合理化防止テーブルを生成/更新し、evolve レポートの Pitfall セクションに含める

### Requirement: 既存の pitfall_manager と整合する
合理化防止テーブルの候補は pitfall_manager の既存ライフサイクル（Candidate→New→Active→Graduated→Pruned）と MUST 整合する。

#### Scenario: 既存 pitfall と合理化パターンが重複する場合
- **WHEN** 合理化パターンが既存 pitfall と Jaccard 類似度 > JACCARD_THRESHOLD で一致
- **THEN** 既存 pitfall に合理化テーブルデータ（テレメトリ裏付け）をエンリッチし、新規 pitfall は作成しない
