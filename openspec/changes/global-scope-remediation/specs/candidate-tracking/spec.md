## ADDED Requirements

### Requirement: カタログ未登録の個人 global 設定を検出する
evolve の Diagnose ステージで `~/.claude/rules/` と `~/.claude/settings.json` hooks を走査し、`recommended-globals.json` に未登録の設定を `global_candidates` として検出する。プロジェクト固有キーワード（AWS ARN, git org 名, サービス URL 等）を含むルールは候補から除外する。

#### Scenario: カタログ未登録のルールが検出される
- **WHEN** `~/.claude/rules/my-custom-rule.md` が存在し、`recommended-globals.json` に `my-custom-rule` が含まれない
- **AND** ルール内容にプロジェクト固有キーワードを含まない
- **THEN** `my-custom-rule` が `global_candidates` に追加される

#### Scenario: プロジェクト固有ルールは除外される
- **WHEN** `~/.claude/rules/aws-auth.md` の内容に AWS ARN パターンが含まれる
- **THEN** `aws-auth` は `global_candidates` に含まれない

#### Scenario: カタログ登録済みのルールは検出されない
- **WHEN** `~/.claude/rules/avoid-bash-builtin.md` が存在し、`recommended-globals.json` に `avoid-bash-builtin` が登録済み
- **THEN** `avoid-bash-builtin` は `global_candidates` に含まれない

### Requirement: 候補の効果をテレメトリで測定する
検出された `global_candidates` について、corrections.jsonl や usage.jsonl から関連テレメトリ（候補ルールが引用された回数、hook の block 回数）を集計し、効果スコアを算出する。

#### Scenario: correction で参照されたルールの効果が高く評価される
- **WHEN** `my-custom-rule` が corrections.jsonl 内で `PROVEN_THRESHOLD`（デフォルト: 3）回以上参照されている
- **THEN** 効果スコアが高（"proven"）と判定される

#### Scenario: テレメトリが不十分な候補は "testing" 状態
- **WHEN** 候補ルールに関連するテレメトリが `TESTING_MINIMUM`（デフォルト: 2）件未満
- **THEN** 候補の状態は "testing"（まだ効果未確認）と記録される

### Requirement: 効果が確認された候補のカタログ昇格を提案する
evolve レポートで `global_candidates` の中から効果が "proven" のものについて、`recommended-globals.json` への追加を提案する。提案は diff 形式でカタログエントリ案を表示する。

#### Scenario: proven 候補の昇格提案が evolve レポートに表示される
- **WHEN** `my-custom-rule` の効果スコアが "proven" である
- **THEN** evolve レポートに「カタログ昇格候補」セクションが表示される
- **AND** `recommended-globals.json` に追加するエントリ案が表示される

#### Scenario: testing 状態の候補は昇格提案されない
- **WHEN** 候補ルールの状態が "testing"
- **THEN** evolve レポートには追跡情報のみ表示され、昇格提案は行われない

### Requirement: 候補状態を evolve-state.json に永続化する
検出された `global_candidates` の情報（名前、種別、初回検出日、状態、効果スコア）を `evolve-state.json` に保存し、セッション間で追跡を継続する。

#### Scenario: 初回検出時に候補が記録される
- **WHEN** `my-custom-rule` が初めて `global_candidates` として検出される
- **THEN** `evolve-state.json` の `global_candidates` に初回検出日と "testing" 状態で記録される

#### Scenario: 既存候補は状態のみ更新される
- **WHEN** `my-custom-rule` が既に `global_candidates` に記録済み
- **THEN** 初回検出日は変更されず、効果スコアと状態のみ更新される
