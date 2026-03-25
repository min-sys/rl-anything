# ADR-006: Constitutional Eval LLM Judge

Date: 2026-03-09
Status: Accepted

## Context

Phase 0（Coherence Score）と Phase 1（Telemetry Score）は LLM コストゼロで環境の構造品質と行動実績を測定するが、「PJ の価値観・原則に沿っているか」という質的評価ができなかった。例えば「LLM コール最小化」「べき等性保証」といった PJ 固有の原則を全レイヤーが遵守しているかは、静的分析やテレメトリでは判定できなかった。

## Decision

- **原則抽出は LLM 半自動抽出 + キャッシュ**: CLAUDE.md と Rules を入力として LLM に原則リストを抽出させ、`.claude/principles.json` にキャッシュ。ユーザーが編集可能。ルールベースの正規表現抽出は精度が低く暗黙的な原則を見逃すため不採用
- **Constitutional 評価はレイヤー単位バッチ**: 1レイヤーの全原則を1回の LLM call で評価。4レイヤー = 4回の LLM 呼び出し。原則xレイヤーの完全マトリクス（20回）はコスト許容範囲を超えるため不採用
- **LLM 呼び出しは `claude -p` パイプライン**: haiku モデルでコスト最小化。Anthropic SDK 直接呼び出しは依存追加と API キー管理が必要なため不採用。失敗時は graceful degradation
- **Chaos Testing は仮想除去**: 評価対象レイヤーの内容を「空」として渡して Coherence Score を再計算。実ファイルは変更しない。各構成要素の Delta Score（除去時のスコア低下量）を安全に算出
- **environment.py は3層ブレンド**: coherence 0.25 + telemetry 0.45 + constitutional 0.30。Constitutional 不可時は既存の2層比率を維持
- **鶏と卵問題の3段階解決**: (1) Coherence Coverage < 0.5 で Constitutional eval をスキップ、(2) 5つの普遍的シード原則をデフォルト搭載、(3) 抽出原則の品質スコア < 0.3 を除外
- **評価結果キャッシュ**: レイヤーファイルのコンテンツハッシュと紐づけてキャッシュ。ファイル変更なしの場合は LLM を呼ばずキャッシュ返却

## Alternatives Considered

- **ルールベースの正規表現で原則抽出**: 「~すべき」「~してはならない」等のパターンマッチは精度が低く、暗黙的な原則を見逃す
- **完全手動の原則定義**: ユーザー負担が大きく Cold Start が遅い
- **原則xレイヤーの完全マトリクス評価（各原則を独立 LLM 呼び出し）**: 5原則x4レイヤー=20回はコスト許容範囲を超える。将来の `--detailed` オプションで有効化可能にする余地は残す
- **Anthropic SDK 直接呼び出し**: 依存追加と API キー管理が必要
- **実ファイル削除による Chaos Testing**: 事故リスクと復元漏れがある。仮想除去で十分
- **等重みの3層ブレンド**: Telemetry（客観データ）が最重要であり、Constitutional は Coherence（静的分析）より信頼性が高い

LLM コスト増はhaiku モデル・原則キャッシュ・評価結果キャッシュ・オプトイン制で軽減する。LLM 採点の不安定さは原則を具体的に記述して対処する。`claude -p` の temperature 制御は未サポートのため、具体的プロンプト + haiku モデルで再現性を担保する。

## Consequences

**良い影響:**
- PJ 固有の価値観・原則への遵守度を定量評価可能になった
- 3層ブレンドにより構造品質・行動実績・原則遵守の3観点で環境品質を総合評価可能に
- 鶏と卵問題の3段階解決により、環境の成熟度に関わらず安全に評価を開始可能
- 仮想除去による Chaos Testing で構成要素の重要度ランキングと SPOF 検出が可能に
- キャッシュ戦略により、変更がない環境では LLM コストゼロで Constitutional Score を返却

**悪い影響:**
- Phase 0-1 と異なり LLM コストが発生する（原則抽出1回 + 評価最大4回）
- LLM Judge の採点には不安定さがあり、同一入力でもスコアにばらつきが出る可能性がある
- Chaos Testing は Coherence ベースの仮想除去のみで、タスク実行ベースの ablation は Phase 3 に先送り
