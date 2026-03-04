## ADDED Requirements

### Requirement: 共通 frontmatter パーサーで description を抽出する

`scripts/lib/frontmatter.py` に汎用 YAML frontmatter パーサーを新設する（MUST）。

- `parse_frontmatter(filepath)` — YAML frontmatter を辞書として返す
- `extract_description(filepath)` — `description` フィールドを抽出し、multiline の場合は1行目のみ返す

`prune.py` の `extract_skill_summary(skill_path)` は `extract_description()` のラッパーとして実装する（MUST）。
`reflect_utils._parse_rule_frontmatter()` は `parse_frontmatter()` に置換する（MUST）。

SKILL.md が存在しない場合やパース不可の場合は空文字を返す（MUST）。

#### Scenario: 正常な SKILL.md から description を抽出する
- **WHEN** `extract_skill_summary()` に有効な SKILL.md パスが渡される
- **THEN** frontmatter の `description` フィールドの値が1行文字列として返される

#### Scenario: SKILL.md が存在しない場合
- **WHEN** `extract_skill_summary()` に存在しないパスが渡される
- **THEN** 空文字 `""` が返される

#### Scenario: frontmatter に description がない場合
- **WHEN** SKILL.md の frontmatter に `description` フィールドがない
- **THEN** 空文字 `""` が返される

#### Scenario: multiline description の場合
- **WHEN** SKILL.md の frontmatter に複数行の `description` がある
- **THEN** 1行目のみが返される

#### Scenario: reflect_utils が共通パーサーを使用する
- **WHEN** `reflect_utils.suggest_claude_file()` が rule の frontmatter を解析する
- **THEN** `scripts/lib/frontmatter.parse_frontmatter()` が呼ばれる（`_parse_rule_frontmatter()` は使用しない）

### Requirement: prune 検出結果に description を含める

`run_prune()` の返却する `zero_invocations`、`decay_candidates`、`global_candidates` の各要素に `description` フィールドを追加する（MUST）。各検出関数の返却値に `extract_skill_summary()` で取得した description を付与する。

#### Scenario: zero_invocations に description が含まれる
- **WHEN** `run_prune()` を実行し `zero_invocations` に候補がある
- **THEN** 各候補の辞書に `description` キーが存在し、SKILL.md の description 値が入っている

#### Scenario: decay_candidates に description が含まれる
- **WHEN** `run_prune()` を実行し `decay_candidates` に候補がある
- **THEN** 各候補の辞書に `description` キーが存在する

#### Scenario: global_candidates に description が含まれる
- **WHEN** `run_prune()` を実行し `global_candidates` に候補がある
- **THEN** 各候補の辞書に `description` キーが存在する

#### Scenario: description 取得失敗時も候補は検出される
- **WHEN** 候補スキルの SKILL.md が存在しない
- **THEN** 候補はリストに含まれ、`description` は空文字となる

#### Scenario: description 空文字時の UI 表示
- **WHEN** 候補スキルの `description` が空文字である
- **THEN** SKILL.md instructions 側で `"(説明なし)"` と表示し、SKILL.md 全文を Read で読み取り要約を生成する

### Requirement: Python 一次判定と Claude の推薦ラベル最終判定

Python 側でキーワードベースの一次判定を行い、Claude が SKILL.md 全文を読み取って最終判定する（MUST）。

#### Python 一次判定ロジック

| 一次ラベル | キーワード手がかり |
|------------|---------------------|
| `archive推奨` | name/description に "debug", "temp", "hotfix", "workaround", "test-" を含む |
| `keep推奨` | name/description に "daily", "pipeline", "utility" を含む、または Trigger が3個以上 |
| `要確認` | 上記いずれにも該当しない |

`prune.py` に `suggest_recommendation(skill_info: dict) -> str` 関数を追加し、一次ラベルを返す（MUST）。

#### Claude 最終判定（SKILL.md instructions）

