# rl-anything

Claude Code のスキル（SKILL.md）やルール（.claude/rules/*.md）を遺伝的アルゴリズムで自動改善する Claude Code Plugin。

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
/plugin marketplace add ~/matsukaze-utils
/plugin install rl-anything@shohu
```

2行でインストール完了。まず一番問題だった `/bot-create` スキルを最適化してみる。

```
/optimize .claude/skills/bot-create/SKILL.md --dry-run
```

dry-run で構造を確認したら、本番実行。

```
/optimize .claude/skills/bot-create/SKILL.md
```

Claude が3つのバリエーションを生成し、それぞれを評価。3世代の進化を経て、最良のバリエーションが選ばれた。

**差分を見て驚いた。** 自分では気づかなかった改善が入っていた:
- 「personality 設定を**必ず**含めること」という明示的な指示が追加された
- 「設定漏れ時の確認ステップ」がエッジケースとして追加された
- 冗長だった前置きが削除され、手順が簡潔になった

---

### 第3章: ドメイン固有の評価で精度が上がった

汎用評価でもある程度は改善されたが、「Bot としての応答品質」は測れていなかった。組み込みの `default` 評価は「明確性・完全性・構造・実用性」しか見ない。

`/generate-fitness` でプロジェクト固有の評価関数を自動生成した。

```
/generate-fitness
```

CLAUDE.md と rules を分析して、このプロジェクトが Slack Bot であることを自動検出。「パーソナリティ適合」「トーン一貫性」「RAG パイプラインの記述精度」を評価軸に持つ fitness 関数が `scripts/rl/fitness/bot.py` に生成された。

これを使って再最適化:

```
/optimize .claude/skills/bot-create/SKILL.md --fitness bot
```

**スコアが 0.62 → 0.84 に上がった。** 汎用評価では 0.75 止まりだったのが、ドメイン固有の評価軸を入れたことで「Bot のスキルとして本当に良いか」が測れるようになった。

---

### 第4章: 14個のスキルを一括で底上げした

手応えを得たので、自律進化ループで全スキルを回した。

```
/rl-loop .claude/skills/aws-deploy/SKILL.md
/rl-loop .claude/skills/rag-ingest/SKILL.md
/rl-loop .claude/skills/evaluate-personality/SKILL.md
...
```

各スキルについて、ベースラインスコアの取得 → バリエーション生成 → 評価 → 人間確認のループが回る。承認/却下は人間が判断するので、おかしな変更が入ることはない。

1週間後の結果:

| 指標 | Before | After |
|------|--------|-------|
| スキル平均スコア | 0.58 | 0.79 |
| 新メンバーの作業ミス率 | 週3件 | 週0-1件 |
| スキル改善にかける時間 | 週4時間 | 週30分（レビューのみ） |

**スキルの品質が資産として蓄積され、自動的に磨かれ続ける仕組みができた。**

---

## インストール

```
/plugin marketplace add ~/matsukaze-utils
/plugin install rl-anything@shohu
```

## 使い方

### スキルの最適化

```
/optimize .claude/skills/my-skill/SKILL.md
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--generations N` | 世代数 | 3 |
| `--population N` | 集団サイズ | 3 |
| `--fitness FUNC` | 適応度関数名 | default |
| `--dry-run` | 構造テスト（LLM 呼び出しなし） | - |
| `--restore` | バックアップから復元 | - |

### 自律進化ループ

```
/rl-loop .claude/skills/my-skill/SKILL.md
```

ベースライン取得 → バリエーション生成 → 評価 → 人間確認を1コマンドで。

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--loops N` | ループ回数 | 1 |
| `--auto` | 人間確認をスキップ | - |
| `--dry-run` | 構造テスト | - |

### 評価関数の自動生成（予定）

```
/generate-fitness
```

CLAUDE.md・rules・skills を分析し、プロジェクト固有の評価関数を自動生成。

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| `optimize` | LLM でバリエーションを生成し、適応度関数で評価して進化 |
| `rl-loop` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
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
