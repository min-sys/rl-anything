## Context

evolve の remediation フェーズで検出される issue の大半が false positive（#23）。4パターンの誤検出が毎回再発し、パイプラインの信頼性を低下させている。

現状の検出ロジック:
- `_extract_paths_outside_codeblocks()`: 正規表現ベースのパス抽出。KNOWN_DIR_PREFIXES で2セグメントパスをフィルタするが、数値パターン（`429/500`）、相対パスのファイル位置基準解決、外部リポジトリ参照には未対応
- `diagnose_rules()`: CLAUDE.md/SKILL.md 内での言及有無で orphan 判定。`.claude/rules/` が Claude の auto-load 対象であることを考慮していない
- `diagnose_claudemd()`: `^#{1,3}\s+[Ss]kills?\b` の厳密マッチ。`## Key Skills` 等の prefix 付き見出しに非対応
- `line_limit`: ルール vs スキルの2分類のみ。CLAUDE.md に MEMORY.md と同じ200行制限、global/project rule の区別なし

## Goals / Non-Goals

**Goals:**
- 4パターンの false positive を解消し、evolve の検出精度を向上
- 既存の true positive 検出を維持（regression なし）
- 各修正の影響範囲を最小限に抑える

**Non-Goals:**
- 検出ロジック全体のリアーキテクチャ
- stale_ref の false negative（検出漏れ）の改善
- remediation エンジン自体の変更

## Decisions

### D1: 数値パターン除外 — 正規表現後フィルタ

`_extract_paths_outside_codeblocks()` のパス候補取得後に、全セグメントが数字のみで構成されるパスを除外する。HTTP ステータスコード（`429/500/503`）やバージョン表記（`1.0/2.1`）の FP を解消。

代替案: 正規表現自体を変更 → 複雑化するため後フィルタが保守しやすい

### D2: ファイル位置基準の相対パス解決

`_check_stale_refs()`（audit.py の stale_ref）および `diagnose_rules()`（layer_diagnose.py の stale_rule）で参照パスを判定する際、プロジェクトルート基準で `Path.exists()` が失敗した場合、参照元ファイルの親ディレクトリ基準でも解決を試みる。スキル内の `references/docs-map.md` 等がスキルディレクトリからの相対パスとして正しい場合に FP を回避。

適用対象:
- `_check_stale_refs()` (audit.py): stale_ref 検出
- `diagnose_rules()` (layer_diagnose.py): stale_rule 検出（同じ FP パターンが発生するため）

### D3: 外部リポジトリ参照・スペック名の除外

パス候補のうち、以下を追加除外:
- プロジェクトルートに存在せず、かつ MEMORY.md / CLAUDE.md のメモ・説明文脈にある参照（既に stale_ref 判定は Path.exists() で行うため、D2 で多くが解決）
- パス候補の最初のセグメント（トップレベルディレクトリ）がプロジェクトルートに存在しないディレクトリであり、かつ KNOWN_DIR_PREFIXES にも含まれない場合、stale_ref 候補から除外。`src/github/token.ts` 等の外部リポジトリ参照に限らず、あらゆる不在トップレベルディレクトリへの参照を一般的に除外

### D4: orphan_rule issue type の廃止

`.claude/rules/` ディレクトリは Claude が自動読み込みするため、現行の `diagnose_rules()` がスキャンする全ルールが auto-load 対象。orphan_rule 判定は事実上 dead code となっている。

方針: orphan_rule issue type を廃止する。`diagnose_rules()` から orphan_rule 検出ロジックを削除し、`coherence.py:score_efficiency()` の orphan_rules カウントも廃止する。

将来対応: telemetry ベースの `unused_rule`（呼び出し実績なし）検出に移行。roadmap.md に記載。

代替案: auto-load 除外ロジックを追加して存続 → 全ルールが auto-load 対象の現状では検出結果が常に空になるため不採用

### D5: セクション名マッチングの柔軟化

正規表現を `^#{1,3}\s+.*[Ss]kills?\b` に変更し、`## Key Skills`、`## Available Skills`、`## Project Skills` 等にもマッチ。日本語パターンも同様に `.*スキル` に拡張。

代替案: セクション名の正規化辞書 → 網羅性の担保が困難なため正規表現拡張が適切

### D6: ファイル種別ごとの段階的行数制限

| ファイル種別 | 現行制限 | 新制限 | 根拠 |
|-------------|---------|--------|------|
| CLAUDE.md | 200 | 制限なし（audit 警告のみ） | PJ の CLAUDE.md は構造的に長くなる |
| MEMORY.md | 200 | 200（変更なし） | auto-memory の context window 制約 |
| global rule | 3 | 3（変更なし） | 簡潔さの原則 |
| project rule | 3 | 5 | PJ 固有ルールは若干の余裕が必要 |
| SKILL.md | 500 | 500（変更なし） | 十分 |

`line_limit.py` に `MAX_PROJECT_RULE_LINES = 5` を追加。`check_line_limit()` にグローバル/プロジェクト区別のためのパス判定ロジックを追加。audit.py の LIMITS dict も対応。

判定アルゴリズム: `str(Path.home())` がパスに含まれれば global rule、それ以外は project rule として判定。

warning 閾値: `CLAUDEMD_WARNING_LINES = 300` を定数として定義。CLAUDE.md が300行を超える場合、audit で warning レベルの通知を出力する（violation ではない）。

## Risks / Trade-offs

- [D4: orphan_rule 廃止で不要ルール検出手段がなくなる] → telemetry ベースの unused_rule に将来移行（roadmap.md 参照）。現時点では許容
- [D5: 正規表現の過度な柔軟化で意図しないセクションにマッチ] → `\b` ワードバウンダリで「Skillset」等との誤マッチを防止
- [D6: CLAUDE.md の制限撤廃で肥大化を見逃す] → audit で warning レベルの通知は維持（制限ではなく推奨として）
