## ADDED Requirements

### Requirement: 全セグメントが数字のみのパスを除外する

`_extract_paths_outside_codeblocks()` は、パス候補のスラッシュ区切り全セグメントが数字（小数点含む）のみで構成される場合、結果から除外しなければならない（MUST）。

#### Scenario: 数字のみのセグメントで構成されるパスは除外される
- **WHEN** テキストがコードブロック外に `429/500` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含めない

#### Scenario: アルファベットを含むセグメントがあれば除外されない
- **WHEN** テキストがコードブロック外に `scripts/test123.py` を含む
- **THEN** `_extract_paths_outside_codeblocks()` は結果に含める
