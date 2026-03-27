---
name: spec-keeper
description: >
  プロジェクトの仕様全体像（SPEC.md）と設計判断記録（ADR）を管理するグローバルスキル。
  gstack の /document-release 後や機能完了時に SPEC.md を最新化し、設計判断があれば
  ADR を自動生成する。AI が新セッションで即座にプロジェクトを理解するための仕組み。

  使用タイミング:
  (1) 新PJで SPEC.md を初期化したい時
  (2) /ship or /document-release 後に仕様を最新化したい時
  (3) 設計判断を ADR として記録したい時
  (4) 「仕様を更新して」「SPEC.md を最新にして」と言われた時

  トリガーワード: spec-keeper, 仕様更新, SPEC.md, ADR, 仕様初期化, spec init,
  spec update, 設計判断記録, decision record, recover, リカバリー, 乖離

  gstack の /ship や /document-release の後に積極的に提案する。
  また新PJで CLAUDE.md はあるが SPEC.md がない場合にも提案する。
---

# spec-keeper

プロジェクトの「現在の仕様全体像」と「設計判断の経緯」を永続化するスキル。
AI が新セッション開始時に SPEC.md を読むだけでプロジェクトを理解できる状態を維持する。

## コンセプト: 4層構造

```
CLAUDE.md              <- 動作ルール（ガードレール、スキル、規約）
SPEC.md                <- 現在の仕様全体像（AI が最初に読むべき）
docs/decisions/        <- ADR（設計判断の「なぜ」を記録）
~/.gstack/projects/    <- セッション単位の設計ドック（gstack 管理）
```

CLAUDE.md は「どう動くか」、SPEC.md は「今何ができるか」、ADR は「なぜそうなったか」。

## Progressive Disclosure レイヤー

SPEC.md は AI がセッション開始時に全量読むドキュメント。Context rot 研究により、無関係だが正しい情報が増えるほど LLM の出力品質が劣化することが実証されている。PJ 規模に応じて適切なレイヤー構成を取る。

### レイヤー定義

| Layer | 構成 | SPEC.md 目安 | 対象PJ |
|-------|------|-------------|--------|
| **L1** | SPEC.md のみ | ~100行以下 | 個人ツール、Bot、小さい API |
| **L2** | SPEC.md (hot) + spec/ (cold) | hot ~60行 | Plugin、SaaS バックエンド |

L3（ドメイン別3層）は該当PJ出現時に検討。

### 閾値

| Layer | 指標 | Healthy | Caution | Action |
|-------|------|---------|---------|--------|
| L1 | SPEC.md 行数 | ~80行以下 | 81-100行 | >100行: L2 昇格を提案 |
| L2 | hot 行数 | ~60行以下 | 61-80行 | >80行: cold へセクション移動 |
| L2 | cold 合計 | ~200行以下 | 201-300行 | >300行: L3 検討（将来） |

### レイヤー判定

- `spec/` ディレクトリが存在する → L2
- 存在しない → L1

### L1 → L2 昇格手順（update 中に提案、承認で即実行）

1. `spec/` ディレクトリを作成
2. 最も行数の多いセクション（通常 Architecture）の詳細を `spec/architecture.md` に移動
3. SPEC.md にサマリー + ポインタを残す（`references/templates.md` の Layer Split Guide 参照）
4. 次に大きいセクションも同様に（hot が 60行以下になるまで）
5. CLAUDE.md の Specification セクションに `- 詳細仕様: [spec/](spec/)` を追加

### 原則

- **ポインタ > インライン** — 詳細はファイルパスで参照し、エージェントが必要時に Read する
- **全タスクに必要な情報のみ hot に残す** — 特定タスクにしか使わない情報は cold へ
- **ツールに委譲できることは書かない** — linter/テストで保証できることは SPEC.md に不要

## コマンド

### `/spec-keeper init` — SPEC.md + ADR の初期化

新PJ、または既存PJに初めて導入する時に使う。
init は利用可能な全情報源を読み込み、SPEC.md と ADR を一括生成する。

#### Step 1: 情報源の収集

プロジェクトにある全ての情報源を探索する。見つかったものだけ読む。

