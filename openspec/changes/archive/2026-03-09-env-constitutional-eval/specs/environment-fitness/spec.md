## MODIFIED Requirements

### Requirement: Environment fitness blending
`compute_environment_fitness()` SHALL blend Coherence Score, Telemetry Score, and Constitutional Score into a single environment fitness.

- Constitutional + テレメトリ充足時: coherence * 0.25 + telemetry * 0.45 + constitutional * 0.30
- テレメトリ充足・Constitutional 不可時: coherence * 0.4 + telemetry * 0.6（既存比率維持）
- テレメトリ不足・Constitutional 可時: coherence * 0.45 + constitutional * 0.55
- テレメトリ不足・Constitutional 不可時: coherence のみ（1.0 weight）
- 返却 dict に sources リスト（使用したスコアソース名）を含める

#### Scenario: Three sources available
- **WHEN** Coherence Score = 0.8, Telemetry Score = 0.7（data_sufficiency=True）, Constitutional Score = 0.85
- **THEN** overall = 0.8 * 0.25 + 0.7 * 0.45 + 0.85 * 0.30 = 0.77, sources = ["coherence", "telemetry", "constitutional"]

#### Scenario: Telemetry data insufficient, Constitutional available
- **WHEN** Coherence Score = 0.8, Telemetry data_sufficiency = False, Constitutional Score = 0.9
- **THEN** overall = 0.8 * 0.45 + 0.9 * 0.55 = 0.855, sources = ["coherence", "constitutional"]

#### Scenario: Constitutional unavailable (fallback to existing 2-layer)
- **WHEN** Coherence Score = 0.8, Telemetry Score = 0.7（data_sufficiency=True）, Constitutional Score = None
- **THEN** overall = 0.8 * 0.4 + 0.7 * 0.6 = 0.74, sources = ["coherence", "telemetry"]

#### Scenario: Only coherence available
- **WHEN** Coherence Score = 0.8, Telemetry data_sufficiency = False, Constitutional Score = None
- **THEN** overall = 0.8, sources = ["coherence"]

#### Scenario: Coverage gate で Constitutional = None
- **WHEN** Coherence Score の Coverage 軸が 0.3 で Coverage ゲートにより Constitutional eval がスキップされた
- **THEN** Constitutional Score = None, `skip_reason: "low_coverage"` が environment fitness 結果に含まれ、2層ブレンドまたは Coherence のみにフォールバック
