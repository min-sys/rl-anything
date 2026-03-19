Closes: #31

## ADDED Requirements

### Requirement: コンテキスト情報からファイルパスパターンを抽出する

`reflect_utils.py` に `suggest_paths_frontmatter(message: str, project_root: Path) -> Optional[PathsSuggestion]` を提供しなければならない（MUST）。correction テキストからファイルパス参照を抽出し、共通のグロブパターンに変換する。パス抽出には `scripts/lib/path_extractor.py`（`audit.py` の `_extract_paths_outside_codeblocks()` を共有モジュール化したもの）を使用する。

`PATHS_SUGGESTION_MIN_FILES` 定数（デフォルト `1`）を定義し、抽出されたファイル参照数がこの値未満の場合は `None` を返す（MUST）。

#### Scenario: ファイルパスを含む correction からグロブパターンを生成

- **WHEN** correction テキストに `hooks/common.py` と `hooks/save_state.py` のようなパス参照が含まれる
- **THEN** `PathsSuggestion(patterns=["hooks/**/*.py"], confidence=...)` を返す

#### Scenario: 拡張子が共通するファイル参照

- **WHEN** correction テキストに `.yml` 拡張子のファイルが複数参照されている
- **THEN** 共通ディレクトリプレフィックスと拡張子を組み合わせたグロブパターンを返す（例: `patterns=[".github/workflows/**/*.yml"]`）

#### Scenario: パスパターンが特定できない場合

- **WHEN** correction テキストにファイルパス参照が含まれない、または共通パターンが見出せない
- **THEN** `None` を返す

#### Scenario: 単一ファイルの参照

- **WHEN** correction テキストに1つのファイルパスのみ参照されている（`PATHS_SUGGESTION_MIN_FILES` = 1 の場合）
- **THEN** そのファイルのディレクトリと拡張子からグロブパターンを生成して返す

#### Scenario: 混合ディレクトリのファイル参照

- **WHEN** correction テキストに `src/api/handler.py` と `tests/test_handler.py` のように異なるディレクトリのファイルが参照されている
- **THEN** 共通プレフィックスがないため、各ディレクトリ単位のグロブパターン（例: `["src/api/**/*.py", "tests/**/*.py"]`）を返すか、拡張子のみのパターン（例: `["**/*.py"]`）にフォールバックする

#### Scenario: 混合拡張子のファイル参照

- **WHEN** correction テキストに `config.yml` と `deploy.sh` のように異なる拡張子のファイルが参照されている
- **THEN** 共通拡張子がないため、ディレクトリベースのグロブパターンを返すか、パターンが特定できない場合は `None` を返す

#### Scenario: 深いネストのファイル参照

- **WHEN** correction テキストに `src/modules/auth/middleware/jwt.ts` と `src/modules/auth/middleware/session.ts` のような深いネストのパスが参照されている
- **THEN** 最も具体的な共通プレフィックスを使用したグロブパターン（例: `["src/modules/auth/middleware/**/*.ts"]`）を返す

#### Scenario: 拡張子なしファイルの参照

- **WHEN** correction テキストに `Makefile` や `Dockerfile` のような拡張子なしファイルが参照されている
- **THEN** ファイル名を直接パターンに使用するか、パターン化が困難な場合は `None` を返す

### Requirement: `PathsSuggestion` dataclass

`reflect_utils.py` に `PathsSuggestion` dataclass を定義しなければならない（MUST）。

```python
@dataclass
class PathsSuggestion:
    patterns: List[str]  # グロブパターンのリスト
    confidence: float     # 提案の確信度 (0.0 - 1.0)
```

### Requirement: reflect が paths 提案を表示する

reflect が correction をルールファイルに反映する際、`suggest_paths_frontmatter()` の結果が `None` でなければ、ルール反映結果とともに `paths` frontmatter の提案を表示しなければならない（MUST）。

#### Scenario: paths 提案あり

- **WHEN** reflect がルールファイルに correction を反映し、`suggest_paths_frontmatter()` が `PathsSuggestion(patterns=["hooks/**/*.py"], confidence=0.85)` を返した
- **THEN** 反映結果に加えて「`paths: ["hooks/**/*.py"]` の追加を推奨」というメッセージを表示する。CC バージョンによっては `globs:` の方が信頼性が高い場合がある旨の注記を含める

#### Scenario: paths 提案なし

- **WHEN** `suggest_paths_frontmatter()` が `None` を返した
- **THEN** paths 関連のメッセージは表示しない

### Requirement: optimize が最適化後に paths 提案を表示する

optimize がルールファイルを最適化した際、最適化対象の correction コンテキストから `suggest_paths_frontmatter()` を呼び出し、提案があれば表示しなければならない（MUST）。optimize では `corrections` リストの各 `message` フィールドを入力とする。

#### Scenario: 最適化後の paths 提案

- **WHEN** optimize がルールファイルを最適化し、correction コンテキストの `message` フィールドから paths パターンが検出された
- **THEN** 最適化結果に paths frontmatter の提案を付加して表示する

### Requirement: remediation がルール生成時に paths 提案を含める

remediation の `generate_proposals()` がルール候補の issue を処理する際、issue の detail にファイルパスパターン情報が含まれていれば `paths_suggestion` フィールドを proposal に付加しなければならない（MUST）。

#### Scenario: ルール候補に paths 提案を付加

- **WHEN** remediation が `rule_candidate` issue を処理し、detail にパスパターン情報がある
- **THEN** proposal に `paths_suggestion` フィールドを含め、提案する frontmatter の `paths` 値を格納する

### Requirement: `detect_dead_globs()` の `paths` / `globs` 両キー対応

`prune.py` の `detect_dead_globs()` を `parse_frontmatter()` ベースにリファクタし、`paths` キーと `globs` キーの両方を処理しなければならない（MUST）。

#### Scenario: `paths` キーのみの frontmatter

- **WHEN** ルールファイルに `paths: ["src/**/*.py"]` がある
- **THEN** `detect_dead_globs()` が `paths` キーの値を読み取り、dead glob 判定を行う

#### Scenario: `globs` キーのみの frontmatter

- **WHEN** ルールファイルに `globs: ["src/**/*.py"]` がある
- **THEN** `detect_dead_globs()` が `globs` キーの値を読み取り、dead glob 判定を行う

#### Scenario: 両キーが存在する frontmatter

- **WHEN** ルールファイルに `paths` と `globs` の両キーがある
- **THEN** 両方のキーの値を統合して dead glob 判定を行う
