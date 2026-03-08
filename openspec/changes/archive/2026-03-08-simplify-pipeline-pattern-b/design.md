## Context

現在の evolve パイプラインは8ステージ（Observe → Discover → Enrich → Optimize → Reorganize → Prune → Reflect → Report）で構成されている。#21 の調査で、enrich が 164 LOC の薄いラッパー、reorganize と prune がマージ候補を二重検出、regression gate が optimize.py にハードコードされている等の問題が判明した。

Pattern B（Observe → Diagnose → Compile）への移行により、機能を失わずにパイプラインを3ステージに簡素化する。これは後続 Phase（全層 Diagnose / 全層 Compile / 自己進化）の土台となる。

### 現在のデータフロー

```
observe hooks → JSONL files
  → discover (パターン検出, LLM)
  → enrich (Jaccard照合, LLMゼロ)
  → optimize (パッチ生成, LLM)
  → reorganize (TF-IDF クラスタ, LLMゼロ)
  → prune (重複+マージ, LLM)
  → remediation (audit違反修正, LLM)
  → reflect (メモリルーティング, LLM)
  → report
```

## Goals / Non-Goals

**Goals:**

- 8ステージ → 3ステージ（Observe → Diagnose → Compile）に統合
- enrich を discover に統合し独立スキルを廃止
- マージ候補検出を prune に一元化（reorganize は split 検出のみに縮小）
- regression gate を共通ライブラリに抽出
- evolve オーケストレーターを3ステージ呼び出しに書き換え
- 既存の全テストが通ること

**Non-Goals:**

- 全層 Diagnose の実装（Phase 2 で対応）
- 全層 Compile の実装（Phase 3 で対応）
- 自己進化機能の実装（Phase 4 で対応）
- スキルの新規追加や機能拡張
- LLM コストの削減（今回は構造の簡素化のみ）
- discover のパターン検出ロジック変更（enrich 統合と session-scan 削除のみ）

## Decisions

### D1: enrich を discover の後処理フィルタに統合

**決定**: enrich.py の Jaccard 類似度マッチングを discover.py の出力パイプラインに組み込む。独立スキルとしての enrich は廃止。

**理由**: enrich は 164 LOC の薄いラッパーで、discover の出力に Jaccard 係数を付与するだけ。独立スキルとしての存在意義が薄い。

**代替案**: enrich を残しつつ evolve から直接呼ばない → 将来の混乱を招くため却下

**実装**:
- `discover.py` に `_enrich_patterns()` 関数を追加
- `scripts/lib/similarity.py` の `jaccard_coefficient` を使用（enrich spec 準拠）
- discover の出力 JSON に `matched_skills` と `unmatched_patterns` を追加
- enrich の SKILL.md は残すが `deprecated: true` を frontmatter に追加

### D2: マージ候補検出を prune に一元化

**決定**: reorganize からマージ候補検出（TF-IDF + 階層クラスタリング）を削除し、prune の semantic similarity ベースの検出に一元化。reorganize は split 検出（300行超）のみに縮小。

**理由**: reorganize と prune が同じ「マージ候補」を別アルゴリズムで検出し、evolve が重複排除している。prune の方が similarity_threshold パラメータがあり柔軟。

**代替案**: reorganize のクラスタリングを prune に移植 → 複雑化するため却下。prune の既存 semantic similarity で十分。

**実装**:
- `reorganize.py` から `merge_groups` 生成ロジックを削除
- `reorganize.py` の出力から `merge_groups` フィールドを除去（`split_candidates` のみ残す）
- `prune.py` は変更なし（既にマージ候補検出を実装済み）
- reorganize は prune の optional pre-step として位置づけ（split 検出 → prune に渡す）

### D3: regression gate を共通ライブラリに抽出

**決定**: `scripts/lib/regression_gate.py` を新設し、optimize.py と rl-loop から参照する。

**理由**: 現在 optimize.py 内にハードコードされた gate ルールが、rl-loop でも別途実装されている。Phase 3 で全層 Compile を実装する際にもこの gate が必要になるため、先行して共通化する。

