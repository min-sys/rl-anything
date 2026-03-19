Closes: #31

## Context

Claude Code の `.claude/rules/` ファイルは YAML frontmatter に `paths` を指定することで、特定ファイル編集時のみルールをロードできる。rl-anything はルール生成（reflect）・最適化（optimize）・自動修正（remediation）を行うが、`paths` frontmatter の提案は行っていない。

また、現在の行数チェック（`line_limit.py` の `check_line_limit()` / `suggest_separation()`、`audit.py` の `check_line_limits()`）は `content.count("\n") + 1` で全体行数を数えており、frontmatter 行も含まれる。`paths` 等の frontmatter を追加すると本文3行でも全体7-8行になり、制限超過と判定される矛盾がある。

## Goals / Non-Goals

**Goals:**
- `frontmatter.py` にコンテンツ行数（frontmatter 除外）取得関数を追加し、Single Source of Truth とする
- `line_limit.py` と `audit.py` の行数カウントを frontmatter 除外に統一
- ルール生成・最適化時に `paths` frontmatter を提案する仕組みを提供する
- 既存の `paths` frontmatter を持つルールの行数チェックが正しく動作することを保証する

**Non-Goals:**
- `paths` frontmatter の自動書き込み（提案のみ、適用はユーザー判断）
- スキルファイル（SKILL.md）の frontmatter 行数除外（スキルは frontmatter が本質的に内容の一部）
- `description` frontmatter の自動提案（別スコープ）

## Decisions

### D1: コンテンツ行数取得関数の配置場所

**決定**: `frontmatter.py` に `count_content_lines(filepath_or_content)` を追加する

**理由**: frontmatter のパース責務はすでに `frontmatter.py` にある。行数取得もここに置くことで frontmatter 区切り検出ロジックの重複を防ぐ。`line_limit.py` は `frontmatter.py` を import して使う。

**代替案**: `line_limit.py` 内に実装 → frontmatter パースロジックの重複が発生するため却下。

### D2: 行数除外の対象

**決定**: `.claude/rules/` 配下のファイルのみ frontmatter 除外カウントを適用する。スキルファイルは全体行数のまま。

**理由**: ルールは「3行以内」という厳しい制約があり frontmatter による圧迫が問題になる。スキルは500行上限で frontmatter 数行は誤差の範囲。スキルの frontmatter は `description` 等が実質的にスキル定義の一部でもある。CLAUDE.md files do not use YAML frontmatter and are unaffected by this change.

### D3: `count_content_lines()` のシグネチャ

**決定**: `count_content_lines(content: str) -> int` とし、文字列を受け取る。ファイルI/Oは呼び出し元の責務。

**理由**: `check_line_limit()` は既に `content: str` を受け取っている。同じインターフェースで統一。`audit.py` の `check_line_limits()` はファイル読み取り後に渡す。

### D4: `paths` 提案のトリガー条件

**決定**: `reflect_utils.py` に `suggest_paths_frontmatter(message: str, project_root: Path) -> Optional[List[str]]` を追加。correction テキストからファイルパスパターン（拡張子、ディレクトリ名）を抽出し、特定ファイルタイプに限定可能と判断した場合にグロブパターンのリストを返す。

**パターン検出の方法**:
1. `audit.py` の `_extract_paths_outside_codeblocks()` を `scripts/lib/path_extractor.py` に共有モジュール化して再利用する。独自のパス抽出ロジックは実装しない
2. 抽出したパスから共通のディレクトリプレフィックスやファイル拡張子をグロブパターンに変換
3. 例: `hooks/common.py` と `hooks/save_state.py` → `hooks/**/*.py`

**理由**: 既存の `suggest_claude_file()` がルーティング先を決定した後に、そのルールに `paths` を付与すべきかを判断するステップとして自然に統合できる。

### D5: `paths` 提案の表示タイミング

**決定**: reflect / optimize / remediation の各出力で「`paths` frontmatter 提案」セクションとして表示する。自動適用はしない。

**理由**: `paths` の適用はコンテキストノイズ削減に有効だが、誤った `paths` はルールが意図した場面で発火しなくなるリスクがある。ユーザー確認を必須とする。

### D6: `paths` vs `globs` キーの扱い

**決定**: 提案時は `paths:` をデフォルトとする（公式ドキュメント記載のため）。ただし提案メッセージに「CC バージョンによっては `globs:` の方が信頼性が高い場合あり」の注記を含める。`detect_dead_globs()` と paths 関連コードは `paths` / `globs` 両キーを処理する。

**背景**: Claude Code の `paths:` frontmatter には既知の信頼性問題がある（#13905, #16299, #17204, #21858, #23478）。`globs:` が代替として存在する。

**代替案**:
- `globs:` のみ → 非公式のため却下
- CC バージョン自動検出 → 過剰な複雑性のため却下

## Risks / Trade-offs

- **[Risk] frontmatter 除外で既存テストの期待値が変わる** → frontmatter 付きのテストケースを追加し、frontmatter なしの既存テストは影響なし（frontmatter なしの場合は全体行数 = コンテンツ行数）
- **[Risk] `paths` 提案の精度が低い場合、ノイズになる** → confidence 閾値を設け、明確なパターンがある場合のみ提案する。提案は表示のみで自動適用しない
- **[Risk] `audit.py` の `check_line_limits()` と `line_limit.py` の `check_line_limit()` で行数カウント方法が乖離する** → 両方とも `count_content_lines()` を使うよう統一
- **[Risk] 行数カウント変更により remediation-outcomes.jsonl の過去データと不連続が生じうる** → trend 分析への影響は軽微（frontmatter 付きルールの割合が小さいため）
