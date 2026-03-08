## Context

Phase 0 で `scripts/rl/fitness/coherence.py` が4軸の構造品質スコアを提供中（`audit --coherence-score` で表示）。hooks が蓄積する5種の JSONL（usage/errors/corrections/sessions/workflows）は discover/audit で部分的に利用されているが、環境の実効性を定量化する統合スコアは存在しない。

既存インフラ:
- `telemetry_query.py`: DuckDB/Python フォールバックの JSONL クエリ層（query_usage/query_errors/query_sessions/query_skill_counts）
- `coherence.py`: 4軸スコア算出 + THRESHOLDS/WEIGHTS パターン
- hooks: usage.jsonl（skill_name, project, timestamp）, errors.jsonl（project, timestamp）, corrections.jsonl, sessions.jsonl（skill_count, error_count）, workflows.jsonl（steps, intent_category）

## Goals / Non-Goals

**Goals:**
- テレメトリデータから環境の実効性を3軸（Utilization/Effectiveness/Implicit Reward）で測定
- LLM コストゼロ（全て既存データの集計のみ）
- coherence.py と同じパターン（THRESHOLDS/WEIGHTS 定数 + score_xxx() 関数群 + compute_xxx_score() 統合）で実装
- データ不足時に安全にフォールバック（data_sufficiency フラグ）
- Coherence + Telemetry をブレンドする environment fitness の提供

**Non-Goals:**
- 新しいデータ収集（hooks 追加・JSONL スキーマ変更）
- Phase 2-3 の LLM ベース評価
- リアルタイム監視・アラート
- corrections.jsonl の高精度パース（簡易的なカウントベースに留める）

## Decisions

### D1: telemetry_query.py への時間範囲クエリ追加

**選択**: 既存の query_xxx() に `since`/`until` パラメータ（ISO 文字列）を追加する。

**理由**: Effectiveness 算出には「直近30日 vs 前30日」の比較が必要。新関数を作るより既存関数を拡張する方が DRY。Python フォールバック・DuckDB 両方で timestamp フィルタを適用する。

**代替案**: 別の query_usage_range() 関数 → 重複が多く保守コスト増。

### D2: スコア算出のアーキテクチャ

**選択**: `scripts/rl/fitness/telemetry.py` に coherence.py と同じパターンで実装。

```
telemetry.py
├── THRESHOLDS (min_sessions, entropy_base, trend_window_days...)
├── WEIGHTS (utilization: 0.30, effectiveness: 0.40, implicit: 0.30)
├── score_utilization(project_dir, days) -> float
├── score_effectiveness(project_dir, days) -> float
├── score_implicit_reward(project_dir, days) -> float
└── compute_telemetry_score(project_dir, days) -> dict
```

**理由**: coherence.py で確立したパターンに従うことで、audit 統合・テストが容易。

### D3: environment_fitness 統合

**選択**: `scripts/rl/fitness/environment.py` で coherence + telemetry をブレンド。

```python
def compute_environment_fitness(project_dir, days=30):
    coherence = compute_coherence_score(project_dir)
    telemetry = compute_telemetry_score(project_dir, days)
    # telemetry データ不足時は coherence のみ
    if not telemetry["data_sufficiency"]:
        return {"overall": coherence["overall"], "sources": ["coherence"]}
    overall = coherence["overall"] * 0.4 + telemetry["overall"] * 0.6
    return {"overall": overall, "sources": ["coherence", "telemetry"]}
```

**理由**: テレメトリが利用可能なら行動実績を重視（0.6）、不足時は構造品質のみに安全にフォールバック。Phase 2-3 追加時もここに統合する設計。

**代替案:**
- **代替 A: 等重み (0.5/0.5)** — シンプルだがテレメトリの情報量を活かせない。構造が整っていても実際に使われていない環境を過大評価するリスク。
- **代替 B: 動的重み（テレメトリデータ量に応じて 0.0〜0.6 をスライド）** — データ量に応じた滑らかな移行が可能だが、閾値設計・テストが複雑化する。
- **採用理由**: Phase 1 では固定重みで十分。行動データが利用可能なら構造よりも実績を重視する設計思想（DX Core 4 の Effectiveness 重視と整合）。動的重みは Phase 2 以降でデータ蓄積量が増えた段階で検討する。

### D4: data_sufficiency 判定

**選択**: 最低30セッション + 最低7日間のデータ幅を要件とする。

**理由**: implementation-plan.md で「最低30セッション」が Phase 0→1 の移行条件として定義済み。7日間は週次パターンを捉えるための最小単位。

### D5: Implicit Reward の簡易実装

**選択**: Phase 1 では Skill 単位の成功率（invoke 後60秒以内に corrections が発生しない = success）のみ。Step-Level Credit Assignment は Phase 2 以降。

**理由**: corrections.jsonl のタイムスタンプ精度と紐付けの難しさから、Phase 1 では過度な精度を求めず proxy 指標に留める。

**補足**: 60秒以内の correction 有無判定では `corrections.session_id == usage.session_id` の一致を要件とする（クロスセッションの誤検出を防止）。

### D6: query_corrections() / query_workflows() の新規追加

**選択**: `telemetry_query.py` に `query_corrections()` と `query_workflows()` を新規追加する。既存パターン（project フィルタ / include_unknown / since / until）に準拠。

**query_corrections() の特記事項**: corrections.jsonl は `project_path`（フルパス）を使用しており、他の JSONL の `project`（末尾名）と異なる。query_corrections() は `project_path` から末尾ディレクトリ名を抽出して `project` パラメータと照合する。

**query_workflows() の特記事項**: workflows.jsonl は `project` フィールドを持たない。Phase 1 では workflows のプロジェクトフィルタをスキップし、全プロジェクト横断で集計する。session_id 経由の join は Phase 2 以降で検討する。

**理由**: telemetry.py の score_effectiveness() は corrections.jsonl と workflows.jsonl を必要とし、score_implicit_reward() も corrections.jsonl を必要とする。telemetry.py 内で直接 `_load_jsonl()` すると DRY 違反になるため、共通クエリ層に追加する。

## Risks / Trade-offs

- [データ偏り] 特定 PJ でのみ hooks が活発 → telemetry_score の PJ 間比較が不公平 → **Mitigation**: スコアは PJ 内の相対トレンドとして解釈、絶対値の PJ 間比較は推奨しない
- [corrections パース精度] corrections.jsonl のフォーマットが曖昧 → **Mitigation**: カウントベースの簡易集計に留め、誤分類は許容。Phase 2 で LLM による高精度分類を検討
- [Shannon entropy の解釈] Skill 数が少ない PJ では entropy が低くなる → **Mitigation**: Skill 数に応じた正規化（entropy / log2(skill_count)）で [0, 1] に正規化
- [テスト可能性] テレメトリデータへの依存 → **Mitigation**: telemetry_query.py のファイルパス注入パターンを活用し、テスト用 JSONL で再現可能に