**インターフェース**:
```python
# scripts/lib/regression_gate.py
def check_gates(
    candidate: str,
    original: str | None = None,
    max_lines: int,  # 必須。呼び出し側が line_limit.py の MAX_SKILL_LINES/MAX_RULE_LINES を参照して渡す
    pitfall_patterns_path: str | None = None,  # references/pitfalls.md から動的にロード
) -> GateResult:
    """全ゲートチェックを実行し結果を返す。pitfall patterns は指定時に references/pitfalls.md から動的にロードする。"""

@dataclass
class GateResult:
    passed: bool
    reason: str | None  # 不合格理由 (e.g., "empty_content", "forbidden_pattern_TODO", "pitfall_pattern({pattern})")
```

**注**: `GateResult` にスコアフィールドは含めない。gate は合否判定のみを担い、スコアリングは呼び出し側（optimize.py 等）の責務とする。

### D4: evolve オーケストレーターを3ステージに再構成

**決定**: evolve の SKILL.md を3ステージ構成に書き換える。

**新しいフロー**:
```
evolve
├─ Step 1: Diagnose
│   ├─ discover (パターン検出 + enrich 統合済み)
│   ├─ audit 問題検出（collect_issues）
│   └─ reorganize (split 検出のみ)
│
├─ Step 2: Compile
│   ├─ optimize (corrections → パッチ, gate は lib/ 参照)
│   ├─ remediation (audit 違反の自動修正)
│   └─ reflect (corrections → メモリルーティング)
│
├─ Step 3: Housekeeping
│   ├─ prune (ゼロ使用アーカイブ + マージ提案)
│   └─ evolve-fitness (30+ サンプル時のみ)
│
└─ Report
```

**理由**: 8ステージの順序依存を明確な3グループに整理。各グループ内は順序依存があるが、グループ間は概念的に独立。

### D5: session-scan の削除

**決定**: discover.py 内の session-scan（テキストレベルパターンマイニング）を削除。

**理由**: ~50 LOC。テキストマイニングはノイズが多く、usage.jsonl ベースのパターン検出で十分カバーされている。

**代替案**: session-scan を optional flag (`--with-session-scan`) として残す → 使用実績がなくコード複雑化するため却下

### D6: backfill のパイプライン外への再分類

**決定**: backfill は evolve パイプラインから分離し、セットアップコマンドとして位置づける。SKILL.md の description を更新。

**理由**: 実行頻度が1-2回で、日常的な evolve パイプラインの一部ではない。

**代替案**: backfill を evolve の初回実行時に自動呼び出し → セットアップは明示的に行うべきため却下

## 設定値の扱い

| 設定値 | 定義場所 | 方針 |
|--------|----------|------|
| FORBIDDEN_PATTERNS | `regression_gate.py` 内の定数 | 設定ファイル化は Non-Goal。コード内定数として維持 |
| Jaccard 閾値 (0.15) | `discover.py` 内の定数 `JACCARD_THRESHOLD` | コード内定数として定義 |
| max_lines | `line_limit.py` の既存定数 `MAX_SKILL_LINES`(500) / `MAX_RULE_LINES`(3) | 既存定数を参照。`check_gates()` の呼び出し側が明示的に渡す |
| pitfall patterns | `references/pitfalls.md` | 動的ロード（既存パス維持） |
| SPLIT_LINE_THRESHOLD (300) | `reorganize.py` 内の定数 | コード内定数として維持 |

## Risks / Trade-offs

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| enrich 統合で discover.py が肥大化 | 中 | `_enrich_patterns()` を独立関数として分離。164 LOC 増に留まる |
| reorganize のマージ検出削除で精度低下 | 低 | prune の semantic similarity が同等以上の精度。TF-IDF クラスタリングは追加的な価値が限定的 |
| regression gate 抽出で既存テストが壊れる | 低 | import パスの変更のみ。gate ロジック自体は不変 |
| evolve SKILL.md の全面書き換えでプロンプト品質低下 | 中 | 既存のステップを論理グループに再編するだけで、個々のステップの記述は維持 |

## Migration Plan

1. **regression gate 抽出** → テスト通過確認
2. **enrich → discover 統合** → テスト通過確認
3. **discover の session-scan 削除** → テスト通過確認
4. **reorganize のマージ検出削除** → テスト通過確認
5. **evolve SKILL.md を3ステージに書き換え** → 手動での evolve 実行テスト
6. **backfill の再分類** → ドキュメント更新

各ステップは独立してコミット可能。問題が発生した場合は個別にリバート可能。
