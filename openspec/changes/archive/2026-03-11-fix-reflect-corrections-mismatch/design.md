Closes: #25

## Context

evolve の discover フェーズは `corrections.jsonl` を全件カウント（`reflect_data_count`）するが、reflect は semantic validation → is_learning フィルタを経て処理件数を決定する。LLM の `claude -p` 呼び出しで件数不一致が発生すると、`semantic_analyze()` が全件を `is_learning=False` にフォールバックし、後続の `is_learning` フィルタで全件除外される。

既存 spec（reflect spec.md）では「JSON parse failure / count mismatch 時は regex 検出結果をフォールバック」と規定されているが、実装がこの spec に準拠していない。

## Goals / Non-Goals

**Goals:**
- semantic validation の件数不一致フォールバックを spec 準拠に修正（regex フォールバック = `is_learning=True` 保持）
- evolve の `reflect_data_count` を pending フィルタ適用後のカウントに修正し、evolve と reflect の認識を一致させる
- フォールバック時に `is_learning` を保持し、全件除外を防止する

**Non-Goals:**
- semantic validation の LLM プロンプト改善（件数不一致の根本原因対策は別タスク）
- reflect の confidence フィルタや project フィルタの変更

## Decisions

### Decision 1: フォールバック時の `is_learning` デフォルト値を `True` にする

**選択**: `semantic_analyze()` の件数不一致フォールバックで `is_learning=True` を返す
**理由**: 既存 spec が「regex 検出結果をフォールバックとして使用」と規定しており、corrections.jsonl に記録された時点で regex パターンマッチ済み。`is_learning=False` は「学習ではない」と確定した場合のみ使うべき。
**代替案**: フォールバック時に `is_learning` フィールドを付与しない → `c.get("is_learning", True)` のデフォルトで True になるが、明示的に True にする方が意図が明確。

### Decision 2: evolve の reflect_data_count に pending フィルタを適用

**選択**: `load_claude_reflect_data()` に `reflect_status == "pending"` フィルタを追加
**理由**: reflect が処理するのは pending のみ。evolve のレポートが「7件ある」と言っても reflect で 0 件（applied/skipped 含む）では混乱する。
**代替案**: evolve 側で pending/total 両方表示 → 複雑化するだけでメリット少ない。

### Decision 3: `validate_corrections` の partial success 対応

**選択**: LLM が返した結果の件数が入力より少ない場合、マッチした分だけ適用し、残りは `is_learning=True` でパススルー
**理由**: 7件中5件だけ LLM が返した場合、全件を捨てるのは過剰。成功分は活用し、失敗分は安全側（regex 結果尊重 = True）に倒す。

## Risks / Trade-offs

- [偽陽性通過リスク] フォールバックで `is_learning=True` にすると、本来除外すべき偽陽性が通過する可能性がある → **緩和策**: reflect の対話レビューで人間がスキップ可能。`--skip-semantic` と実質同等の挙動で安全
- [evolve カウント変更] `reflect_data_count` が減少するため、トリガー閾値（`pending_count >= 5`）に影響する → **緩和策**: 実態を反映した正しいカウントなので、むしろ望ましい変更
