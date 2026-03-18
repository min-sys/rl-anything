## Context

Superpowers (v5.0.5) は開発方法論の強制フレームワーク。14スキル全体をプラグインとして導入すると、OpenSpec とワークフローが重複し（brainstorming↔explore, writing-plans↔propose, executing-plans↔apply）、SessionStart で全スキル発火を強制される（"YOU MUST USE IT"）。

Superpowers から cherry-pick すべき知見は3つ:
- **合理化防止テーブル**: スキップの言い訳を列挙して潰す手法 → rl-anything はテレメトリで定量化できる
- **CSO (Claude Search Optimization)**: description 設計の知見 → Anthropic 公式ツールガイドが裏付け
- **証拠提示義務**: "Evidence before claims" → TDD とは独立した検証パターン

## Goals / Non-Goals

**Goals:**
- 上記3つの知見を rl-anything の既存パイプラインに組み込む
- テレメトリ駆動で合理化防止テーブルを自動生成する（Superpowers は静的・手動）
- 既存の evolve/discover/remediation パイプラインに自然に統合

**Non-Goals:**
- Superpowers プラグインの導入（OpenSpec とワークフロー重複、TDD 全面強制のため不採用）
- TDD 強制ルールの追加
- OpenSpec スキルの変更
- ランタイム hook による合理化ブロック・証拠強制（将来フェーズ）

## Decisions

### D1: 合理化防止テーブルの生成戦略

**選択**: corrections.jsonl + テレメトリ統合型の自動生成

pitfall_manager.py に `generate_rationalization_table()` を追加。corrections.jsonl から「スキップ/バイパス」パターンを検出し、テレメトリ（usage.jsonl, errors.jsonl）と突合して「言い訳 vs 実際の結果」テーブルを生成する。

**代替案**:
- A) Superpowers 式の静的テーブルをハードコード → メンテコスト大、プロジェクト固有性なし
- B) LLM で corrections を分析 → コスト高、再現性低
- C) テレメトリのみ（corrections なし）→ 「なぜスキップしたか」の文脈が欠落

**理由**: corrections.jsonl には「いや違う、先にテストを書いて」等の修正パターンが蓄積されている。これとテレメトリの結果（手戻り率、エラー率）を組み合わせることで、Superpowers が手動で作る合理化防止テーブルを**データ駆動で自動生成**できる。

### D2: CSO チェックの実装場所

**選択**: skill_quality fitness に CSO 軸として統合（独立モジュールにしない）

既存の `scripts/rl/fitness/skill_quality.py`（stdin/stdout スクリプト、7軸ルールベース: headings/frontmatter/examples/ng_ok/line_length/arguments/workflow）に `check_cso_compliance()` 関数を追加し、CSO を **8軸目** として同列に統合する。外部モジュールは不要。

**代替案**:
- A) 独立 fitness 関数 `cso.py` → 呼び出し元が増えて複雑化
- B) discover の enrich に組み込み → fitness と discover の責務混在

**理由**: CSO はスキル品質の一軸であり、skill_quality の拡張として自然。新規 fitness 関数を増やすと audit の複雑性が増す。

### D3: 証拠提示義務パターンの配置

**選択**: verification_catalog.py の VERIFICATION_CATALOG に新パターンとして追加

`evidence-before-claims` パターンを追加。detect 関数で「完了主張なのに実行証拠がない」パターンを検出。

**代替案**:
- A) 独立ルールファイルとして `.claude/rules/` に配置 → discover/remediation との統合が弱い
- B) pitfall テンプレートとして配置 → 検証パターンとしての再利用性が低い

**理由**: verification_catalog は既に discover → issue_schema → remediation のパイプラインに統合済み。新パターンを追加するだけで既存の配信経路を活用できる。

### D4: Superpowers プラグイン導入の見送り

**選択**: プラグインは導入せず、知見のみ cherry-pick

**見送りの理由**:
- Superpowers のワークフロー（brainstorming→writing-plans→executing-plans）が OpenSpec（explore→propose→apply）と重複
- SessionStart で「全スキル MUST 使用」が注入され、CLAUDE.md で抑制しても指示の綱引きが発生
- TDD 強制が全スキルに波及するが、TDD は本プロジェクトの方針に合わない
- Superpowers の価値の 40% が TDD。残り 60% のうち知見レベルで取り込めるものは 3 アイデアのみ

**代替案（検討済み）**:
- A) ハイブリッド（install + CLAUDE.md 抑制）→ 指示の綱引き問題
- B) Fork して rl-anything に組み込み → メンテコスト大
- C) 知見のみ抽出（**採用**）→ 必要な 3 アイデアを rl-anything のパイプラインに組み込む

### D5: 合理化パターン検出の閾値設計

**選択**: 定数化 + evolve-state.json 管理

```python
# scripts/lib/skill_evolve.py に配置（既存の pitfall 定数と同居）
RATIONALIZATION_MIN_CORRECTIONS = 3    # 最低 corrections 数
RATIONALIZATION_SKIP_KEYWORDS = ["スキップ", "不要", "省略", "後で", "skip", "なくても", "大丈夫", "簡単だから"]
RATIONALIZATION_OUTCOME_WINDOW_DAYS = 30  # 結果追跡ウィンドウ
```

**理由**: pitfall_manager の既存パターン（CANDIDATE_MIN_OCCURRENCES=2 等）に倣い、定数化して regression gate でチェック可能にする。skill_evolve.py には ROOT_CAUSE_JACCARD_THRESHOLD, CANDIDATE_PROMOTION_COUNT 等の定数が集約されており、合理化パターンの閾値も同居が適切。

### D6: CSO スコアリングの具体的チェック項目

**選択**: 4 チェック項目（要約ペナルティ、トリガー語ボーナス、行動促進ボーナス、長さペナルティ）

1. **要約ペナルティ**: description が本文の最初の段落と高類似度（Jaccard > 0.5）→ ペナルティ(-0.2)
2. **トリガー語ボーナス**: description に具体的なトリガーワード（動詞、コマンド名等）を含む → ボーナス(+0.1/語, max +0.3)
3. **行動促進ボーナス**: description が「Use when...」「Trigger:」等の行動指示形式 → ボーナス(+0.1)
4. **長さペナルティ**: description が CSO_MAX_DESCRIPTION_LENGTH (1024文字) を超過 → ペナルティ(-0.1)

**理由**: Superpowers の CSO 知見「要約型 description はエージェントに本文をスキップさせる」を定量化。Anthropic の [Tool Guide](https://www.anthropic.com/engineering/writing-tools-for-agents) 推奨の "keep descriptions under 1024 characters" を長さチェックとして取り込む。既存の skill_triggers.py のトリガーワード抽出を再利用できる。

## Risks / Trade-offs

### R1: corrections.jsonl のデータ量不足
合理化パターン検出には一定量の corrections が必要。新規プロジェクトではテーブル生成ができない。
**対策**: `RATIONALIZATION_MIN_CORRECTIONS` ゲートで不十分時はスキップ。backfill で補完可能。

### R2: CSO スコアの偽陽性
description が長い場合に要約ペナルティが誤発火する可能性。
**対策**: Jaccard 閾値を保守的に設定（0.5）。fitness_evolution で accept/reject データから閾値を自動調整。