| 優先度 | 情報源 | 取得内容 |
|--------|--------|----------|
| **1** | `CLAUDE.md` | 技術スタック、制約、ガードレール |
| **2** | `openspec/changes/archive/` | 設計判断（Decisions）、代替案、トレードオフ、変更経緯 |
| **3** | `~/.gstack/projects/{slug}/` | design doc、test plan、review log |
| **4** | `CHANGELOG.md` | 変更履歴のサマリー |
| **5** | `docs/` 配下 | README、ARCHITECTURE、既存ドキュメント |
| **6** | `git log --oneline -50` | コミットの傾向（feat/fix/refactor） |
| **7** | コードの構造 | `package.json`、主要ディレクトリ構成 |

#### Step 2: プロジェクト種別の判定

情報源から自動判定し、ユーザーに確認:
- **MVP積み上げ型**: openspec archive に `mvp*` / `phase*` が多い、feat: コミット主体
- **頻繁改善型**: fix:/chore: コミット主体、インフラ関連ファイルが多い

#### Step 2.5: レイヤー判定

PJ の規模から初期レイヤーを判定する。以下のいずれかに該当すれば L2 を提案:
- ソースファイル数 > 50
- `src/` や `lib/` 配下に 3+ サブディレクトリ
- CLAUDE.md > 100行

デフォルトは L1（安全側）。L2 を検出した場合、ユーザーに確認:
「このプロジェクトは規模的に2層構成（SPEC.md + spec/）が適切です。L2 で生成しますか？」

#### Step 3: SPEC.md の生成

`references/templates.md` から対応するテンプレートを読み、全情報源を統合して埋める。

- **L1 の場合**: SPEC.md を1ファイルで生成（全セクションをインラインに）
- **L2 の場合**: SPEC.md (hot ~60行) + `spec/` ディレクトリを生成。Architecture 詳細等は `spec/architecture.md` に配置し、SPEC.md にはサマリー + ポインタを残す。`references/templates.md` の Layer Split Guide と Cold ファイルテンプレートを参照

各セクションの情報源:
- **Current Capabilities**: openspec archive のタイトルを時系列で機能一覧に変換
- **Architecture**: design.md の Decisions セクション + コード構造から構成
- **Key Design Decisions**: 次の Step 4 で生成する ADR へのリンク

#### Step 4: ADR の自動生成（3層フィルタ）

Claude Code の Glob→Grep→Read 階層戦略と同じ思想で、
コストの低い操作から段階的に絞り込む。Read は最後の最後だけ。

**Layer 1: grep スキャン（数秒、Read なし、LLM 判定なし）**

Bash grep のみで「設計判断を含む design.md」を高速抽出する。

```bash
# 設計判断セクションを含む design.md を抽出（数秒で完了）
find openspec/changes/archive -name "design.md" \
  -exec grep -l "^## Decision\|^# Decision\|^## Risks\|Trade-off\|Approach" {} \;
```

gstack の design doc も同様にスキャン:
```bash
grep -l "Approach\|Decision\|Trade-off" ~/.gstack/projects/*/\*-design-*.md 2>/dev/null
```

git log からも重要な設計変更コミットを抽出:
```bash
git log --oneline --all | grep -i "refactor\|migrate\|architect\|redesign\|breaking"
```

**Layer 2: ヘッダ構造分類（数秒、Read なし、grep 出力のみ）**

Layer 1 の候補に対して、セクションヘッダだけを抽出してアーキテクチャ重要度を自動分類する。

```bash
# 各候補の design.md からセクションヘッダのみ抽出（本文は読まない）
grep "^#" path/to/design.md
```

ディレクトリ名 + セクションヘッダから 3カテゴリに自動分類:

| カテゴリ | 判定基準 | 例 |
|----------|----------|-----|
| **High** (アーキテクチャ) | `world`, `core`, `refactor`, `migrate`, `system`, `foundation`, `phase1` がディレクトリ名に含む。またはヘッダに `Architecture`, `Data Model`, `Store`, `State Management` がある | `add-world-core-shell-phase1` |
| **Medium** (機能設計) | `Decisions` セクションがあるが High に該当しない | `implement-lie-system-foundation` |
| **Low** (UI/修正) | `fix-`, `enhance-`, `polish-`, `cleanup-`, `improve-` で始まる。またはヘッダが `Visual`, `Layout`, `Style` のみ | `fix-toast-stack-management` |

