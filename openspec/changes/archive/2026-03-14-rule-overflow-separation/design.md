## Context

optimize の regression gate は `line_limit_exceeded` でパッチをリジェクトするが、解決策を提示しない。ユーザーが手動で「skillに逃す？」と気づくまで問題が放置される。

既存の関連実装:
- `scripts/lib/line_limit.py`: 行数制限定数 + `check_line_limit()`
- `scripts/lib/regression_gate.py`: `check_gates()` → `GateResult`
- `skills/genetic-prompt-optimizer/scripts/optimize.py`: gate 不合格時に `_format_gate_reason()` でメッセージ表示
- `skills/evolve/scripts/remediation.py`: `fix_line_limit_violation()` で LLM 圧縮（分離は未実装）

## Goals / Non-Goals

**Goals:**
- optimize gate 不合格（`line_limit_exceeded`）時に skill/references への分離提案を生成・表示
- evolve/remediation で proposable な `line_limit_violation` に対し分離実行ロジックを追加
- reflect で rule 行数超過パターンを検出し corrections に記録

**Non-Goals:**
- rule の自動書き換え（分離は提案のみ、実行はユーザー承認後）
- skill ファイルの行数超過対応（rule に限定）
- CLAUDE.md の行数超過対応（既存の warning_only で十分）

## Decisions

### D1: 分離提案の生成場所 — `line_limit.py` に `suggest_separation()` を追加

**選択肢A**: optimize.py 内にインライン実装
**選択肢B**: line_limit.py に共通関数として追加 ← **採用**

**理由**: optimize / remediation / reflect の3箇所から呼ばれるため共通化が必要。line_limit.py は既に行数関連の Single Source of Truth。

`suggest_separation(target_path, content) -> SeparationProposal | None` を追加。rule の場合のみ分離提案を生成し、分離先パス（`references/<topic>.md` or skill 化）と要約テンプレートを返す。

### D2: optimize gate 不合格時のフロー — 提案メッセージをresultに含める

現在: gate 不合格 → `_format_gate_reason()` → リジェクトメッセージ表示 → 終了
変更後: gate 不合格 → `_format_gate_reason()` に分離提案を追記 → result の `suggestion` フィールドに格納

optimize は LLM 1パスパッチのツールなので、分離実行は行わない。提案テキストを表示してユーザーに判断を委ねる。

### D3: remediation の `fix_line_limit_violation` 拡張 — 分離モード追加

現在: auto_fixable → LLM 圧縮のみ
変更後: auto_fixable かつ rule ファイル → `suggest_separation()` で分離先を決定 → LLM に「要約+参照リンク」への書き換えを指示 + 分離先ファイルを生成

分離実行は evolve パイプライン内（ユーザー承認あり）のため auto で実行可能。

### D4: reflect での検出 — corrections 記録時に行数チェック

reflect は corrections.jsonl を処理して CLAUDE.md/rules に反映する。反映先が rule の場合、反映後の行数を `check_line_limit()` で確認し、超過時は `suggest_separation()` の提案をユーザーに表示。

## Risks / Trade-offs

- [LLM 分離品質] LLM が rule の要約を適切に作れず情報が欠落する → 分離前後の内容を diff で表示し、ユーザーが確認できるようにする
- [分離先の命名] references/ のファイル名が既存と衝突する → `suggest_separation()` で既存ファイルを確認し、衝突時はサフィックス付与
