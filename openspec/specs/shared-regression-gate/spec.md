## ADDED Requirements

### Requirement: 共通 regression gate ライブラリ
`scripts/lib/regression_gate.py` を新設し、ゲートチェックロジックを一元管理しなければならない（MUST）。optimize.py および rl-loop から参照される。

#### Scenario: check_gates が全チェックを実行
- **WHEN** `check_gates(candidate="...", original="---\nname: test\n---\ncontent", max_lines=500, pitfall_patterns_path="references/pitfalls.md")` を呼び出す
- **THEN** 空コンテンツチェック、行数制限チェック、禁止パターンチェック、frontmatter 保持チェック、pitfall パターンチェックを順に実行し、`GateResult` を返す

#### Scenario: 空コンテンツ
- **WHEN** `check_gates(candidate="", original=None, max_lines=500)` を呼び出す
- **THEN** `GateResult(passed=False, reason="empty_content")` を返す

#### Scenario: 行数制限超過
- **WHEN** 候補が 501 行で `max_lines=500` の場合
- **THEN** `GateResult(passed=False, reason="line_limit_exceeded")` を返す

#### Scenario: 禁止パターン検出
- **WHEN** 候補に `TODO` が含まれる
- **THEN** `GateResult(passed=False, reason="forbidden_pattern_TODO")` を返す

#### Scenario: frontmatter 消失
- **WHEN** original が `---` で始まり candidate が `---` で始まらない
- **THEN** `GateResult(passed=False, reason="frontmatter_lost")` を返す

#### Scenario: pitfall パターン検出
- **WHEN** `pitfall_patterns_path` が指定され、候補が `references/pitfalls.md` に記載されたパターンに一致する
- **THEN** `GateResult(passed=False, reason="pitfall_pattern({pattern})")` を返す

#### Scenario: 全ゲート通過
- **WHEN** 空でなく、行数制限内で、禁止パターンなく、frontmatter が保持されており、pitfall パターンに一致しない
- **THEN** `GateResult(passed=True, reason=None)` を返す

### Requirement: pitfall パターンチェック
`references/pitfalls.md` からゲートパターンをロードし、候補テキストに対して照合しなければならない（MUST）。`pitfall_patterns_path` が `None` の場合はスキップする。

#### Scenario: pitfall パターンファイルが存在しない
- **WHEN** `pitfall_patterns_path` に指定されたファイルが存在しない
- **THEN** pitfall チェックをスキップし、他のゲートチェックを継続する

### Requirement: GateResult データクラス
`GateResult` は `passed: bool`, `reason: str | None` の2フィールドを持つ dataclass でなければならない（MUST）。スコアリングは呼び出し側（optimize.py 等）の責務であり、`GateResult` には含めない。

#### Scenario: GateResult の構造
- **WHEN** `GateResult` をインスタンス化する
- **THEN** `passed`, `reason` の2フィールドにアクセスできる

### Requirement: check_gates のインターフェース
`check_gates()` は以下のシグネチャでなければならない（MUST）:
`check_gates(candidate: str, original: str | None = None, max_lines: int, pitfall_patterns_path: str | None = None) -> GateResult`
`max_lines` はデフォルト値を持たない必須パラメータである。呼び出し側が `line_limit.py` の `MAX_SKILL_LINES`(500) / `MAX_RULE_LINES`(3) を参照し明示的に渡す。

#### Scenario: max_lines が明示的に渡される
- **WHEN** optimize.py がスキルのパッチを検証する
- **THEN** `check_gates(candidate=patch, original=original, max_lines=MAX_SKILL_LINES)` のように明示的に渡す

### Requirement: optimize.py は共通 gate を使用する
optimize.py は `scripts/lib/regression_gate.py` から `check_gates` を import し、ローカルにゲートロジックを持ってはならない（MUST NOT）。gate 不合格時に `score=0.0` を設定するのは optimize.py の責務である。

#### Scenario: optimize.py のゲート呼び出し
- **WHEN** optimize.py がパッチ候補を評価する
- **THEN** `check_gates()` を呼び出してゲート判定を行い、不合格時は `score=0.0` を設定する

### Requirement: rl-loop のゲート利用方針
rl-loop-orchestrator は optimize 経由で gate 済みのパッチを受け取るため、full gate の再実行は不要である。rl-loop 独自の `check_line_limit()` による行数チェックは維持する（MUST）。rl-loop が直接パッチを生成する場合は `check_gates()` を使用すべきである（SHOULD）。

#### Scenario: rl-loop が optimize 経由でパッチを受け取る
- **WHEN** rl-loop が optimize の出力パッチを使用する
- **THEN** full gate は再実行せず、`check_line_limit()` による行数チェックのみ実行する

#### Scenario: rl-loop が直接パッチを生成する
- **WHEN** rl-loop が optimize を経由せず独自にパッチを生成する
- **THEN** `check_gates()` を使用してゲート判定を行う
