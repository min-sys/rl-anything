## ADDED Requirements

### Requirement: fitness 関数の自動生成
analyze-project.py の出力JSONを入力として、プロジェクト固有の fitness 関数（Python スクリプト）を生成しなければならない（MUST）。生成されたスクリプトは既存の rl-anything インターフェース（stdin でスキル内容 → stdout で 0.0-1.0 スコア）に準拠しなければならない（MUST）。

#### Scenario: 正常な生成フロー
- **WHEN** analyze-project.py の出力JSONが与えられる
- **THEN** `scripts/rl/fitness/{domain}.py` を生成し、生成先パスを stdout に出力しなければならない（MUST）

#### Scenario: 生成先ディレクトリが存在しない場合
- **WHEN** `scripts/rl/fitness/` ディレクトリが存在しない
- **THEN** ディレクトリを自動作成してからファイルを生成しなければならない（MUST）

#### Scenario: 同名ファイルが既に存在する場合
- **WHEN** 同名の fitness 関数ファイルが既に存在する
- **THEN** 既存ファイルを `.backup` にリネームしてから新規生成しなければならない（MUST）

#### Scenario: .backup ファイルが既に存在する場合
- **WHEN** 出力先に `.backup` ファイルが既に存在する
- **THEN** 既存の `.backup` を `.backup.{timestamp}` にリネームしてから新規バックアップを作成しなければならない（MUST）。timestamp は ISO8601 形式（例: `20260301T120000`）とする

#### Scenario: Claude CLI が利用不可の場合
- **WHEN** Claude CLI（`claude` コマンド）が利用不可（コマンドが見つからない、タイムアウト等）の場合
- **THEN** エラーメッセージを stderr に出力し、手動生成用のテンプレートパス（`templates/fitness-template.py`）を提示して exit 1 で終了しなければならない（MUST）

### Requirement: 生成される fitness 関数のインターフェース準拠
生成されるPythonスクリプトは rl-anything の fitness 関数インターフェースに厳密に準拠しなければならない（MUST）。

#### Scenario: stdin/stdout インターフェース
- **WHEN** 生成された fitness 関数に stdin でスキル内容を渡す
- **THEN** 0.0〜1.0 の数値のみを stdout に出力しなければならない（MUST）

#### Scenario: evaluate 関数の存在
- **WHEN** 生成された fitness 関数のソースコードを確認する
- **THEN** `def evaluate(content: str) -> float` と `def main()` が定義されていなければならない（MUST）

#### Scenario: 生成される fitness 関数の実行フロー
- **WHEN** 生成された fitness 関数が実行される
- **THEN** 以下の順序で処理しなければならない（MUST）:
  1. `main()` は `sys.stdin.read()` でスキル内容を受け取る
  2. `evaluate(content)` を呼び出して 0.0-1.0 のスコアを取得する
  3. `print(score)` で標準出力にスコアを出力する
- **NOTE** これは optimize.py の `_run_custom_fitness` が `echo content | python3 fitness.py` で呼び出すインターフェースに準拠する

### Requirement: 生成される fitness 関数の評価基準反映
analyze-project.py の criteria をもとに、ドメイン固有の評価ロジックを生成しなければならない（MUST）。

#### Scenario: criteria の weight が評価に反映される
- **WHEN** criteria に `{"name": "front_matter", "weight": 0.3}` が含まれる
- **THEN** 生成される関数内で front matter チェックが全体の30%の重みで評価されなければならない（MUST）

#### Scenario: keywords がチェック対象になる
- **WHEN** keywords に `["冒険", "探索", "地形"]` が含まれる
- **THEN** 生成される関数内でこれらのキーワードの出現をチェックするロジックを含めなければならない（MUST）

#### Scenario: anti_patterns がチェック対象になる
- **WHEN** anti_patterns に `["TODO", "FIXME"]` が含まれる
- **THEN** 生成される関数内でこれらのアンチパターンの存在を減点するロジックを含めなければならない（MUST）

### Requirement: 運用知見（pitfalls）の評価ロジックへの反映
analyzer JSON の anti_patterns に pitfalls.md 由来のパターンが含まれる場合、生成される fitness 関数はそれらを減点対象として評価ロジックに組み込まなければならない（MUST）。

#### Scenario: pitfalls 由来の anti_patterns が存在する場合
- **WHEN** analyzer JSON の anti_patterns に pitfalls.md から抽出されたパターン（例: `"personality 設定の記述漏れ"`, `"エラーハンドリングなし"`）が含まれる
- **THEN** 生成される evaluate 関数内で、スキル内容にこれらのパターンが該当する場合に減点するロジックを含めなければならない（MUST）

#### Scenario: pitfalls 由来の anti_patterns が存在しない場合
- **WHEN** analyzer JSON の anti_patterns に pitfalls.md 由来のパターンが含まれない
- **THEN** 従来通り CLAUDE.md・rules 由来の anti_patterns のみで評価ロジックを生成しなければならない（MUST）

### Requirement: テンプレートベースの生成
fitness-template.py をスケルトンとして使用し、LLMで穴埋め・カスタマイズして最終的な関数を生成しなければならない（MUST）。

#### Scenario: テンプレートの構造が維持される
- **WHEN** fitness 関数を生成する
- **THEN** fitness-template.py の基本構造（docstring、evaluate関数、main関数）が維持されなければならない（MUST）
