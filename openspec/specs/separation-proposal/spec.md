## ADDED Requirements

### Requirement: suggest_separation 関数

`scripts/lib/line_limit.py` に `suggest_separation(target_path: str, content: str) -> Optional[SeparationProposal]` を追加する。rule ファイルが行数制限を超過している場合に、分離先パスと要約テンプレートを含む `SeparationProposal` を返す。

#### Scenario: グローバル rule が3行超過

- **WHEN** グローバル rule（`~/.claude/rules/foo.md`）が4行以上の content で呼ばれた
- **THEN** `SeparationProposal` を返し、`reference_path` が `~/.claude/rules/references/foo.md`、`summary_template` が要約+参照リンクのテンプレートを含む

#### Scenario: PJ rule が5行超過

- **WHEN** PJ rule（`.claude/rules/bar.md`）が6行以上の content で呼ばれた
- **THEN** `SeparationProposal` を返し、`reference_path` が `.claude/references/bar.md` を含む

#### Scenario: 行数制限内

- **WHEN** rule ファイルが行数制限内の content で呼ばれた
- **THEN** `None` を返す

#### Scenario: skill ファイル

- **WHEN** skill ファイル（`.claude/skills/` 配下）で呼ばれた
- **THEN** `None` を返す（rule のみ対象）

### Requirement: SeparationProposal データクラス

`SeparationProposal` は以下のフィールドを持つ dataclass とする:
- `target_path: str` — 元の rule ファイルパス
- `reference_path: str` — 分離先ファイルパス
- `summary_template: str` — rule に残す要約+参照リンクのテンプレート
- `excess_lines: int` — 超過行数

#### Scenario: フィールドアクセス

- **WHEN** `SeparationProposal` インスタンスを生成した
- **THEN** 全フィールドに型安全にアクセスできる

### Requirement: 分離先パスの衝突回避

`suggest_separation()` は分離先パスが既に存在する場合、サフィックス（`_2`, `_3`, ...）を付与して衝突を回避する。

#### Scenario: references/foo.md が既に存在

- **WHEN** `references/foo.md` が既に存在する状態で `foo.md` rule の分離提案を生成
- **THEN** `reference_path` が `references/foo_2.md` となる
