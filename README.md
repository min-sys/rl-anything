# rl-anything

Claude Code のスキル（SKILL.md）やルール（.claude/rules/*.md）を遺伝的アルゴリズムで自動改善する Claude Code Plugin。

## Before: スキルの手動改善が抱える問題

Claude Code でスキルを書くと、いくつかの問題にぶつかる。

- **品質がバラバラ**: スキルの品質が書いた人の熟練度に依存する。曖昧な記述があると Claude が重要な手順を飛ばす
- **改善が追いつかない**: スキルが10個を超えると、手動で継続的に磨き続ける時間がない
- **基準がない**: 「良いスキル」の定義がチーム内で共有されていない。レビューも属人的になる

## What: 遺伝的アルゴリズムによる自動最適化

rl-anything は、スキル/ルールを遺伝的アルゴリズムで自動改善する。

1. 対象スキルのバリエーションを LLM で複数生成（突然変異 + 交叉）
2. 各バリエーションを適応度関数で評価（0.0〜1.0 のスコア）
3. エリート選択 + 進化で次世代を生成
4. 最良のバリエーションを提案、人間が承認/却下

スラッシュコマンド `/optimize` と `/rl-loop` で即座に実行できる。

## After: 定量的な品質管理が手に入る

| 指標 | Before | After |
|------|--------|-------|
| スキル平均スコア | 0.58 | 0.79 |
| 新メンバーの作業ミス率 | 週3件 | 週0-1件 |
| スキル改善にかける時間 | 週4時間 | 週30分（レビューのみ） |

- スキルの品質が数値で見える。改善が自動化される
- 新スキル追加時に `/optimize` を1回通すだけで品質の底上げが完了する
- 評価関数をプロジェクト固有にカスタマイズすることで、ドメインに最適化された改善が得られる

## クイックスタート

```bash
# Step 1: インストール（ターミナルで実行）
curl -sL https://raw.githubusercontent.com/shohu/rl-anything/main/install.sh | bash

# Step 2: Claude Code を再起動して新しいプラグインを読み込む

# Step 3: 既存セッション履歴からデータを収集＋分析
/rl-anything:backfill

# Step 4: プロジェクト固有の評価関数を生成
/rl-anything:generate-fitness

# Step 5: スキルを1つ最適化してみる
/rl-anything:optimize my-skill

# Step 6: 結果に満足したら、自律進化ループで継続改善
/rl-anything:rl-loop my-skill
```

## 導入ストーリー: ある Slack Bot プロジェクトの場合

### 第1章: スキルが増えて、品質がばらつき始めた

ある日、あなたは Claude Code で Slack Bot を開発している。Bot の応答品質を上げるために、14個のスキルを `.claude/skills/` に書いた。

- `/aws-deploy` — CDK デプロイ手順
- `/rag-ingest` — RAG データ投入
- `/evaluate-personality` — 応答品質の評価
- `/bot-create` — 新ボット作成
- ...他10個

最初は手作業でスキルを磨いていた。「この言い回しの方が Claude の出力がいいな」「エッジケース追加しよう」。だが14個もあると、**改善が追いつかない**。

あるとき、新メンバーが `/bot-create` を使ったら、Bot の personality 設定が抜け落ちた応答が生成された。スキルの記述が曖昧で、Claude が重要な手順を飛ばしたのだ。

**問題は明確だった**:
- スキルの品質がバラバラ。書いた人の熟練度に依存している
- 手動で14個を継続的に磨き続ける時間がない
- 「良いスキル」の基準がチーム内で共有されていない

---

### 第2章: rl-anything を導入した

```
/rl-anything:optimize bot-create --dry-run
```

dry-run で構造を確認したら、本番実行。

```
/rl-anything:optimize bot-create
```

Claude が3つのバリエーションを生成し、それぞれを評価。3世代の進化を経て、最良のバリエーションが選ばれた。

**差分を見て驚いた。** 自分では気づかなかった改善が入っていた:
- 「personality 設定を**必ず**含めること」という明示的な指示が追加された
- 「設定漏れ時の確認ステップ」がエッジケースとして追加された
- 冗長だった前置きが削除され、手順が簡潔になった

---

### 第3章: ドメイン固有の評価で精度が上がった

汎用評価でもある程度は改善されたが、「Bot としての応答品質」は測れていなかった。組み込みの `default` 評価は「明確性・完全性・構造・実用性」しか見ない。

`/rl-anything:generate-fitness` でプロジェクト固有の評価関数を自動生成した。

```
/rl-anything:generate-fitness
```

CLAUDE.md と rules を分析して、このプロジェクトが Slack Bot であることを自動検出。「パーソナリティ適合」「トーン一貫性」「RAG パイプラインの記述精度」を評価軸に持つ fitness 関数が `scripts/rl/fitness/bot.py` に生成された。

これを使って再最適化:

```
/rl-anything:optimize bot-create --fitness bot
```

**スコアが 0.62 → 0.84 に上がった。** 汎用評価では 0.75 止まりだったのが、ドメイン固有の評価軸を入れたことで「Bot のスキルとして本当に良いか」が測れるようになった。

---

### 第4章: 14個のスキルを一括で底上げした

手応えを得たので、自律進化ループで全スキルを回した。

```
/rl-anything:rl-loop aws-deploy
/rl-anything:rl-loop rag-ingest
/rl-anything:rl-loop evaluate-personality
...
```

各スキルについて、ベースラインスコアの取得 → バリエーション生成 → 評価 → 人間確認のループが回る。承認/却下は人間が判断するので、おかしな変更が入ることはない。

---

### 第5章: 運用に乗せた

一括最適化で底上げできた。だが本当の価値は「継続的に品質を維持・向上できること」にある。チームで以下の運用サイクルを回し始めた。

#### 新スキル追加時

新メンバーが `/slack-thread-summary` スキルを書いた。まず最適化を1回通す。

```
/rl-anything:optimize slack-thread-summary --fitness bot
```

レビューで diff を確認して承認。「エッジケースが足りない」「手順が曖昧」といった問題が自動で修正される。**PR レビューの前に品質の底上げが終わっている**状態になった。

#### 定期メンテナンス（月1回）

月1回、全スキルに自律進化ループを回す。

```
/rl-anything:rl-loop aws-deploy
/rl-anything:rl-loop rag-ingest
...
```

スキルの内容は変わっていなくても、評価基準（fitness 関数）が改善されたり、LLM の能力が変わることで新たな改善が見つかる。スコアが前回から下がったスキルがあれば重点的にチェックする。

#### スコアが下がったとき

CLAUDE.md やルールを大きく書き換えた後、既存スキルとの整合性が崩れることがある。`--fitness bot` で再評価すると、影響を受けたスキルのスコア低下がすぐに分かる。

```
/rl-anything:optimize bot-create --fitness bot --dry-run
```

dry-run でスコアだけ確認し、問題があれば本番実行して修復。**変更の影響が定量的に見える**ので、壊れたまま放置されない。

#### 評価関数の育て方

運用していると「この観点が評価に足りない」と気づく。fitness 関数を手動で調整する。

```python
# scripts/rl/fitness/bot.py に追加
if "エラーハンドリング" not in content:
    score -= 0.1  # Bot スキルにエラー処理の記述がなければ減点
```

評価関数を育てるほど、最適化の精度が上がる。**スキルの品質基準がコードとして蓄積される**。

#### 運用のまとめ

| タイミング | やること | 所要時間 |
|-----------|---------|---------|
| 新スキル追加時 | `/optimize` で1回最適化 → diff レビュー | 5分 |
| 月1回 | 全スキルに `/rl-loop` → スコア確認 | 30分 |
| CLAUDE.md/ルール変更後 | 影響スキルを `--dry-run` で再評価 | 10分 |
| 評価に不足を感じたとき | fitness 関数を手動調整 | 15分 |

**3ヶ月後の振り返り**: スキルの平均スコアは 0.79 → 0.85 に上がり、「スキルの品質が原因の事故」はゼロになった。新メンバーのオンボーディングでも「まず `/optimize` を通して」が定着し、最初から一定品質のスキルがチームに入るようになった。

---

## 詳細リファレンス

### スキルの最適化（`/rl-anything:optimize`）

スラッシュコマンド:

```
/rl-anything:optimize <TARGET> [OPTIONS]
```

スクリプト直接実行:

```bash
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md [OPTIONS]
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--target PATH` | 最適化対象のスキルファイルパス | 必須 |
| `--generations N` | 世代数 | 3 |
| `--population N` | 集団サイズ | 3 |
| `--fitness FUNC` | 適応度関数名 | default |
| `--dry-run` | 構造テスト（LLM 呼び出しなし） | - |
| `--restore` | バックアップから復元 | - |

### 自律進化ループ（`/rl-anything:rl-loop`）

スラッシュコマンド:

```
/rl-anything:rl-loop <TARGET> [OPTIONS]
```

スクリプト直接実行:

```bash
python3 <PLUGIN_DIR>/skills/rl-loop-orchestrator/scripts/run-loop.py \
  --target .claude/skills/my-skill/SKILL.md [OPTIONS]
```

ベースライン取得 → バリエーション生成 → 評価 → 人間確認を1コマンドで。

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--target PATH` | 対象スキルファイルパス | 必須 |
| `--loops N` | ループ回数 | 1 |
| `--auto` | 人間確認をスキップ | - |
| `--dry-run` | 構造テスト | - |

### 評価関数の自動生成（`/rl-anything:generate-fitness`）

CLAUDE.md・rules・skills を分析し、プロジェクト固有の評価関数を自動生成。

```
/rl-anything:generate-fitness
```

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| `genetic-prompt-optimizer` | LLM でバリエーションを生成し、適応度関数で評価して進化 |
| `rl-loop-orchestrator` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
| `rl-scorer` エージェント | 技術品質 + ドメイン品質 + 構造品質の3軸で採点 |

## 適応度関数

### 組み込み

| 関数 | 説明 |
|------|------|
| `default` | LLM による汎用評価（明確性・完全性・構造・実用性） |
| `skill_quality` | ルールベースの構造品質チェック |

### プロジェクト固有

`scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}` で使用。

インターフェース: stdin でスキル内容を受け取り、0.0〜1.0 を stdout に出力。

```python
#!/usr/bin/env python3
import sys

def evaluate(content: str) -> float:
    score = 0.0
    if "必須キーワード" in content:
        score += 0.5
    return score

def main():
    content = sys.stdin.read()
    print(f"{evaluate(content)}")

if __name__ == "__main__":
    main()
```

## rl-scorer のドメイン自動判定

CLAUDE.md からドメインを推定し、評価軸を自動切替。

| ドメイン | 評価軸 |
|----------|--------|
| ゲーム | 没入感・面白さ・バランス・具体性 |
| API/バックエンド | 正確性・堅牢性・保守性・セキュリティ |
| Bot/対話 | パーソナリティ適合・有用性・トーン一貫性 |
| ドキュメント | 正確性・可読性・実行可能性・完全性 |

## 向いているプロジェクト

| 特徴 | 理由 |
|------|------|
| スキルが10個以上 | 手動メンテのコストが高い。一括で品質底上げできる |
| ドメイン固有の語彙・ルールがある | 汎用評価では「良いスキル」を測れない |
| スキル品質が Claude の出力品質に直結 | スキルが雑だと Claude の出力も雑になる |
| チームで Claude Code を使っている | 暗黙知をスキル化 → 最適化 → チーム全体の品質向上 |

## テスト

```bash
python3 -m pytest skills/ -v
```

## ライセンス

MIT