分類結果をユーザーに提示:
```
ADR 候補スキャン完了（{N} 秒）:
  High（アーキテクチャ）: 8 件
  Medium（機能設計）: 15 件
  Low（UI/修正）: 40 件 ← 通常は除外

High の候補:
  1. [x] add-world-core-shell-phase1 — ## Decisions: ストア実装, データ責務分割, UI受け渡し
  2. [x] implement-lie-system-foundation — ## Decisions: 嘘生成アルゴリズム, 信頼度モデル
  ...

High + Medium は全選択します。除外したいものがあれば番号で指定してください。
Low から追加したいものがあれば番号で指定してください。
```

**Layer 3: 選択された候補のみ Read → 並行 ADR 生成**

ユーザーが選んだ候補（5-15件）に対してのみ Read を実行する。

5件以上なら Agent ツールで並行処理:
- 各 Agent が design.md + proposal.md を Read
- ADR ドラフトを生成して `docs/decisions/{NNN}-{slug}.md` に Write

各 ADR は以下から構成:
- **Context**: proposal.md の Problem Statement（あれば）
- **Decision**: design.md の Decisions セクション
- **Alternatives**: design.md の Approaches Considered / Risks / Trade-offs
- **Consequences**: 後続の archive でその判断がどう影響したか（あれば）

gstack の design doc (`~/.gstack/projects/`) に Approaches Considered がある場合も同様に抽出。

**パフォーマンス目安**:
- Layer 1+2: 150件 → 数秒（grep のみ）
- Layer 3: 10件選択 → 並行 Agent で 30-60秒
- 合計: 1分以内（旧方式: 5分以上 or タイムアウト）

#### Step 5: CLAUDE.md 追記 + 完了

CLAUDE.md に以下を追記（まだなければ）:
```markdown
## Specification
- 現在の仕様全体像: [SPEC.md](SPEC.md)
- 詳細仕様: [spec/](spec/)          ← L2 の場合のみ追加
- 設計判断の記録: [docs/decisions/](docs/decisions/)
```

生成した SPEC.md と ADR の数をユーザーに報告する。

### `/spec-keeper update` — SPEC.md の最新化

機能追加・変更後に実行。gstack の `/ship` → `/document-release` 後が最適なタイミング。

#### Step 1: 構造突合（MUST — update の最初に必ず実行）

SPEC.md を Read した後、以下を実行:

1. **レイヤー判定**: `spec/` ディレクトリの存在を確認 → L1 or L2
2. **行数チェック**: SPEC.md の行数を `wc -l` で取得。L2 の場合は spec/ 配下の行数も合計
3. **数値突合（汎用）**: SPEC.md 内の「N個」「N モジュール」等の数値記載を Read で抽出し、対応するディレクトリの `ls` / `find` 結果と比較。PJ固有の数え方はせず、SPEC.md に書かれている数値だけを対象にする
4. **feat+refactor コミット数**: SPEC.md 最終更新以降の変更規模を推定

```bash
# SPEC.md 行数 + spec/ 行数（L2の場合）
echo "spec_md_lines: $(wc -l < SPEC.md | tr -d ' ')"
[ -d spec ] && echo "spec_cold_lines: $(find spec -name '*.md' -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')" || echo "spec_cold_lines: 0"
echo "adr: $(ls docs/decisions/*.md 2>/dev/null | wc -l | tr -d ' ')"
echo "feat_refactor: $(git log --oneline --since="$(git log -1 --format=%ci -- SPEC.md)" --grep="^feat\|^refactor" 2>/dev/null | wc -l | tr -d ' ')"
```

結果を突合表として表示:

