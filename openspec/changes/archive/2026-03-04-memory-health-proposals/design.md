## Context

rl-anything plugin は MEMORY ファイルの行数超過チェック（audit）と corrections の昇格候補検出（reflect）を持つが、MEMORY 内容の品質分析や更新提案は行わない。MEMORY は使い続けるうちに陳腐化（削除済みパス参照）や肥大化が蓄積する。

既存の基盤:
- `audit.py`: `find_artifacts()` で project-local memory 一覧取得、`check_line_limits()` で行数チェック済み
- `reflect_utils.py`: `read_auto_memory()` で auto-memory 読み取り、`read_all_memory_entries()` で全メモリ層読み取り済み
- `reflect.py`: `detect_duplicates()` で corrections とメモリの重複検出済み
- `scripts/lib/similarity.py`: `tokenize()` でテキスト→トークン集合の変換済み
- `scripts/bloat_control.py`: `BLOAT_THRESHOLDS["memory_md_lines"] = 150` で evolve 向け memory 肥大化警告済み

## Goals / Non-Goals

**Goals:**
- audit レポートに Memory Health セクションを追加し、陳腐化参照・肥大化警告を検出する
- reflect 出力に memory_update_candidates を追加し、corrections と既存 MEMORY の関連を提示する
- LLM コストゼロ（ルールベースのみ）で実装する

**Non-Goals:**
- MEMORY への自動書き込み（提案のみ、書き込みはユーザー/Claude判断）
- LLM ベースの意味的類似度判定（既存の similarity engine は skills/rules 対象であり MEMORY は対象外）
- corrections.jsonl の構造変更

## Decisions

### D1: 陳腐化検出は「ファイルパス参照の存在チェック」に限定

MEMORY 内のファイルパス参照（`/path/to/file` や相対パス `skills/update/` 等）を正規表現で抽出し、ディスク上の存在を確認する。意味的な陳腐化（「npm を使う」→ 実際は bun に移行済み）は検出しない。

**理由**: LLM コストゼロの制約下で確実に検出できるのはファイルパスの存在チェックのみ。意味的な陳腐化は reflect の corrections 経路でカバーされる。

### D2: 肥大化警告は NEAR_LIMIT_RATIO 定数で早期警告

既存の `check_line_limits()` は上限超過のみ報告する。Memory Health セクションでは `NEAR_LIMIT_RATIO = 0.8` 到達時点で "Near Limit" として警告し、トピックファイルへの分離を提案する。

**理由**: 上限超過後に対処するより、事前警告で計画的に分離できる方がユーザー体験が良い。

**bloat_control.py との関係**: `bloat_control.py` は evolve パイプライン向けに `BLOAT_THRESHOLDS["memory_md_lines"] = 150` で別の警告閾値を持つ。audit Memory Health は `/audit` レポート向け。それぞれ異なる用途・タイミングで使用されるため共存する。行数上限自体は `audit.py` の `LIMITS` を Single Source of Truth とする。

### D3: reflect の memory_update_candidates はキーワードマッチベース

corrections の message/extracted_learning と既存 MEMORY エントリ間で、`MIN_KEYWORD_MATCH`（定数、デフォルト 3）語以上の共通キーワード（ストップワード除外）が存在する場合に候補とする。`duplicate_found=True` の correction は除外（既に重複処理済み）。

キーワード抽出には `scripts/lib/similarity.py` の `tokenize()` を再利用する。ストップワードは `reflect.py` の定数 `_MEMORY_STOP_WORDS` で定義する（英語一般語 + 短い技術汎用語）。

**理由**: 部分文字列マッチだけでは一般語でノイズが多い。キーワードベースのマッチングで精度と速度のバランスを取る。`tokenize()` は既に `similarity.py` に実装済みで DRY を維持できる。

### D4: audit の generate_report() に project_dir パラメータ追加

`build_memory_health_section()` がファイル存在チェックに project_dir を必要とするため、`generate_report()` のシグネチャに `project_dir` を追加する。既存の呼び出し元 `run_audit()` は既に `proj` を保持しているため影響は軽微。

### D5: auto-memory ファイルの探索

`audit.py` の `find_artifacts()` は `project_dir/.claude/memory/` のみを探索するが、ユーザーの MEMORY.md は auto-memory パス（`~/.claude/projects/<encoded>/memory/`）に存在する。`build_memory_health_section()` では `reflect_utils.read_auto_memory()` を使って auto-memory ファイルも検査対象とする。

**理由**: ユーザーが最もよく使う MEMORY.md は auto-memory にあり、これを検査しないと Memory Health の価値が大幅に低下する。

## Risks / Trade-offs

- **パス検出の偽陽性** — MEMORY 内のコード例やコマンド例のパスを「陳腐化」と誤検出する可能性がある → コードブロック（``` ``` ）内のパスは除外する
- **キーワードマッチの精度** — 短いキーワードや一般的な技術用語で false positive が出る可能性がある → `MIN_KEYWORD_MATCH` 定数と `_MEMORY_STOP_WORDS` 定数で制御する
- **既存テストへの影響** — `generate_report()` のシグネチャ変更により既存テストが壊れる → `project_dir` を Optional[Path] = None としてデフォルト値を持たせる
- **MEMORY 読み取りエラー** — 権限エラーやエンコーディングエラー → ファイルをスキップし stderr に警告を出力する
