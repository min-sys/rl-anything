## Context

Phase 0（Coherence Score）と Phase 1（Telemetry Score）が完了・運用済み。`environment.py` が 2層ブレンド（coherence 0.4 + telemetry 0.6）を実装済み。Phase 2 では LLM コストが発生する Constitutional Evaluation と Chaos Testing を追加する。

既存資産:
- `coherence.py` — 4軸構造品質（Coverage/Consistency/Completeness/Efficiency）
- `telemetry.py` — 3軸行動実績（Utilization/Effectiveness/Implicit Reward）
- `environment.py` — 2層ブレンド + `_load_sibling()` パターン
- `reflect_utils.py` — `find_claude_files()` で CLAUDE.md 発見
- `layer_diagnose.py` — 4レイヤー診断
- `audit` — `--coherence-score`, `--telemetry-score` オプション

## Goals / Non-Goals

**Goals:**
- CLAUDE.md/Rules から PJ 固有の原則を抽出する `principles.py` を実装
- 全レイヤーを原則に照らして LLM Judge で採点する `constitutional.py` を実装
- 構成要素の除去で堅牢性を測る `chaos.py` を実装
- `environment.py` を 3層ブレンド（Coherence + Telemetry + Constitutional）に拡張
- `audit --constitutional-score` で Constitutional Score を表示

**Non-Goals:**
- Chaos Testing の完全自動実行（本 change では手動トリガーのみ）
- Phase 3（Task Exec / Eureka / Elo）の実装
- 原則の自動生成・進化（本 change では抽出+キャッシュのみ）
- pass^k による信頼性測定（Phase 3 の範囲）

## Decisions

### D1: 原則抽出のアプローチ — LLM 半自動抽出 + キャッシュ

**選択**: CLAUDE.md と Rules を入力として LLM に原則リストを抽出させ、`.claude/principles.json` にキャッシュ。ユーザーが編集可能。

**代替案**:
- A) ルールベースの正規表現抽出 → 「〜すべき」「〜してはならない」等のパターンマッチ。精度が低く、暗黙的な原則を見逃す
- B) 完全手動定義 → ユーザー負担が大きく Cold Start が遅い

**理由**: Constitutional AI の知見（<$0.01/判定）から LLM 呼び出し 1回で原則抽出は十分安価。キャッシュにより繰り返しコストを排除。ユーザー編集で精度を担保。

### D2: Constitutional 評価の粒度 — レイヤー単位バッチ

**選択**: レイヤー単位バッチ — 1レイヤーの全原則を1回の LLM call で評価。4レイヤー = 4回の LLM 呼び出し。

**代替案**:
- A) 原則×レイヤーの完全マトリクス（各原則を独立 LLM 呼び出し） → Anthropic "Demystifying Evals" の独立 grader 推奨に合致するが、5原則×4レイヤー=20回は Phase 2 のコスト許容範囲を超える
- B) 全レイヤーを一括で1回の LLM 評価 → コンテキスト長制限リスク、軸ごとの分離が困難

**トレードオフ**: 独立 grader 理想型（A）は精度面で優れるが、Phase 2 ではコスト最小化を優先。SHOULD NOT（非推奨だが許容）として原則×レイヤー個別評価も残し、将来の `--detailed` オプション等で有効化可能にする。

**理由**: 4回の LLM 呼び出しで実用的な精度を確保しつつ、コストを 1/5 に削減。レイヤー内の全原則スコアが1レスポンスで得られるため集計も簡潔。

### D3: LLM 呼び出しの実装 — `claude -p` パイプライン

**選択**: `claude -p "..." --model haiku` で外部プロセスとして LLM 呼び出し。

**代替案**:
- A) Anthropic SDK 直接呼び出し → 依存追加が必要、API キー管理
- B) rl-scorer エージェント流用 → スコアリングの粒度が合わない

**理由**: 既存の rl-anything パターン（LLM 依存を外部プロセスに閉じ込める）と整合。haiku モデルでコスト最小化。失敗時は Constitutional Score なしで environment fitness を算出可能（graceful degradation）。

### D4: Chaos Testing のアプローチ — 仮想除去（ファイルを実際に削除しない）

**選択**: 評価対象レイヤーの内容を「空」として渡して Coherence Score を再計算。実ファイルは変更しない。

**代替案**:
- A) 実ファイルを一時削除して再計測 → 事故リスク、復元漏れ
- B) 完全なタスク実行ベースの ablation → Phase 3 の範囲

