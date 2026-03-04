## Context

現在の prune スキルは `detect_zero_invocations()` で30日間使用ゼロのスキルを検出し、AskUserQuestion で「全てアーカイブ / 個別に選択 / スキップ」の3択を提示する。ユーザーはスキル名しか見えないため、中身を知らないスキルについて判断できない。

SKILL.md には必ず `description` フィールドがあり、各スキルの目的を1行で記述している。これを活用すれば、追加の LLM 呼び出しなしで基本的なコンテキストを提供できる。

さらに、SKILL.md の全文を Claude に読ませれば「今後必要か？」の推薦判定が可能だが、これは SKILL.md の instructions 内で Claude に実行させる形で実現する（Python スクリプト側ではなく）。

## Goals / Non-Goals

**Goals:**
- prune 候補の各スキルについて、description を検出結果に含める（zero_invocations, decay_candidates, global_candidates）
- Python 側でキーワードベースの一次判定を行い、Claude が SKILL.md 全文で最終判定する2段階推薦
- AskUserQuestion の options 上限（4つ）を遵守した2段階承認フローに変更する
- frontmatter パースロジックを `scripts/lib/frontmatter.py` に共通化し DRY 原則を守る

**Non-Goals:**
- Python スクリプト内での LLM 呼び出し（コスト・複雑性の増加を避ける）
- prune の検出ロジック自体の変更（30日閾値、decay スコア等はそのまま）
- 自動アーカイブ（人間承認は引き続き必須）

## Decisions

### Decision 1: frontmatter パースの共通化（`scripts/lib/frontmatter.py`）

**選択**: `scripts/lib/frontmatter.py` に汎用 YAML frontmatter パーサーを新設し、`prune.py` と `reflect_utils.py` の両方から利用する。

- `parse_frontmatter(filepath)` — 汎用 YAML frontmatter パーサー（`---` 区切り）
- `extract_description(filepath)` — description 抽出（multiline 対応、1行目のみ返却）
- `prune.py` の `extract_skill_summary()` は `extract_description()` のラッパー
- `reflect_utils._parse_rule_frontmatter()` は `parse_frontmatter()` に置換

**理由**: `reflect_utils.py` に既存の `_parse_rule_frontmatter()` があり、同じ YAML frontmatter パースロジックを prune.py にも追加すると DRY 違反。共通モジュールに統合する。

**代替案**:
- `reflect_utils._parse_rule_frontmatter()` を public にして prune から import → reflect_utils への不適切な依存
- prune.py 内に独自実装 → DRY 違反

### Decision 2: 推薦ラベルの2段階判定（Python 一次判定 + Claude 最終判定）

**選択**: Python 側でキーワードベースの一次判定を行い、Claude が SKILL.md 全文を読んで最終判定を上書きする。

#### Python 一次判定（`suggest_recommendation()`）

| 一次ラベル | キーワード手がかり |
|------------|---------------------|
| `archive推奨` | name/description に "debug", "temp", "hotfix", "workaround", "test-" を含む |
| `keep推奨` | name/description に "daily", "pipeline", "utility" を含む、または Trigger が3個以上 |
| `要確認` | 上記いずれにも該当しない |

#### Claude 最終判定（SKILL.md instructions チェックリスト）

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

**理由**: 主観的な Claude 判定だけだと基準がブレる。Python で客観的な一次判定を行い、Claude は文脈を踏まえた上書き判定のみにすることで、再現性と判断品質を両立。

### Decision 3: 2段階承認フロー（AskUserQuestion options 上限対応）

**選択**: multiSelect 形式から2段階フローに変更。

1. **テキスト出力**: 全候補一覧を推薦ラベル + description 付きで表示
2. **AskUserQuestion（3択）**: 「全てアーカイブ / 個別に選択 / スキップ」
3. **個別 AskUserQuestion**:「個別に選択」時、各候補に対して「アーカイブ / 維持 / 後で判断」の3択

**理由**: AskUserQuestion は `maxItems: 4` の制約がある。候補3つ + 全てアーカイブ + スキップ = 5 options は動作しない。2段階フローなら options 数を常に3〜4に収められる。

**代替案**:
- multiSelect でカテゴリ別分割 → カテゴリ数が少ない場合に不自然な分割が発生
- 全てテキスト入力 → 構造化されず誤操作リスクが高い

## Risks / Trade-offs

- **[2段階フローの操作負荷] → 候補が多いと個別質問が多くなる**
  → 「全てアーカイブ」「スキップ」で一括処理可能。個別選択は必要な場合のみ。
- **[Claude の推薦が外れる場合] → ユーザーが誤判断する**
  → Python 一次判定 + Claude 最終判定の2段階で精度向上。推薦はあくまで参考情報。最終判断はユーザー。
- **[SKILL.md を読む追加コスト] → コンテキストウィンドウ消費**
  → 候補スキル数は通常3〜5個程度。SKILL.md は小さいファイルなので影響は軽微。
- **[description 空文字時のフォールバック] → ユーザーが判断材料を得られない**
  → SKILL.md instructions 側で `"(説明なし)"` と表示し、SKILL.md 全文を Read で読み取って要約を生成する。Python 側は空文字を返すのみ。
