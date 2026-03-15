## ADDED Requirements

### Requirement: Stale memory auto-deletion via FIX_DISPATCH
`stale_memory` issue に対する fix 関数 `fix_stale_memory()` を FIX_DISPATCH に登録する（MUST）。fix 関数は MEMORY.md から該当エントリ行（リンク行）を削除する（SHALL）。参照先の個別メモリファイルが存在しない場合、MEMORY.md のポインタ行のみ削除する（SHALL）。

#### Scenario: Stale memory entry removed
- **WHEN** MEMORY.md に `[feedback_old](feedback_old.md)` があるが `feedback_old.md` が存在しない
- **THEN** `fix_stale_memory()` が MEMORY.md から該当行を削除し、verify_fix で resolved=true を返す

#### Scenario: Stale memory with existing file but dead reference inside
- **WHEN** MEMORY.md エントリの参照先ファイルは存在するが、ファイル内の参照パスが無効
- **THEN** MEMORY.md のポインタ行は維持し、参照先ファイル内の無効参照を proposable として提案する

#### Scenario: Multiple stale entries in single run
- **WHEN** MEMORY.md に 3 件の stale エントリが検出された
- **THEN** 3 件すべてが auto_fixable として一括承認対象になる

### Requirement: MEMORY.md near_limit detection and proposal
MEMORY.md の行数が既存定数 `NEAR_LIMIT_RATIO`（0.8）× MEMORY_LIMIT（200行）= 160行を超えた場合、`near_limit` issue を生成する（MUST）。新たな閾値定数は作成せず、audit.py L59 の既存 `NEAR_LIMIT_RATIO` を再利用する（SHALL）。issue は proposable に分類され、最も大きいセクションの個別ファイル分離を提案する（SHALL）。

#### Scenario: MEMORY.md at 165 lines
- **WHEN** MEMORY.md が 165 行で NEAR_LIMIT_RATIO 閾値（160行）を超えている
- **THEN** `near_limit` issue が生成され、proposable に分類される。提案内容に最大セクション名と推定削減行数を含む

#### Scenario: MEMORY.md under threshold
- **WHEN** MEMORY.md が 150 行で NEAR_LIMIT_RATIO 閾値（160行）未満
- **THEN** `near_limit` issue は生成されない
