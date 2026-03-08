## ADDED Requirements

### Requirement: 陳腐化メモリエントリを検出する
`diagnose_memory()` は、MEMORY.md 内で言及されているファイルパスやモジュール名がプロジェクト内に存在しない場合、`stale_memory` issue として検出しなければならない（MUST）。既存の audit `stale_ref` でカバーされないパターン（モジュール名のみの言及、バージョン情報の陳腐化、「～は削除済み」「～に移行」等のセマンティックな記述）を対象とする。

#### Scenario: メモリ内の参照先が存在する
- **WHEN** MEMORY.md 内で `scripts/lib/telemetry_query.py` が言及されており、そのファイルが存在する
- **THEN** 当該エントリは `stale_memory` として検出されない

#### Scenario: メモリ内の参照先が存在しない（stale_ref 未カバーパターン）
- **WHEN** MEMORY.md 内で `obsolete_module` というモジュール名のみが言及されているが、対応するファイルが存在しない
- **THEN** `{"type": "stale_memory", "file": "...MEMORY.md", "detail": {"path": "obsolete_module", "line": 15, "context": "..."}, "source": "diagnose_memory"}` が出力される

#### Scenario: 既存 stale_ref でカバー済みのパスは重複検出しない
- **WHEN** MEMORY.md 内のファイルパス参照が既に audit の `stale_ref` として検出されている
- **THEN** `stale_memory` としては検出しない（重複排除）

### Requirement: 重複メモリセクションを検出する
`diagnose_memory()` は、MEMORY.md 内の見出しレベルのセクションで意味的に重複しているものを `memory_duplicate` issue として検出しなければならない（MUST）。検出はセクション名のトークン重複率（Jaccard 係数）で判定する。

#### Scenario: セクション名が類似していない
- **WHEN** MEMORY.md 内に「ユーザー指示」と「リポジトリ情報」のセクションがある
- **THEN** `memory_duplicate` として検出されない

#### Scenario: セクション名が類似している
- **WHEN** MEMORY.md 内に「OpenSpec Changes」と「OpenSpec 変更履歴」のセクションがある
- **THEN** `{"type": "memory_duplicate", "file": "...MEMORY.md", "detail": {"sections": ["OpenSpec Changes", "OpenSpec 変更履歴"], "similarity": 0.7}, "source": "diagnose_memory"}` が出力される

### Requirement: 閾値は定数から参照する
`diagnose_memory()` が使用する閾値（Jaccard 係数の閾値等）はモジュールレベル定数または coherence.py の THRESHOLDS dict から取得しなければならない（MUST）。

### Requirement: 診断結果は統一フォーマットで出力する
`diagnose_memory()` は `List[Dict]` を返し、各要素は `{"type": str, "file": str, "detail": dict, "source": str}` フォーマットでなければならない（MUST）。

#### Scenario: 問題がない場合
- **WHEN** すべてのメモリファイルが正常
- **THEN** 空のリストを返す
