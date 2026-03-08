## ADDED Requirements

### Requirement: Coherence Coverage gate
`compute_constitutional_score()` は評価前に Coherence Score の Coverage 軸を確認しなければならない（MUST）。`coverage < THRESHOLDS["min_coverage_for_eval"]`（デフォルト 0.5）の場合、Constitutional eval をスキップし `None` を返さなければならない（MUST）。返却 dict に `skip_reason: "low_coverage"` と `coverage_value` を含めなければならない（MUST）。

#### Scenario: Coverage 不足で Constitutional eval スキップ
- **WHEN** Coherence Score の Coverage 軸が 0.3 である
- **THEN** `compute_constitutional_score()` は `None` を返し、`skip_reason: "low_coverage"`, `coverage_value: 0.3` が含まれる

#### Scenario: Coverage 充足で Constitutional eval 実行
- **WHEN** Coherence Score の Coverage 軸が 0.7 である
- **THEN** Constitutional eval が通常通り実行される

### Requirement: Constitutional Score computation
`constitutional.py` の `compute_constitutional_score()` は原則リストと全レイヤー（CLAUDE.md/Rules/Skills/Memory）を入力として、各原則×各レイヤーの遵守度を LLM Judge で評価し、Constitutional Score（0.0〜1.0）を算出しなければならない（MUST）。

#### Scenario: 全原則が遵守されている場合
- **WHEN** 5 つの原則すべてが全レイヤーで遵守されていると LLM が判定する
- **THEN** Constitutional Score が 0.9 以上になる

#### Scenario: 一部原則が違反している場合
- **WHEN** 5 つの原則のうち 2 つが Skills レイヤーで違反していると LLM が判定する
- **THEN** Constitutional Score が違反の程度に応じて低下し、violations リストに違反詳細が含まれる

### Requirement: Layer-batched evaluation
各レイヤーの評価は1回の LLM 呼び出し（`claude -p --model haiku`）で全原則をバッチ評価しなければならない（MUST）。4レイヤー = 4回の LLM 呼び出しで完了する。1回の LLM 呼び出しで複数原則を一括評価してはならない（SHOULD NOT）— 将来の `--detailed` オプションで原則×レイヤー個別評価を有効化可能とする。各評価は原則ごとの `score`（0.0〜1.0）、`rationale`（判定理由）、`violations`（違反箇所リスト）を返さなければならない（MUST）。

#### Scenario: レイヤー単位バッチ評価
- **WHEN** 5 つの原則と 4 レイヤーが存在する
- **THEN** 4 回の LLM 呼び出しが行われ、各呼び出しでレイヤー内の全原則に対する score, rationale, violations が含まれる

#### Scenario: 特定レイヤーのみ違反がある場合
- **WHEN** 原則「LLMコール最小化」に対して Skills の 1 つで `claude -p` を使用している
- **THEN** Skills レイヤーの評価結果で該当原則の violations に Skill 名とファイルパスが含まれ、score が低下する

### Requirement: LLM response validation
LLM レスポンスの JSON パースに失敗した場合、1回リトライしなければならない（MUST）（`optimize.py` の `_extract_markdown()` パターン踏襲）。スコア値が [0.0, 1.0] 範囲外の場合、clamp して範囲内に収めなければならない（MUST）。LLM 呼び出しがタイムアウトした場合、該当レイヤーをスキップしなければならない（MUST）。

#### Scenario: JSON パース失敗時のリトライ
- **WHEN** LLM レスポンスが不正な JSON を返す
- **THEN** 1回リトライし、再度失敗した場合は該当レイヤーをスキップする

#### Scenario: スコア範囲外の clamp
- **WHEN** LLM が score: 1.5 を返す
- **THEN** score が 1.0 に clamp される

#### Scenario: タイムアウト時のスキップ
- **WHEN** LLM 呼び出しが 30 秒以内に応答しない
- **THEN** 該当レイヤーの評価がスキップされ、残りのレイヤーで Constitutional Score が算出される

### Requirement: Score aggregation method
Constitutional Score は以下の集計方法で算出しなければならない（MUST）:
- `per_principle[i] = mean(layer_scores[i])` — 原則 i の全レイヤー平均
- `per_layer[j] = mean(principle_scores[j])` — レイヤー j の全原則平均
- `overall = mean(per_principle)` — 全原則の平均（等重み）

返却 dict に `per_principle`（原則別スコア）と `per_layer`（レイヤー別スコア）の両方のブレークダウンを含めなければならない（MUST）。

#### Scenario: 原則別・レイヤー別のブレークダウン
- **WHEN** 3 原則 × 4 レイヤーの評価が完了する
- **THEN** 返却 dict に `per_principle` (3件) と `per_layer` (4件) のスコアが含まれ、`overall` が `per_principle` の平均と一致する

#### Scenario: 一部レイヤーがスキップされた場合の集計
- **WHEN** 3 原則 × 4 レイヤーのうち 1 レイヤーがスキップされた
- **THEN** `per_principle[i]` は成功した 3 レイヤーの平均で算出され、`per_layer` にはスキップされたレイヤーが含まれない

### Requirement: Evaluation result caching
Constitutional eval の結果を各レイヤーファイルのコンテンツハッシュ（SHA-256）と紐づけて `.claude/constitutional_cache.json` にキャッシュしなければならない（MUST）。レイヤーのファイルが未変更の場合、LLM を呼ばずキャッシュを返却しなければならない（MUST）。`--refresh` フラグでキャッシュを無視しなければならない（MUST）。

#### Scenario: ファイル未変更時のキャッシュ返却
- **WHEN** 前回評価後にレイヤーファイルが一切変更されていない
- **THEN** LLM を呼ばず、キャッシュされた Constitutional Score が返される

#### Scenario: 一部レイヤーのみ変更
- **WHEN** Rules レイヤーのみ変更され、Skills/CLAUDE.md/Memory は未変更
- **THEN** Rules レイヤーのみ LLM 再評価し、他レイヤーはキャッシュを使用する

### Requirement: Graceful degradation
LLM 呼び出しが失敗したレイヤーはスキップし、成功したレイヤーのみでスコアを算出しなければならない（MUST）。全レイヤーの評価が失敗した場合は `None` を返さなければならない（MUST）。

#### Scenario: 一部 LLM 呼び出しが失敗
- **WHEN** 4 レイヤー中 1 レイヤーの LLM 評価が失敗する
- **THEN** 残り 3 レイヤーのスコアで Constitutional Score が算出され、`evaluated_layers: 3, total_layers: 4` が返却に含まれる

#### Scenario: 全 LLM 呼び出しが失敗
- **WHEN** 全レイヤーの LLM 評価が失敗する
- **THEN** `None` が返される

### Requirement: Cost tracking
各 LLM 呼び出しの推定コストを集計し、返却 dict に `estimated_cost_usd` として含めなければならない（MUST）。haiku モデルの入出力トークン数から推定する。

#### Scenario: コスト推定の表示
- **WHEN** 4 レイヤーの評価が完了する
- **THEN** 返却 dict に `estimated_cost_usd` が含まれ、`llm_calls_count: 4` も含まれる
