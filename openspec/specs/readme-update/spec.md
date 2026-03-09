## MODIFIED Requirements

### Requirement: README.md のストーリー構成

README.md を Before/After のストーリー構成で全面更新する（SHALL）。導入前の課題、Plugin の概要、導入後の効果を描く。加えて、evolve フローの記述を実装の7フェーズに合わせて更新し、Before/After チュートリアルセクションを追加する。

#### Scenario: Before（課題）セクションが存在する
- **WHEN** README.md を確認する
- **THEN** 「スキル/ルールの手動改善に時間がかかる」「改善の品質が属人的」等の導入前の課題が記述されている

#### Scenario: What（概要）セクションが存在する
- **WHEN** README.md を確認する
- **THEN** rl-anything が何をするか（直接パッチによるスキル/ルールの自動最適化）が簡潔に記述されている

#### Scenario: After（効果）セクションが存在する
- **WHEN** README.md を確認する
- **THEN** 導入後の具体的な効果（スラッシュコマンドで即座に最適化開始、定量的なスコアによる品質管理）が記述されている

#### Scenario: evolve フローが7フェーズで記述されている
- **WHEN** README.md の evolve セクションを確認する
- **THEN** Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → Reflect → Report の全フェーズが記述されている

#### Scenario: Before/After チュートリアルが存在する
- **WHEN** README.md のチュートリアルセクションを確認する
- **THEN** 1つのスキルを `/rl-anything:evolve` で改善する手順と、改善前後のスコア比較が記載されている

### Requirement: README.md のクイックスタートがスラッシュコマンド形式

README.md のクイックスタートは `python3 <PLUGIN_DIR>/...` ではなく、スラッシュコマンド形式で記述する（SHALL）。

#### Scenario: /optimize のクイックスタートが記載されている
- **WHEN** README.md のクイックスタートセクションを確認する
- **THEN** `/optimize --target .claude/skills/my-skill/SKILL.md` 形式の使用例が記載されている

#### Scenario: /rl-loop のクイックスタートが記載されている
- **WHEN** README.md のクイックスタートセクションを確認する
- **THEN** `/rl-loop --target .claude/skills/my-skill/SKILL.md` 形式の使用例が記載されている

#### Scenario: python3 コマンドの直接実行は詳細リファレンスに移動
- **WHEN** README.md のクイックスタートセクションを確認する
- **THEN** `python3 <PLUGIN_DIR>/...` 形式のコマンドはクイックスタートに含まれず、詳細リファレンスセクションに記載されている
