## ADDED Requirements

### Requirement: fitness 関数の自動生成
analyze-project.py の出力JSONを入力として、プロジェクト固有の fitness 関数（Python スクリプト）を生成する。生成されたスクリプトは既存の rl-anything インターフェース（stdin でスキル内容 → stdout で 0.0-1.0 スコア）に準拠する。

#### Scenario: 正常な生成フロー
- **WHEN** analyze-project.py の出力JSONが与えられる
- **THEN** `scripts/rl/fitness/{domain}.py` を生成し、生成先パスを stdout に出力する

#### Scenario: 生成先ディレクトリが存在しない場合
- **WHEN** `scripts/rl/fitness/` ディレクトリが存在しない
- **THEN** ディレクトリを自動作成してからファイルを生成する

#### Scenario: 同名ファイルが既に存在する場合
- **WHEN** 同名の fitness 関数ファイルが既に存在する
- **THEN** 既存ファイルを `.backup` にリネームしてから新規生成する

### Requirement: 生成される fitness 関数のインターフェース準拠
生成されるPythonスクリプトは rl-anything の fitness 関数インターフェースに厳密に準拠する。

#### Scenario: stdin/stdout インターフェース
- **WHEN** 生成された fitness 関数に stdin でスキル内容を渡す
- **THEN** 0.0〜1.0 の数値のみを stdout に出力する

#### Scenario: evaluate 関数の存在
- **WHEN** 生成された fitness 関数のソースコードを確認する
- **THEN** `def evaluate(content: str) -> float` と `def main()` が定義されている

### Requirement: 生成される fitness 関数の評価基準反映
analyze-project.py の criteria をもとに、ドメイン固有の評価ロジックを生成する。

#### Scenario: criteria の weight が評価に反映される
- **WHEN** criteria に `{"name": "front_matter", "weight": 0.3}` が含まれる
- **THEN** 生成される関数内で front matter チェックが全体の30%の重みで評価される

#### Scenario: keywords がチェック対象になる
- **WHEN** keywords に `["冒険", "探索", "地形"]` が含まれる
- **THEN** 生成される関数内でこれらのキーワードの出現をチェックするロジックが含まれる

#### Scenario: anti_patterns がチェック対象になる
- **WHEN** anti_patterns に `["TODO", "FIXME"]` が含まれる
- **THEN** 生成される関数内でこれらのアンチパターンの存在を減点するロジックが含まれる

### Requirement: テンプレートベースの生成
fitness-template.py をスケルトンとして使用し、LLMで穴埋め・カスタマイズして最終的な関数を生成する。

#### Scenario: テンプレートの構造が維持される
- **WHEN** fitness 関数を生成する
- **THEN** fitness-template.py の基本構造（docstring、evaluate関数、main関数）が維持される
