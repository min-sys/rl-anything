## Why

prune スキルが「過去30日間で呼び出しゼロのスキルをアーカイブしますか？」と提示するが、スキルの中身が分からないためユーザーが判断できない。「漠然といわれても判断できない」というフィードバックがあった。使用頻度だけでなく、スキルの内容を踏まえた「今後必要か？」の推薦があれば、ユーザーは自信を持って判断できる。

## What Changes

- SKILL.md の description を読み取り、各候補スキルの1行説明を AskUserQuestion の options に含める
- LLM にスキル内容を分析させ「今後も必要そうか？」の推薦ラベル（keep推奨 / archive推奨 / 判断保留）を付与する
- AskUserQuestion を multiSelect 形式に変更し、個別選択可能にする
- prune.py に `extract_skill_summary()` 関数を追加し、SKILL.md から description を抽出する

## Capabilities

### New Capabilities
- `skill-content-analysis`: 候補スキルの SKILL.md を読み取り、description 抽出 + LLM による必要性判定を行う

### Modified Capabilities
（既存 spec への要件変更なし）

## Impact

- `skills/prune/SKILL.md`: Step 2〜3 のフロー変更（コンテキスト収集 + multiSelect）
- `skills/prune/scripts/prune.py`: `extract_skill_summary()` 関数の追加
- LLM 呼び出しコスト: 候補スキル数 × 1回の軽量判定（SKILL.md の description 解析のみ）