```
構造突合結果:
| セクション        | SPEC.md | 実態 | 差分 |
|------------------|---------|------|------|
| hooks/           |       7 |   11 |   +4 |
| skills/          |      20 |   20 |    0 |
| scripts/lib/     |      28 |   28 |    0 |
| fitness/         |       7 |    8 |   +1 |
| docs/decisions/  |      18 |   18 |    0 |
参考: feat+refactor コミット数 = 3
```

判定:
- **数値差分 ≥1** → リカバリーモード（Step R1）へ。差分があるセクションを重点更新対象とする
- **数値差分 0 かつ feat+refactor ≥4** → リカバリーモード（Step R1）へ。コミットに反映漏れがある可能性
- **数値差分 0 かつ feat+refactor 0-3** → 通常更新（Step 2）へ

#### Step 2: 通常更新（乖離度: 通常）

1. 最新の変更を把握:
   - `git log --oneline` で SPEC.md 最終更新以降のコミットを確認
   - `~/.gstack/projects/` の最新 design doc を確認
   - `git diff` で変更されたファイルを確認
2. SPEC.md の該当セクションを Edit で更新:
   - **Current Capabilities** / **System Architecture**: 新機能・変更を反映
   - **Recent Changes**: 変更サマリーを追記（改善型のみ）。**直近5件を超えたら古い項目を CHANGELOG.md へ移動（削除は絶対禁止 — 必ず移動先を先に確保してから SPEC.md を編集すること）**
   - **Key Design Decisions**: 新しい ADR があれば該当カテゴリにリンク追加 + Architecture 本文にインライン参照
   - **Current Limitations**: 解決済みの制限を削除、新たな制限を追加
   - **Next**: 次の計画を更新
3. `Last updated:` の日付を更新
4. **レイヤー健全性チェック（MUST）**: 更新後の行数を確認し、「Progressive Disclosure レイヤー」セクションの閾値表に従って判定:
   - **L1 で SPEC.md > 100行** → L2 昇格を提案。承認されたら「L1 → L2 昇格手順」を即実行
   - **L2 で hot > 80行** → cold 移動候補セクションを提示し、承認で移動実行
   - **L2 の場合**: spec/ ファイルの `Last updated:` も確認し、古い場合は SPEC.md と同時に更新

更新は最小限に — 変更があった箇所だけ編集し、全面書き換えはしない。

#### Step R1: リカバリーモード（乖離度: 中〜大）

通常の差分ベース更新では精度が落ちるため、**セクション単位の突合**に切り替える。

**R1-1: 変更の棚卸し**

feat/refactor コミットを A/B/C に分類してユーザーに提示:

```bash
git log --oneline --since="$(git log -1 --format=%ci -- SPEC.md)" \
  --grep="^feat\|^refactor" --format="%h %s"
```

| カテゴリ | 判定基準 | SPEC.md への影響 |
|---------|---------|----------------|
| **A: Architecture** | 新モジュール、ディレクトリ構造変更、大規模リファクタ | Architecture + API セクション要更新 |
| **B: API/Interface** | 新コマンド、パラメータ変更、新スキル追加 | API/Capabilities セクション要更新 |
| **C: 内部改善** | パフォーマンス、内部リファクタ、バグ修正 | 反映不要（Recent Changes のみ） |

**R1-2: セクション単位の突合と更新**

Step 1 の突合表で **差分があるセクションを優先的に更新** する。一度に全セクションを書き換えず、セクションごとに確認しながら更新する。

差分があるセクションでは、`ls` や `find` の結果と SPEC.md のコンポーネント一覧を目視比較し、**何が増えて何が消えたか**を特定してから Edit する。

| セクション | 突合先 | 数値差分時の確認方法 |
|-----------|--------|-------------------|
| Architecture（hooks） | `ls hooks/*.py` | SPEC.md の hooks 一覧と diff |
| Architecture（scripts/lib） | `ls scripts/lib/*.py` | SPEC.md のモジュール一覧と diff |
| Architecture（fitness） | `ls scripts/rl/fitness/*.py` | SPEC.md の適応度関数一覧と diff |
| API/Interface / Capabilities | `ls -d skills/*/` | SPEC.md のスキルコマンド表と diff |
| Design Decisions | `ls docs/decisions/*.md` | SPEC.md の ADR 件数・リンクと diff |
| Recent Changes | git log | 直近5件に絞る、古い項目は CHANGELOG.md へ移動 |
| Overview | CLAUDE.md | 差分検出不可、意味的に確認 |
| Limitations / Next | コード観察 | 差分検出不可、意味的に確認 |

