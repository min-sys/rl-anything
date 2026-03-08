## adaptive-granularity

ファイルサイズに応じたセクション分割レベルの自動調整と小セクション統合。

### インターフェース

```python
def determine_split_level(file_lines: int) -> Literal["none", "h2_h3", "h2_only"]:
    """ファイル行数に基づき分割レベルを決定"""

def split_sections(content: str, level: str) -> list[Section]:
    """Markdown を指定レベルの見出しでセクション分割"""

def merge_small_sections(sections: list[Section], min_lines: int = 10) -> list[Section]:
    """min_lines 未満のセクションを直前のセクションに統合"""
```

### Section データクラス

```python
@dataclass
class Section:
    id: str              # "h2-3" 等の一意識別子
    heading: str         # 見出しテキスト（"## Troubleshooting" 等）
    lines: list[str]     # セクション本文（見出し行含む）
    parent_id: str | None  # 親セクションID（h3 の場合は所属 h2）
    depth: int           # 見出し深度（2 = ##, 3 = ###）
```

## ADDED Requirements

### Requirement: 分割レベル判定

`determine_split_level(file_lines)` は以下のルールに従わなければならない（MUST）:

| ファイル行数 | 分割レベル | 理由 |
|-------------|-----------|------|
| < 60 | `none` | 一括最適化で十分。TextGrad 相当 |
| 60-200 | `h2_h3` | `##` と `###` で分割。現行 MPO と同一 |
| > 200 | `h2_only` | `##` のみで分割。セクション数を抑制 |

- MUST: 境界値（60行、200行）は上記テーブル通りに判定する
- MUST: 戻り値は `"none"` / `"h2_h3"` / `"h2_only"` のいずれかのみ
- SHOULD: 閾値はモジュール先頭の定数として定義し、将来的に設定ファイルで上書き可能にする

#### Scenario: 短ファイル（50行）は一括処理

```
Given: 50行の Markdown ファイル
When: determine_split_level(50) を呼び出す
Then: "none" が返る
And: split_sections(content, "none") はファイル全体を1セクションとして返す
```

#### Scenario: 中ファイル（150行）は h2+h3 で分割

```
Given: 150行の Markdown ファイル（## が3個、### が5個）
When: determine_split_level(150) を呼び出す
Then: "h2_h3" が返る
And: split_sections(content, "h2_h3") は8セクションを返す
```

#### Scenario: 長ファイル（500行）は h2 のみで分割

```
Given: 500行の Markdown ファイル（## が10個、### が20個）
When: determine_split_level(500) を呼び出す
Then: "h2_only" が返る
And: split_sections(content, "h2_only") は10セクションを返す（### は無視）
```

### Requirement: セクション分割

- MUST: `split_sections()` は指定された `level` に応じた見出しのみで分割する
- MUST: `level="none"` の場合、ファイル全体を単一の `Section` として返す
- MUST: 各 `Section` の `id` はファイル内で一意でなければならない
- SHOULD: `id` は `"{depth}-{index}"` 形式（例: `"h2-3"`）とする

#### Scenario: level=none でファイル全体を1セクションとして返す

```
Given: 40行の Markdown ファイル
When: split_sections(content, "none") を呼び出す
Then: 1つの Section が返る
And: その Section の lines はファイル全体の行を含む
```

### Requirement: 小セクション統合ルール

- MUST: 先頭セクション（ファイル冒頭〜最初の見出しまで）は統合対象外
- MUST: `min_lines` 未満のセクションは **直前のセクション** に統合する
- MUST: 統合時、元の見出し行は保持する（セクション本文に含める）
- SHOULD: 連続する小セクションは順次統合（A + B + C が全て小なら A に B, C を統合）
- MAY: `min_lines` のデフォルト値（10）を設定ファイルで変更可能にする

#### Scenario: 8行セクションは前セクションに統合

```
Given: split_sections() の結果に8行のセクション B がある（min_lines=10）
When: merge_small_sections(sections, min_lines=10) を呼び出す
Then: セクション B は直前のセクション A に統合される
And: セクション B の見出し行は A の本文に含まれる
```

### Requirement: 失敗時挙動

- MUST: 見出しが1つもないファイル → `determine_split_level` の結果に関わらず `"none"`（一括）にフォールバック
- MUST: `split_sections()` で不正な `level` 値 → `ValueError` を送出
- MUST: 統合後にセクション数が0になる場合 → 統合前の状態を返す

#### Scenario: 見出しのないファイルはフォールバック

```
Given: 300行の Markdown ファイルだが見出し（##）が1つもない
When: determine_split_level(300) → "h2_only" で split_sections() を呼び出す
Then: ファイル全体を1セクションとして返す（"none" と同等の挙動）
```

### 期待効果

atlas-browser（1,180行、88セクション）での推定:
- `h2_only` 分割: 88 → ~45 セクション
- 小セクション統合後: ~45 → ~35 セクション
- **削減率: 約60%**

### 参考

- GAAPO（Frontiers 2025）: 動的戦略配分、リアルタイム収束パターンに基づく粒度切替
- MoG（Mix-of-Granularity）: 情報密度に応じた動的チャンク粒度選択
