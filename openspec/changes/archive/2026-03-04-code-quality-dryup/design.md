## Context

fix-merge-false-positives レビュー中に発見された4件のコード品質問題。いずれも DRY 違反・スタブ残留であり、既存の動作を変えない純粋リファクタリング。

現状:
- `_check_line_limit()` + 行数定数が optimize.py / run-loop.py / discover.py の3箇所に重複
- `jaccard_coefficient()` / `tokenize()` が enrich.py にローカル定義。`scripts/lib/similarity.py` に TF-IDF は共通化済みだが Jaccard は未統合
- `generate_adversarial_candidates()` が名前と実態の不一致（静的テンプレートを返すだけ）
- `fitness-template.py` の `evaluate()` がスタブのまま黙って 0.5 を返す

## Goals / Non-Goals

**Goals:**
- 重複コードを Single Source of Truth に統合し保守性を向上
- スタブ実装の黙った成功を排除し、問題を早期検出可能にする
- 関数名と実態の不一致を解消

**Non-Goals:**
- 新機能の追加（純粋リファクタリングのみ）
- TF-IDF と Jaccard の統合 API 設計（将来課題）
- discover.py の行数チェックロジック追加（定数のみ共通化）

## Decisions

### D1: 行数制限の共通モジュール配置先

**決定**: `scripts/lib/line_limit.py`

**理由**: `scripts/lib/` は既に `similarity.py`, `semantic_detector.py` など共通ライブラリの配置場所。`scripts/rl/` は workflow_analysis 等の別目的ディレクトリ。

**代替案**:
- `scripts/rl/line_limit.py` — proposal.md の記載だが、`scripts/lib/` の方がプロジェクト規約に合致

### D2: Jaccard 関数の配置先

**決定**: 既存の `scripts/lib/similarity.py` に `tokenize()` と `jaccard_coefficient()` を追加

**理由**: 同ファイルに TF-IDF 類似度が既にあり、類似度計算の Single Source of Truth として統合するのが自然。別ファイルにすると類似度関連の分散が増える。

**代替案**:
- `scripts/rl/similarity.py` (新規) — proposal.md の記載だが、`scripts/lib/similarity.py` が既に存在するため重複を生む
- `scripts/lib/jaccard.py` (新規) — 粒度が細かすぎる

### D3: `generate_adversarial_candidates()` の改善方法

**決定**: `get_adversarial_templates()` にリネーム + docstring を「テンプレート辞書の提供」に修正

**理由**: 関数は静的テンプレートを返す役割であり、`generate` は動的生成を示唆して誤解を招く。`get_*_templates` なら意図が明確。

**代替案**:
- 関数削除 — 呼び出し元 `evolve_fitness()` が利用しているため削除不可
- 動的生成の実装 — スコープ外（Non-Goals）

### D4: fitness-template.py のスタブ検出方法

**決定**: `evaluate()` で `scores` が空の場合に stderr へ警告出力し `0.0` を返す（0.5 フォールバック削除）

**理由**: 0.5 は「普通」を意味し未実装を隠蔽する。0.0 なら明らかに異常値として検出可能。stderr 警告でユーザーに実装漏れを通知。

**代替案**:
- 例外送出 — fitness 関数はパイプラインの一部で例外は中断を意味するため過剰
- 0.5 のまま警告のみ — スコア値で未実装を区別できない

### D5: `_check_line_limit()` のインターフェース統一

**決定**: モジュールレベル関数 `check_line_limit(target_path: str, content: str) -> bool` として統一。超過時は stderr に警告出力。

**理由**: run-loop.py の関数シグネチャ（パス + コンテンツ受け取り、警告出力あり）が最も汎用的。optimize.py のインスタンスメソッド版はクラス内で薄いラッパーとして呼び出し可。

## Risks / Trade-offs

- **import パス変更によるテスト失敗** → 既存テスト（test_enrich.py 等）の import を更新。CI で検証
- **discover.py の定数のみ共通化** → `_check_line_limit()` 関数は discover.py では未使用のため定数 import のみ。将来的に必要になれば関数も利用可能
- **fitness-template.py は generate-fitness がコピーして使うテンプレート** → テンプレート自体の変更は即座に既存の生成済みファイルには影響しない（新規生成分から適用）