**理由**: Phase 2 の Chaos Testing は「構成要素の重要度ランキング」が目的。Coherence Score の入力を仮想的に操作するだけで、各構成要素の ΔScore（除去時のスコア低下量）を安全に算出可能。

### D5: environment.py の 3層ブレンド重み

**選択**: coherence 0.25 + telemetry 0.45 + constitutional 0.30（Constitutional 利用可能時）。Constitutional 不可時は既存の 2層比率を維持。

**理由**: Constitutional は LLM Judge のため Coherence（静的分析）より信頼性が高く重みを大きくする。一方 Telemetry（行動実績）は客観データのため最重要を維持。

### D6: 鶏と卵問題の解決 — 3段階品質保証

**選択**: 低品質な CLAUDE.md から抽出した原則で評価しても無意味な「鶏と卵問題」を、3段階で解決する。

1. **Coherence Coverage ゲート**: `coherence.coverage < 0.5` の場合、Constitutional eval をスキップ（`constitutional_score = None`, `skip_reason = "low_coverage"`）。環境の構造がそもそも不十分な段階では原則ベース評価は時期尚早
2. **シード原則**: LLM 抽出原則に加え、5つの普遍的原則をデフォルト搭載。CLAUDE.md が貧弱でも最低限の評価軸を確保
3. **原則品質スコア**: 抽出後に各原則の specificity（具体性）と testability（検証可能性）を 0.0-1.0 で評価。品質が低い原則（< 0.3）は Constitutional eval から除外

**理由**: Coverage ゲートが「そもそも評価すべきか」を判定し、シード原則が Cold Start を解決し、品質スコアが低品質原則の混入を防ぐ。3段階のフィルタにより、CLAUDE.md の品質に依存しない堅牢な Constitutional eval を実現。

### D7: 評価結果キャッシュ

**選択**: Constitutional eval の結果をレイヤーファイルのコンテンツハッシュと紐づけてキャッシュ。ファイル変更なしの場合は LLM を呼ばずキャッシュを返却。

**理由**: 連続した audit 実行や、変更のないレイヤーの再評価を避けることで LLM コストを大幅削減。原則キャッシュ（D1）と組み合わせることで、変更がない環境では LLM コストゼロで Constitutional Score を返却可能。

## Configuration Pattern

既存パターン踏襲: 全閾値・重みはモジュールレベル `THRESHOLDS` / `WEIGHTS` dict で管理する。

```python
# principles.py
THRESHOLDS = {
    "min_coverage_for_eval": 0.5,    # Coherence Coverage ゲート
    "min_principle_quality": 0.3,     # 原則品質スコアの下限
}

# constitutional.py
WEIGHTS = {
    # レイヤー単位の評価結果から全体スコアを算出する重み
}
THRESHOLDS = {
    "cache_ttl_hours": 24,           # 評価結果キャッシュの TTL
}

# chaos.py
THRESHOLDS = {
    "critical_delta": 0.10,          # ΔScore >= 0.10 → critical
    "spof_delta": 0.15,              # ΔScore >= 0.15 → SPOF WARNING
    "low_delta": 0.02,               # ΔScore < 0.02 → low（prune 候補）
}
```

## Risks / Trade-offs

- **[LLM コスト増]** → Mitigation: haiku モデル使用、原則キャッシュ、評価結果キャッシュ（D7）、`--constitutional-score` オプトイン制（デフォルトでは実行しない）
- **[LLM 採点の不安定さ]** → Mitigation: 原則を具体的に記述（「LLMコールを最小化」→「Skill 内で claude -p を使用してはならない」レベル）、複数回評価の平均化は Phase 3 で検討
- **[原則の粒度問題]** → Mitigation: 抽出後の `.claude/principles.json` をユーザーが編集可能にし、粗すぎ/細かすぎを人間が調整
- **[鶏と卵問題]** → Mitigation: D6 の3段階品質保証（Coverage ゲート + シード原則 + 品質スコア）
- **[Chaos Testing の限界]** → Mitigation: Phase 2 では Coherence ベースの仮想除去のみ。タスク実行ベースの ablation は Phase 3
- **[claude -p 依存]** → Mitigation: LLM 呼び出し失敗時は Constitutional Score を None として environment fitness に含めない（graceful degradation）

## Open Questions

- **LLM temperature 制御**: `claude -p` は temperature パラメータ未サポート（2026-03-09 確認済み）。Constitutional eval の再現性は `--model haiku` + 具体的プロンプトで担保する。将来 `claude -p` に temperature オプションが追加された場合は低 temperature（0.0-0.1）を採用する
