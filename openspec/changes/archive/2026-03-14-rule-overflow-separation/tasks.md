## 1. line_limit.py に分離提案機能追加

- [x] 1.1 `SeparationProposal` dataclass を `scripts/lib/line_limit.py` に追加
- [x] 1.2 `suggest_separation(target_path, content)` 関数を実装（rule判定・超過チェック・分離先パス生成・衝突回避）
- [x] 1.3 `suggest_separation` のユニットテスト追加（グローバルrule/PJ rule/skill/制限内/衝突回避の各シナリオ）

## 2. optimize の gate フィードバック拡張

- [x] 2.1 `_format_gate_reason()` で `line_limit_exceeded` 時に `suggest_separation()` を呼び出し、提案メッセージを追記
- [x] 2.2 result dict に `suggestion` フィールドを追加
- [x] 2.3 optimize の gate フィードバックテスト追加（rule超過時の提案表示、skill超過時の非表示）

## 3. remediation の分離実行モード追加

- [x] 3.1 `fix_line_limit_violation()` で対象が rule の場合に分離モード（要約+参照リンク書き換え + 分離先ファイル生成）を追加
- [x] 3.2 `_verify_line_limit_violation()` で分離後の rule 行数制限チェックと分離先ファイル存在確認を追加
- [x] 3.3 remediation 分離モードのテスト追加

## 4. reflect での行数チェック追加

- [x] 4.1 reflect の rule 反映処理に `check_line_limit()` + `suggest_separation()` 呼び出しを追加
- [x] 4.2 reflect 行数チェックのテスト追加
