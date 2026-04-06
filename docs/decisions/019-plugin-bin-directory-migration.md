# ADR-019: Plugin bin/ ディレクトリへの移行とライブラリ再設計

Date: 2026-04-06
Status: Accepted
Related: CC v2.1.91 Plugin bin/ サポート追加

## Context

CC v2.1.91 でプラグインが `bin/` 配下に実行ファイルを置き、Bash tool から bare command として呼べるようになった。

rl-anything の `skills/*/scripts/*.py` は以下の二役を兼ねていた:

1. **CLI entry point** — SKILL.md の `python3 <PLUGIN_DIR>/skills/*/scripts/*.py` で起動
2. **importable module** — `evolve.py` が `from audit import run_audit` のように他スクリプトを直接 import

`<PLUGIN_DIR>` プレースホルダーは LLM が実行時に解決する設計で、解決ミスのリスクと認知負荷があった。また `evolve.py` 冒頭には他スキルの scripts ディレクトリを sys.path に追加する行が 8 本あり、構造的な複雑さの原因となっていた。加えて `hooks/common.py` が hook scripts と library scripts の双方から参照される「二役」状態にあり、`handover.py` と `reflect.py` が `sys.path.insert(hooks/)` という設計本来の意図と異なる参照をしていた。

## Decision

以下の完全移行（Approach B）を採用する:

1. **`scripts/lib/plugin_root.py` を新設** — `PLUGIN_ROOT` 定数を一箇所で定義し、全スクリプトの `.parent.parent.parent.parent` ハードコードを廃止する

2. **cross-import される scripts を `scripts/lib/` に移動** — `audit.py`, `discover.py`, `prune.py`, `reorganize.py`, `remediation.py` を `scripts/lib/` へ移動する。モジュール名は維持するため、既存の `from audit import run_audit` 等のコードは変更不要

3. **`bin/` に thin CLI を新設** — `bin/rl-{audit,discover,prune,reorganize,evolve,reflect,handover,optimize,loop,backfill,...}` として実行権限付きの Python スクリプトを配置する。各ファイルは `scripts/lib/` の関数を呼ぶ薄いラッパー

4. **`hooks/common.py` を thin re-exporter に変更** — DATA_DIR, append_jsonl 等の共有ユーティリティを `scripts/lib/rl_common.py` に移動し、`hooks/common.py` は `from rl_common import *` だけの再エクスポーターになる。`handover.py` と `reflect.py` の `sys.path.insert(hooks/)` を削除する

5. **SKILL.md の呼び出しを bare command に更新** — `python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py` → `rl-audit`

6. **pytest P0 collision を同時解消** — 各テストディレクトリに `__init__.py` を追加する

移行後、`skills/` 配下は SKILL.md のみを含む。実行ファイルは `bin/`、ライブラリは `scripts/lib/`、CC 向けスペックは `skills/*/SKILL.md` に完全に役割が分離される。

## Alternatives Considered

### Approach A: Shell thin wrapper のみ（ファイル移動なし）

`bin/rl-audit` を `exec python3 "${CLAUDE_PLUGIN_ROOT}/skills/audit/scripts/audit.py" "$@"` とする 1 行 bash wrapper。Python ファイルはそのまま。

不採用理由: import グラフの問題が残る。`evolve.py` の sys.path 8 行は消えない。`hooks/common.py` の二役も解消しない。「短い bare command」の恩恵だけを得て、構造的な問題は先送りになる。

### Approach C: 何もしない

既存の `<PLUGIN_DIR>` パターンのまま。

不採用理由: LLM のパス解決依存が残る。コマンドラインからの手動実行や CI でのスクリプト直接呼び出しが煩雑なまま。

## Consequences

**良い影響**:
- `evolve.py` の sys.path 操作が 8 行 → 2 行に削減される（scripts/lib/ が直接参照可能になるため）
- SKILL.md の bash ブロックが `rl-audit "$(pwd)"` と簡潔になり、`<PLUGIN_DIR>` の解決が不要になる
- `bin/` で全 CLI が発見可能になる（`ls bin/rl-*` で一覧できる）
- CI からスクリプトを直接呼べる（`bin/rl-audit --dry-run`）
- `hooks/` cross-import が完全に解消される
- pytest P0 collision が同時に解消される
- `skills/` = Claude 向け仕様、`bin/` = 実行ファイル、`scripts/lib/` = ライブラリ という役割分担が明確になる

**悪い影響**:
- 移行スコープが Approach A より大きい（scripts/lib/ 集約 + bin/ 作成 + テスト更新）
- `skills/enrich/` は deprecated 済みだが削除は別 PR が必要
- `hooks/` を importable module として使う既存パターン（`handover.py`, `reflect.py`）のリファクタが必要
- `_plugin_root` の depth が移動先によって変わるため、`plugin_root.py` による一本化が必須