**R1-3: 未記録の設計判断を ADR に救出（大乖離の場合のみ）**

```bash
git log --since="$(git log -1 --format=%ci -- SPEC.md)" \
  --grep="廃止\|移行\|置換\|replace\|migrate\|deprecate\|breaking" --oneline
```

設計判断を含むコミットが見つかったら、ユーザーに ADR 作成を提案する。

**R1-4: 更新完了**

- `Last updated:` を更新（`(recovery)` を付記: 例 `Last updated: 2026-03-25 by /spec-keeper update (recovery)`）
- 肥大化チェック実行
- 次回からの乖離防止のため、`/spec-keeper update` の実行タイミングをユーザーにリマインド

### `/spec-keeper adr` — ADR の作成

設計判断を記録したい時に使う。

1. 既存 ADR の番号を確認:
   ```bash
   ls docs/decisions/ 2>/dev/null | sort -n | tail -1
   ```
2. 次の番号を採番（3桁ゼロ埋め: 001, 002, ...）
3. ユーザーに以下を確認:
   - 何を決めたか（Decision）
   - なぜその判断に至ったか（Context）
   - 検討した代替案（Alternatives）
4. `references/templates.md` の ADR テンプレートで `docs/decisions/{NNN}-{slug}.md` を生成
5. SPEC.md への反映（ハイブリッドパターン）:
   - **ADR セクション**: 該当カテゴリの行にリンクを追加（カテゴリがなければ新設）
   - **インライン参照**: その判断が Architecture/データフロー等の記述に直接関わる場合、該当箇所に `([ADR-NNN])` を埋め込む。「覆されやすい判断」（技術選定、廃止/移行、構成変更）を優先

`~/.gstack/projects/` に design doc がある場合、Approaches Considered セクションから
Alternatives を自動抽出して ADR のドラフトに含める。

### `/spec-keeper status` — 仕様の鮮度チェック

SPEC.md が古くなっていないか確認する。

1. SPEC.md の `Last updated:` 日付を確認
2. その日付以降のコミット数を数える
3. レイヤー判定（`spec/` の有無）+ 行数チェック
4. レポート:

```
SPEC.md Status:
  レイヤー: L1（SPEC.md のみ） or L2（SPEC.md + spec/）
  SPEC.md: {N}行 [{healthy/caution/action needed}]
  spec/ (cold): {N}ファイル, 計 {N}行     ← L2 のみ
  合計: {N}行
  ADR: {N}件（最新: ADR-{NNN}）
  未反映コミット: {N}件
  判定: 最新 or 更新推奨
  昇格候補: なし or L2昇格推奨（SPEC.md > 100行）
```

健全性判定は「Progressive Disclosure レイヤー」セクションの閾値表に従う。

## ADR 関連付け（ハイブリッドパターン）

SPEC.md と ADR の関連性を AI が効率的に把握できるよう、2層で関連付ける:

1. **インライン参照**: Architecture/データフロー等の本文中に `([ADR-NNN](path))` を埋め込む。対象は「覆されやすい判断」（技術選定、廃止/移行、構成変更）に限定
2. **カテゴリ別サマリー**: Key Design Decisions セクションはドメイン別に1行サマリー化。全件リストは `docs/decisions/` に委譲

これにより AI が Architecture を読んだ時点で「なぜそうなっているか」に辿り着ける。

## gstack との連携

gstack の `/document-release` が完了した後に、以下を提案する:
- SPEC.md の更新が必要そうなら `/spec-keeper update` を提案
- design doc に Approaches Considered がある場合、ADR の作成を提案

## rl-anything との連携（将来）

rl-anything の discover が SPEC.md の鮮度を検出し、更新を提案できるようにする。
evolve パイプラインで SPEC.md の品質チェック（カバレッジ、具体性）を組み込む。
これは Phase 3 として、実運用フィードバック後に検討する。