Step 2 で Claude は各候補の SKILL.md 全文を Read で読み取り、以下のチェックリストで最終判定する（MUST）。Python 一次判定を上書きしてよい。

**archive推奨チェックリスト:**
- [ ] 特定PJ固有で他PJでは使えない
- [ ] 一時デバッグ・hotfix 用途で目的完了済み
- [ ] 他スキルに機能が統合済み
- [ ] description に "deprecated" や "obsolete" を含む

**keep推奨チェックリスト:**
- [ ] 複数PJで利用可能な汎用スキル
- [ ] リファレンス・テンプレート価値がある
- [ ] 定期的に必要になる性質（daily, weekly, deploy 等）
- [ ] Trigger が3個以上定義されている

**判定ルール**: いずれか2つ以上該当 → そのラベル、両方1つずつ or いずれも0 → 要確認

#### Scenario: 汎用スキルに keep推奨 が付く
- **WHEN** 候補スキルの SKILL.md に複数プロジェクトで利用可能な記述がある
- **THEN** Claude は `keep推奨` ラベルを付与する

#### Scenario: デバッグ用スキルに archive推奨 が付く
- **WHEN** 候補スキルの SKILL.md に特定バグ修正やデバッグ目的の記述がある
- **THEN** Claude は `archive推奨` ラベルを付与する

#### Scenario: 判断困難なスキルに 要確認 が付く
- **WHEN** スキルの用途がユーザーの個別状況に依存する
- **THEN** Claude は `要確認` ラベルを付与する

#### Scenario: Python 一次判定で archive推奨 のキーワードに該当する
- **WHEN** スキル名に "debug" を含む
- **THEN** `suggest_recommendation()` は `"archive推奨"` を返す

#### Scenario: Python 一次判定で keep推奨 のキーワードに該当する
- **WHEN** スキルの description に "daily" を含む
- **THEN** `suggest_recommendation()` は `"keep推奨"` を返す

### Requirement: 2段階承認フローで人間承認を行う

prune の人間承認フローは2段階で行う（MUST）。AskUserQuestion の options は常に4つ以下とする（MUST）。

#### Stage 1: テキスト出力で全候補一覧を表示

候補スキルの一覧をテキスト出力する。各スキルは以下の形式:

```
1. スキル名 [推薦ラベル]
   説明: description（空文字の場合は "(説明なし)"）
```

#### Stage 2: AskUserQuestion で方針を選択（3択）

AskUserQuestion で以下の3つの options を提示する（MUST）:

| option | label | description |
|--------|-------|-------------|
| 1 | 全てアーカイブ | 一覧の全候補をアーカイブする |
| 2 | 個別に選択 | 各候補について個別に判断する |
| 3 | スキップ | 全て維持し、何もしない |

#### Stage 3: 個別選択フロー（「個別に選択」の場合）

各候補スキルに対して個別に AskUserQuestion を表示する（MUST）。各質問の options は3つ:

| option | label | description |
|--------|-------|-------------|
| 1 | アーカイブ | このスキルをアーカイブする |
| 2 | 維持 | このスキルを維持する |
| 3 | 後で判断 | 今回はスキップする |

#### Scenario: 3つの候補がある場合の表示
- **WHEN** zero_invocations に3つの候補がある
- **THEN** テキストで3つの候補一覧を表示し、AskUserQuestion で3択（全てアーカイブ / 個別に選択 / スキップ）を提示する

#### Scenario: 個別に選択が選ばれた場合
- **WHEN** ユーザーが「個別に選択」を選択する
- **THEN** 各候補に対して個別の AskUserQuestion（アーカイブ / 維持 / 後で判断）が順次表示される

#### Scenario: 候補が1つの場合
- **WHEN** zero_invocations に1つの候補がある
- **THEN** テキストで1つの候補を表示し、AskUserQuestion で3択を提示する

#### Scenario: 候補が0の場合
- **WHEN** zero_invocations が空
- **THEN** AskUserQuestion は表示されず、「未使用スキルはありません」と報告する
