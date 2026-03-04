## Context

rl-anything v0.12.0 に対する ambiguous-intent-resolver / updater-senior-engineer の2エージェントレビューで5つの優先改善項目が特定された。

現状の課題:
- `scripts/` 直下と `skills/*/scripts/` に同名ファイルが5組存在（discover, evolve, audit, aggregate_runs, fitness_evolution）。テストで `importlib` workaround が必要
- README の evolve フロー記述が古い（3フェーズ記述だが実装は7フェーズ）
- corrections の偽陽性を報告する手段がない
- LLM に渡す corrections データにサニタイズがない
- corrections.jsonl のファイルパーミッションが未設定

## Goals / Non-Goals

**Goals:**
- scripts/ 二重管理を解消し、skills/*/scripts/ に一本化
- README.md の evolve フロー・チュートリアルを実装に同期
- corrections 偽陽性のフィードバック機構を追加
- LLM 入力サニタイズ方針を実装
- corrections.jsonl のパーミッションを 600 に設定

**Non-Goals:**
- GeneticOptimizer の責務分割（別 change で対応）
- rl-loop の claude CLI 出力依存問題（別 change で対応）
- Individual.id の UUID 化（別 change で対応）
- マルチユーザー・マルチプロジェクトのデータ分離改善

## Decisions

### D1: scripts/ 二重管理の解消方針

**決定**: `scripts/` 直下の重複ファイルを削除し、`skills/*/scripts/` に一本化する。テストの import パスを修正する。

**理由**: `skills/*/scripts/` 側が最新（argparse 追加、ad-hoc フィルタ等）であり、`scripts/` 直下は旧版。一本化先は skills/ が妥当。

**代替案**: symlink で繋ぐ → Plugin インストール時に壊れやすい。却下。

### D2: 偽陽性フィードバックの保存形式

**決定**: `~/.claude/rl-anything/false_positives.jsonl` に JSONL 形式で保存。`detect_correction()` で読み込んでフィルタリングする。

**理由**: 既存の JSONL パターン（corrections.jsonl, usage.jsonl）と一貫性がある。起動時に全件ロードは避け、reflect 実行時に参照する設計。

**代替案**: common.py の `FALSE_POSITIVE_FILTERS` にハードコードで追加 → ユーザー固有のパターンに対応できない。却下。

### D3: LLM 入力サニタイズの範囲

**決定**: `semantic_detector.py` の `ANALYSIS_PROMPT` に渡す corrections データに対して、message フィールドを最大500文字に切り詰め、制御文字を除去する。プロンプトインジェクション対策として XML タグの除去を追加。

**理由**: 完全なサニタイズは不可能だが、攻撃面を減らすことに意味がある。既存の `should_include_message()` フィルタを強化する形で実装。

**代替案**: システムプロンプトで「ユーザー入力のタグを無視せよ」と制御 → LLM の挙動依存で保証不可。却下。

### D4: ファイルパーミッション設定の実装箇所

**決定**: `ensure_data_dir()` でディレクトリを `700`、`append_jsonl()` で新規ファイル作成時に `600` を設定。

**理由**: 既存の一元管理ポイント（common.py）に集約でき、全 hooks/scripts に自動適用される。

**代替案**: 各 hook で個別に chmod を呼び出す → 設定漏れリスクが高い。却下。

### D5: README evolve フローの更新方針

**決定**: 現行の「3つの柱」表はそのまま維持し、evolve フローの詳細セクションを実装に合わせて7フェーズに更新。Before/After チュートリアルセクションを追加。

**理由**: 「日次 evolve だけでいい」のメッセージは維持しつつ、実態との乖離を解消する。

**代替案**: README を自動生成する → 手動記述の方が品質担保しやすい。却下。

## Risks / Trade-offs

- [偽陽性 JSONL 肥大化] → `reflect` 実行時にのみ読み込み、一定期間後に古いエントリを自動削除
- [サニタイズによる正当な corrections の欠損] → 切り詰めのみで内容は保持、制御文字除去は安全
- [scripts/ 削除による外部参照の破壊] → テスト・SKILL.md 内の参照を全て更新。CHANGELOG に破壊的変更として記載
