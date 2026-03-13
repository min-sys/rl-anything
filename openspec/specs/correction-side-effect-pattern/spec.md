## Purpose

副作用見落としに関する corrections パターンを検出し、reflect_utils の suggest_claude_file で適切なルーティングを行う。

## Requirements

### Requirement: 副作用見落とし corrections パターン検出

`reflect_utils.py` に `detect_side_effect_correction(message: str) -> bool` 関数を追加しなければならない（MUST）。corrections メッセージに副作用見落としを示すキーワードパターンが含まれる場合に `True` を返す。

検出キーワード（MUST）:
- 日本語: 「副作用」「残留」「意図しない」「再帰的」
- 日本語複合パターン: `pending.*(?:残留|table|テーブル)`
- 英語: `"side effect"`, `"unintended"`, `"residual"`, `"recursive"`, `"leftover"`

以下のキーワードは FP リスクが高いため含めてはならない（MUST NOT）:
- 「pending」単体（汎用的すぎる）
- 「再帰」単体（「再帰的」のみ許可）
- 「トップレベル投稿」（特殊すぎる）

キーワードは定数リスト `_SIDE_EFFECT_KEYWORDS_JA` / `_SIDE_EFFECT_KEYWORDS_EN` / `_SIDE_EFFECT_COMPOUND_PATTERNS` として定義しなければならない（MUST）。

#### Scenario: 日本語キーワードが含まれる
- **WHEN** message に「副作用を確認していなかった」が含まれる
- **THEN** `True` を返さなければならない（MUST）

#### Scenario: 英語キーワードが含まれる
- **WHEN** message に "unintended side effect" が含まれる
- **THEN** `True` を返さなければならない（MUST）

#### Scenario: 複合パターンがマッチする
- **WHEN** message に「pending テーブルに残留していた」が含まれる
- **THEN** `True` を返さなければならない（MUST）

#### Scenario: 「pending」単体ではマッチしない
- **WHEN** message に「pending の状態を確認」のみが含まれる（残留/table/テーブル を含まない）
- **THEN** `False` を返さなければならない（MUST）

#### Scenario: 「再帰」単体ではマッチしない
- **WHEN** message に「再帰関数」が含まれるが「再帰的」は含まれない
- **THEN** `False` を返さなければならない（MUST）

#### Scenario: 関連キーワードがない
- **WHEN** message に副作用関連キーワードが一切含まれない
- **THEN** `False` を返さなければならない（MUST）

### Requirement: suggest_claude_file への統合

`suggest_claude_file()` は、`detect_side_effect_correction()` が `True` を返す correction に対し、verification ルールディレクトリへのルーティングを提案しなければならない（MUST）。ルーティング先は `.claude/rules/verification.md`、confidence は 0.85 とする。

この判定は既存の project signals チェック（優先度2）の**後**に挿入しなければならない（MUST）。優先度は3とする。project signals が `True` を返した場合、副作用チェックはスキップしなければならない（MUST）。

#### Scenario: 副作用 correction のルーティング
- **WHEN** correction メッセージに「副作用」キーワードが含まれ、project signals がマッチしない
- **THEN** `.claude/rules/verification.md` へのルーティングを提案しなければならない（MUST）。confidence は 0.85 でなければならない（MUST）

#### Scenario: guardrail が優先される
- **WHEN** correction が guardrail タイプかつ副作用キーワードを含む
- **THEN** guardrail ルーティングが優先されなければならない（MUST）

#### Scenario: project signals が優先される
- **WHEN** correction メッセージに副作用キーワードが含まれるが、PJ固有シグナルもマッチする
- **THEN** project signals のルーティングが優先されなければならない（MUST）。副作用チェックはスキップされなければならない（MUST）
