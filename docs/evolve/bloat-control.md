# 肥大化制御

skills / rules / memory / CLAUDE.md が際限なく膨張する問題への対策。

## 核心原則

> **「膨張するな」とプロンプトに書いても効かない。**
> 32世代実験で2回失敗。コードで120行制限を強制したら32世代持った。

## アーティファクト別の制約と根拠

| アーティファクト | 制約 | 根拠 |
|-----------------|------|------|
| CLAUDE.md | **200行 / 40,000文字以下** | 公式ドキュメント。超えると性能警告 |
| rules/*.md | **3行以内**（既存ルール） | rules-style.md。抽象化を強制 |
| rules 総数 | **~150ルール以下**（ロード時） | 150超で遵守率が低下する実証データ |
| SKILL.md | **500行以下** | メタデータ30-50トークン、本体はオンデマンド |
| MEMORY.md | **200行（ハードリミット）** | Claude Code ソースで `pZ = 200` としてハードコード |
| memory/*.md | **120行以下** | 32世代実験の安定値 |

## 4つの制御メカニズム

### 1. コードによる構造的制約

evolve / optimize / discover の生成・更新パイプラインで強制:

```python
def validate_artifact(path: str, content: str) -> bool:
    """生成/更新時にサイズをバリデーション"""
    lines = content.strip().split('\n')

    if path.endswith('CLAUDE.md') and len(lines) > 200:
        return False  # 圧縮版を再生成
    if '/rules/' in path and len(lines) > 3:
        return False  # 3行以内に収める
    if 'SKILL.md' in path and len(lines) > 500:
        return False  # 圧縮版を再生成
    if '/memory/' in path and len(lines) > 120:
        return False  # 分割を提案
    return True
```

### 2. Path-scoped rules による遅延ロード

```yaml
---
paths:
  - "src/api/**/*.ts"
