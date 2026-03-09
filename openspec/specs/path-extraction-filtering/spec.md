## ADDED Requirements

### Requirement: 拡張子なしの2セグメントパスは既知ディレクトリプレフィックスで検証する

`_extract_paths_outside_codeblocks()` がセグメントが正確に2つの相対パス候補（例: `foo/bar`）を検出し、どちらのセグメントにもファイル拡張子（`.` の後に英数字）がない場合、最初のセグメントが既知のプロジェクトディレクトリプレフィックスにマッチする場合のみパスを受け入れる（SHALL）。既知プレフィックスには最低限 `skills`, `scripts`, `hooks`, `.claude`, `openspec`, `docs` を含む（SHALL）。

#### Scenario: 既知プレフィックスで拡張子なしのパスは受け入れられる
- **WHEN** テキストがコードブロック外に `skills/update` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

#### Scenario: 既知プレフィックスで拡張子ありのパスは受け入れられる
- **WHEN** テキストがコードブロック外に `scripts/reflect_utils.py` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

#### Scenario: 未知プレフィックスで拡張子なしのパスは除外される
- **WHEN** テキストがコードブロック外に `usage/errors` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含めない

#### Scenario: 説明的コンテキスト内の未知プレフィックスで拡張子なしのパスは除外される
- **WHEN** テキストが `- discover/audit: telemetry_query...` のような行に `discover/audit` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含めない

### Requirement: ファイル拡張子付きパスはプレフィックスに関係なく常に受け入れる

ファイル拡張子を含むパス候補（`.py`, `.md`, `.json`, `.yaml`, `.yml`, `.ts`, `.js` などのセグメント）は、2セグメントプレフィックスフィルタをバイパスし、正当なファイル参照の除外を避けるため結果に含める（SHALL）。

#### Scenario: 未知プレフィックスでもファイル拡張子ありのパスは受け入れられる
- **WHEN** テキストがコードブロック外に `config/settings.yaml` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

#### Scenario: 深いパスで拡張子ありは受け入れられる
- **WHEN** テキストがコードブロック外に `some/deep/nested/file.py` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

### Requirement: 3セグメント以上のパスは常に受け入れる

セグメントが3つ以上の相対パス候補（例: `skills/audit/scripts/audit.py`, `scripts/rl/tests/`）は、2セグメントフィルタをバイパスし常に含める（SHALL）。マルチレベルパスが説明的略記として使われることはまれなため。

#### Scenario: 拡張子なしの3セグメントパスは受け入れられる
- **WHEN** テキストがコードブロック外に `skills/audit/scripts` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

#### Scenario: 深いパスは受け入れられる
- **WHEN** テキストがコードブロック外に `scripts/rl/tests/test_workflow_analysis.py` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

### Requirement: 絶対パスは新しいフィルタの影響を受けない

絶対パス（`/` で始まる）は既存のフィルタ（長さ、http、スラッシュコマンド）のみを引き続き使用する（SHALL）。新しい2セグメントプレフィックスフィルタは相対パスにのみ適用する（SHALL NOT）。

#### Scenario: 絶対パスはそのまま通過する
- **WHEN** テキストがコードブロック外に `/Users/foo/bar` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める

### Requirement: 既存のコードブロック除外は変更しない

フェンスドコードブロック（``` ... ```）内のパスは、新しいフィルタリングロジックに関係なく、引き続き結果から除外する（SHALL）。

#### Scenario: コードブロック内のパスは除外される
- **WHEN** テキストがフェンスドコードブロック内に `usage/errors` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含めない

### Requirement: 専用ユニットテストで真陽性と偽陽性のケースをカバーする

`_extract_paths_outside_codeblocks()` の専用テストファイルを作成し（SHALL）、以下をカバーするパラメータ化テストケースを含める:
- 真陽性: 既知プレフィックス付きパス、ファイル拡張子付きパス、絶対パス、深いパス
- 偽陽性: `usage/errors`, `discover/audit` など、説明的スラッシュ区切り表現
- エッジケース: コードブロック境界、混合コンテンツ

#### Scenario: すべての指定ケースでテストスイートが通過する
- **WHEN** テストスイートを `python3 -m pytest skills/audit/scripts/tests/test_path_extraction.py -v` で実行する
- **THEN** すべてのテストケースが通過する

### Requirement: 全セグメントが数字のみのパスを除外する

`_extract_paths_outside_codeblocks()` は、パス候補のスラッシュ区切り全セグメントが数字（小数点含む）のみで構成される場合、結果から除外しなければならない（MUST）。

#### Scenario: 数字のみのセグメントで構成されるパスは除外される
- **WHEN** テキストがコードブロック外に `429/500` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含めない

#### Scenario: アルファベットを含むセグメントがあれば除外されない
- **WHEN** テキストがコードブロック外に `scripts/test123.py` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める
