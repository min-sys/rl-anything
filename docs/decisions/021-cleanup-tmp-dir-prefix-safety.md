# ADR-021: Cleanup スキルの tmp_dir prefix を rl-anything 名前空間に限定する

Date: 2026-04-22
Status: Accepted
Related: Issue #69（cleanup スキル新設）、PR #70、Issue #71（userConfig 化 follow-up）

## Context

Issue #69 の機能提案に応じて `/rl-anything:cleanup` を新設した。初版では PR マージ・デプロイ後に残る 6 種類の痕跡（マージ済みローカルブランチ、remote refs、一時 worktree、一時ディレクトリ、close 候補 Issue、PR Test plan 残件）をまとめて候補提示 → 個別承認 → 実行する設計とした。

カテゴリ 4（一時ディレクトリ削除）の初版プロトタイプは、`scripts/lib/cleanup_scanner.py::scan_tmp_dirs` のデフォルト prefix として以下を採用していた:

```
claude-, gstack-, rl-anything-
```

PR #70 内で dogfood したところ、実環境のスキャン結果に以下が含まれることが判明した:

- `/tmp/claude-501` — Claude Code ランタイム（UID 付きソケット/PID ディレクトリ）
- `/tmp/claude-mcp-browser-bridge-<user>` — 実行中の MCP server bridge
- `/tmp/gstack-work` — gstack の永続作業ディレクトリ

ユーザーが個別承認 UI で誤って "Yes" を押すと、**現在動いている Claude Code セッションが即死する**危険がある。AskUserQuestion による個別承認で最終防御はあるものの、初版の爆発半径設計が広すぎた。

## Decision

**初版 SKILL.md のデフォルト prefix を `rl-anything-` のみに narrow する。加えて scanner 側に `_DEFAULT_TMP_EXCLUDE_PATTERNS` を追加し、`claude-<digits>` と `claude-mcp-*` を恒久的に除外する defense-in-depth を入れる。**

具体的には以下を実施:

1. `skills/cleanup/SKILL.md` のデフォルト呼び出しを `scan_tmp_dirs(prefixes=["rl-anything-"])` に変更。カテゴリ 4 冒頭で「`claude-` / `gstack-` は衝突領域のため default 対象外」と根拠を明示
2. `scripts/lib/cleanup_scanner.py` に `_DEFAULT_TMP_EXCLUDE_PATTERNS = (r"^claude-\d+$", r"^claude-mcp-.*")` を追加
3. `scan_tmp_dirs` に `exclude_patterns: Optional[Iterable[str]] = None` を追加。`None` 時はデフォルト安全網を適用、`[]` を明示すれば無効化可能（逃げ道は残す）
4. テスト 4 件追加（UID 付き除外 / MCP 除外 / カスタム exclude / 空 list override）
5. CHANGELOG の `[Fixed]` セクションに経緯を記録
6. prefix 拡張（`claude-sandbox-*` や `gstack-scratch-*` 等の安全な spilled-over 名前空間を扱いたいケース）は Issue #71 で userConfig 化を追跡する

## Alternatives

### (A) wide prefix を維持し、exclude pattern のみで守る

`claude-` / `gstack-` をデフォルトに含めたまま、`_DEFAULT_TMP_EXCLUDE_PATTERNS` のブラックリストで危険なものを除外する案。

- **Pros**: Claude Code が将来同じ UID prefix で別 purpose の tmp dir を作った時に機能を維持できる
- **Cons**: ブラックリストは網羅性担保が難しく、未知の Claude/gstack tmp dir が増えるたびに exclude pattern 追加が必要。「allow-by-default + deny-list」は爆発半径設計として安全性が低い

### (B) 最初から userConfig 化する

初版から `cleanup_tmp_prefixes` を `manifest.json` の userConfig に切り出し、デフォルトは空 list にする案。

- **Pros**: 柔軟性と安全性を両立できる
- **Cons**: 初版スコープが膨らみ、Issue #69 の意図（まず使える後片付けスキルを出す）と乖離。userConfig 周りは他の `userConfig`（auto_trigger 等）とのコンフリクト検討も必要。初版はシンプルに名前空間を絞るだけで十分と判断

### (C) カテゴリ 4 を初版で無効化

一時ディレクトリ削除機能自体を Phase 2 に繰り下げ、初版はカテゴリ 1-3, 5-6 のみを対象にする案。

- **Pros**: 危険領域をそもそも触らない
- **Cons**: Issue #69 の要件 4 を意図的に落とすことになり、「後片付けの空白地帯を埋める」という提案の趣旨に反する。narrow prefix で rl-anything 名前空間だけでも機能として価値がある

## Consequences

### Positive

- 初版 cleanup スキルの爆発半径が rl-anything 自身が生成する tmp dir のみに限定される
- ユーザーが userConfig などで `claude-` prefix を後から追加した場合でも、scanner 側の `_DEFAULT_TMP_EXCLUDE_PATTERNS` が UID dir と MCP bridge を守る二重防御になる
- dogfood で即座に検出できた例として、新規スキル出荷時の「同 PR 内 dogfood」プラクティスの価値を再確認

### Negative

- 初版では `claude-sandbox-*` 等の Claude Code が便利に掃除してほしい tmp dir を掃除できない（明示的に userConfig で prefix を追加するまでは）
- userConfig 化（#71）の設計と実装が未了のため、prefix 拡張には当面 scanner への直接引数渡しが必要

### Neutral

- `exclude_patterns` パラメータは逃げ道として `[]` 指定で無効化可能。スクリプト経由で rl-anything の bench テンポラリを掃除する等の ad hoc ユースは維持できる

## References

- Issue #69: `[Feedback] 機能提案: 後片付け（cleanup）スキルの新設`
- Issue #71: `[Feedback] 機能提案: /rl-anything:cleanup の tmp dir prefix を userConfig 化 + 危険 pattern の exclude 安全ネット`
- PR #70: `feat(cleanup): add /rl-anything:cleanup skill for post-deploy tidy-up`
- 実装: `scripts/lib/cleanup_scanner.py`, `skills/cleanup/SKILL.md`
- テスト: `scripts/tests/test_cleanup_scanner.py::test_scan_tmp_dirs_default_excludes_*`