---
APIエンドポイントには入力バリデーションを含める
```

`paths` なしの rules は全セッションでロード。
`paths` ありの rules はマッチするファイルを触った時だけロード。

**効果**: ルール総数が多くても、1セッションでロードされる量を制御できる。

### 3. Hot/Cold 分離

```
Hot（毎セッションロード）:
  CLAUDE.md          ← 200行以内
  rules/*.md         ← paths なしのもの
  MEMORY.md          ← 200行以内

Cold（オンデマンドロード）:
  skills/*/SKILL.md  ← トリガーされた時だけ
  rules/*.md         ← paths ありのもの
  memory/*.md        ← 参照された時だけ

Archive（ロードされない）:
  .claude/rl-anything/archive/  ← Prune で退避済み
```

### 4. 自動圧縮トリガー（将来計画 — 部分実装）

> **ステータス**: bloat check レポートは audit スキルで実装済み。自動トリガーによる圧縮提案は将来計画。

| トリガー | アクション | 実装状況 |
|---------|-----------|---------|
| CLAUDE.md > 150行 | evolve で圧縮提案 | audit で検出可能 |
| MEMORY.md > 150行 | トピック別ファイルへの分割提案 | audit で検出可能 |
| rules 総数 > 100 | 重複検出 + 統合提案 | 将来計画 |
| skill 総数 > 30 | 使用頻度分析 + archive 提案 | 将来計画 |

## Global vs Project スコープ

### スコープの階層

```
~/.claude/              ← global（全PJで使う）
  skills/
  rules/
  plugins/
  CLAUDE.md

./.claude/              ← project（このPJだけ）
  skills/
  rules/
  plugins/              ← project-scoped plugin

./CLAUDE.md             ← project
```

### 問題の本質: コンテキストコストではなく evolve の判断精度

スキルは遅延ロードで軽量。global に100個あっても問題ない:

```
セッション開始時: name + description のみ（30-50 tokens/skill）
  → 100 global skills = ~3,000 tokens（コンテキストの1%未満）
タスクマッチ時:   SKILL.md 全文ロード（<5k tokens）
  → 無関係なスキルはロードされない
```

**本当の問題は evolve が正しく判断できないこと**:

| 問題 | 具体例 |
|------|--------|
| Prune の誤判断 | global "figma" スキル → 現PJで0回使用 → 淘汰候補？（他2PJで活発利用中） |
| Optimize のスコープ不足 | global スキルを現PJのデータだけで最適化 → 他PJのユースケースが欠落 |
| Discover の配置迷い | PJ-A で figma パターン検出 → global? project?（PJ-B でも使うか不明） |
| 中間スコープの不在 | global（全100PJ）↔ project（1PJ）→ 2-3PJ共有の置き場がない |

### Claude Code の既存スコープ機構

| 仕組み | 効果 | 限界 |
|--------|------|------|
| `disable-model-invocation: true` | 自動発見を無効化。明示 `/` 呼び出しのみ | 使うPJでも手動呼び出しが必要 |
| Project-scoped plugin | `claude plugin add --project` | PJ数だけ個別にインストール必要 |
| Plugin namespace | `plugin:skill` で衝突回避 | スコープ制御ではない |
| Path-scoped rules | `paths: ["src/api/**"]` | rules のみ。skills には非対応 |
| `extends` (Feature Request [#4800](https://github.com/anthropics/claude-code/issues/4800)) | 設定の継承チェーン | 未実装 |

参考: Cursor は4種のアクティベーション（Always / Intelligently / File Pattern / Manual）を持つ。
Claude Code にないのは「スキルのファイルパターンベースのアクティベーション」。

### evolve の解決策: 3層アプローチ

```
Layer 1: Usage Registry（観測）
  global スキルの使用状況をプロジェクト横断で追跡
  → Prune / Optimize の判断根拠

Layer 2: Scope Advisor（提案）
  使用パターンから最適スコープを提案
  → global ↔ project 移動 / plugin 化

Layer 3: Plugin Bundling（実行）
  関連スキル群を plugin パッケージにグループ化
  → プロジェクト単位でインストール / アンインストール
```

#### Layer 1: Usage Registry

observe hooks がスキル使用を記録するたびに、プロジェクトパスも保存:

```jsonl
// ~/.claude/rl-anything/usage-registry.jsonl
{"skill":"~/.claude/skills/figma-to-code","project":"/path/to/web-app","last_used":"2026-03-01","count":30}
{"skill":"~/.claude/skills/figma-to-code","project":"/path/to/design-system","last_used":"2026-02-28","count":10}
// 他の98PJからのエントリなし → 2/100PJ で使用
```

evolve はこのデータから:
- **Prune**: 「2PJで活発に使用中」→ 淘汰しない
- **Optimize**: 両PJの使用データを考慮して最適化
- **Report**: 使用PJ数と頻度を表示

#### Layer 2: Scope Advisor

`/evolve` 実行時に Scope Advisory をレポートに含める:

```
Scope recommendations:
  ─────────────────────────────────────────
  ~/.claude/skills/figma-to-code:
    Used in: 2/100 projects (web-app, design-system)
    Context cost: 42 tokens/session (low)
    → ✅ Keep as global（コスト低、2PJ間で共有価値あり）

  ~/.claude/skills/legacy-api-client:
    Used in: 0/100 projects
    Last used: 2025-11-15 (105 days ago)
    → ⚠️ Archive candidate（30日以上全PJで未使用）

  ./.claude/skills/prisma-migration:
    Used in: 1/1 projects
    Similar global: ~/.claude/skills/db-migration (78% similar)
    → 💡 Global promotion candidate（統合して global 化の検討を）
  ─────────────────────────────────────────
```

判断基準:

| 状況 | 推奨 |
|------|------|
| global skill: 全PJで0回、30日超 | archive 候補 |
| global skill: 1PJのみで使用 | project 降格を提案 |
| global skill: 2+ PJで使用、コスト低 | global 維持 |
| project skill: 他PJでも使えそう | global 昇格 or plugin 化を提案 |
| 複数 global skills: 常に一緒に使用 | plugin bundle 提案 |

#### Layer 3: Plugin Bundling（将来計画 — 未実装）

> **ステータス**: 将来計画。Layer 1/2 の運用データが十分に蓄積された後に着手予定。

evolve が「常に一緒に使われるスキル群」を検出したら plugin 化を提案:

```
検出: figma-to-code + figma-extract + design-tokens-sync
  → 3つは常に同じPJで使用されている
  → 「figma-toolkit plugin」として bundle 提案

提案される構造:
  ~/.claude/plugins/figma-toolkit/
    plugin.json
    skills/
      figma-to-code/SKILL.md
      figma-extract/SKILL.md
      design-tokens-sync/SKILL.md
    rules/
      figma-naming.md

使うPJでだけインストール:
  cd web-app && claude plugin add figma-toolkit --project
```

### evolve のスコープルール

**デフォルト: project スコープのみ操作**

| 操作 | project | global |
|------|---------|--------|
| Discover（発見） | ✅ 自動 | 提案のみ（人間が判断） |
| Create（生成） | ✅ 自動 | `--scope global` で明示指定 |
| Optimize（最適化） | ✅ 自動 | `--scope global`（Usage Registry 参照） |
| Prune（淘汰） | ✅ 自動 | Usage Registry ベースで安全判断 |
| Audit（健康診断） | ✅ 含む | ✅ 含む（読み取りのみ） |
| Scope Advisory | ✅ 含む | ✅ 含む（Usage Registry ベース） |

### Global 昇格の判断基準

Discover がスキル/ルール候補を見つけた時の分類:

```
「このパターンは全PJで使うか？」

  YES の兆候:
    - git, commit, PR 関連 → global
    - テスト、lint 関連 → おそらく global
    - Claude Code の使い方自体 → global

  NO の兆候:
    - 特定フレームワーク依存 → project
    - ドメイン固有の用語 → project
    - ファイルパスを含む → project

  MAYBE（中間スコープ）:
    - 特定ツール依存（figma, storybook 等） → global + Usage Registry 追跡
    - 特定言語依存（Rust, Go 等） → global（description でフィルタ）
    - チーム固有ワークフロー → plugin 化を提案
```

### Prune の Global 安全設計

Usage Registry を使った安全な淘汰判断:

```
global skill: Usage Registry に他PJの使用記録あり
  → 淘汰しない。Scope Advisory で状況を報告のみ

global skill: Usage Registry で全PJ 0回、30日超
  → archive 候補として提案（人間承認必須）

project skill: 0回使用、30日超
  → 淘汰候補として提案
```

### Global と Project の重複検出

Audit フェーズで検出:

```
Audit report:
  Duplicates (global ↔ project):
    ~/.claude/rules/lint.md ≈ ./.claude/rules/lint-check.md (92% similar)
    → project 側を削除して global に統一しますか？

  Scope mismatches:
    ~/.claude/skills/prisma-helper (global) — used in 1/100 projects only
    → project scope に降格しますか？
```

## 圧縮 vs 分割

> **圧縮（要約）はやらない。分割する。**

根拠: Stanford ACE 研究で、18,282トークンを122トークンに圧縮 →
精度が 66.7% → 57.1% に低下。構造化された分割は +10.6% の改善。

```
✗ CLAUDE.md の内容を要約して短くする
✓ ドメイン別に .claude/rules/ へ分割する
✓ 常時不要な情報は skills/ へ移動する（オンデマンドロード）
✓ 古い memory はトピック別ファイルに退避する
```

## evolve での肥大化チェック

`/evolve` 実行時に自動チェックし、Report に含める:

```
Bloat check:
  CLAUDE.md:  45/200 lines (✅ healthy)
  MEMORY.md: 185/200 lines (⚠️ 93% — split recommended)
  Rules:      11 files, 8 universal + 3 path-scoped (✅ healthy)
  Skills:     23 active (✅ under 30 limit)

  Recommendations:
    1. MEMORY.md: 移動候補 → memory/debugging.md (35 lines)
    2. MEMORY.md: 移動候補 → memory/deploy-patterns.md (28 lines)
       → 移動後 MEMORY.md は 122 lines に
```

## 参考

| ソース | 知見 |
|--------|------|
| [32世代実験](https://dev.to/stefan_nitu/32-more-generations-my-self-evolving-ai-agent-learned-to-delete-its-own-code-18bp) | 120行制限がコード強制で32世代安定 |
| [Claude Code 公式](https://code.claude.com/docs/en/memory) | CLAUDE.md 200行、MEMORY.md 200行ハードリミット |
| [Claude Code Skills](https://code.claude.com/docs/en/skills) | スキル遅延ロード: 30-50 tokens/skill。description ベースの自動マッチ |
| [Claude Code Plugins](https://code.claude.com/docs/en/plugins) | plugin:skill namespace。project-scoped install (`--project`) |
| [GitHub #4800](https://github.com/anthropics/claude-code/issues/4800) | `extends` フィールド提案。ESLint/TSConfig 式の設定継承チェーン |
| [Cursor Rules](https://cursor.com/docs/context/rules) | 4種アクティベーション: Always / Intelligently / File Pattern / Manual |
| [Stanford ACE](https://tylerfolkman.substack.com/p/stop-compressing-context) | 圧縮は精度低下。構造化分割が+10.6% |
| [SpecWeave](https://spec-weave.com/docs/skills/extensible/self-improving-skills/) | maxLearningsPerSession: 10 で流量制限 |
| [Mem0](https://arxiv.org/abs/2504.19413) | 7kトークン平均、90%以上の圧縮率 |
| [claude-self-reflect](https://github.com/ramakay/claude-self-reflect) | 90日半減期の記憶減衰 |
| [GitHub #7336](https://github.com/anthropics/claude-code/issues/7336) | ベースライン108kトークン → 遅延ロードで95%削減 |
| [Skill-Manager Plugin](https://github.com/valllabh/skill-manager) | global skills の enable/disable 切り替え |
