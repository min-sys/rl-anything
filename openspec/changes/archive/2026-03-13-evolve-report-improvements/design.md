## Context

evolve パイプラインは Diagnose→Compile→Housekeeping の3ステージで環境改善を行う。現在の課題:

1. **トレンド不在**: 対策済み表示はあるが前回比が見えず、改善効果を判断できない
2. **auto_fixable が狭い**: line_limit 軽微違反・reference type 未設定が手動止まり
3. **fitness evolution コールドスタート**: MIN_DATA_COUNT=30 に到達できず機能不全
4. **目標値不明**: Bash 割合の閾値がレポートに表示されない

既存コード:
- `remediation.py`: classify_issue (confidence × scope) → FIX_DISPATCH/VERIFY_DISPATCH
- `fitness_evolution.py`: MIN_DATA_COUNT=30 で insufficient_data 返却
- `tool_usage_analyzer.py`: BASH_RATIO_THRESHOLD=0.40 定義済みだがレポート未表示
- `evolve-state.json`: evolve 状態永続化（trigger_summary, calibration_history 等）
- `frontmatter.py`: `parse_frontmatter()` で YAML frontmatter パース（read-only）

## Goals / Non-Goals

**Goals:**
- evolve レポートに対策効果のトレンド（前回比）を表示
- remediation の auto_fixable 範囲を拡張（line_limit 1行超過、reference type 未設定）
- fitness evolution に bootstrap モード追加（5件以上で簡易分析）
- Bash 割合に目標閾値を併記

**Non-Goals:**
- グラフ・チャート描画（テキストレポートの範囲内）
- BASH_RATIO_THRESHOLD 自体の変更（既存値 0.40 を維持）
- reference type の判定ロジック変更（audit の detect_untagged_reference_candidates をそのまま利用）

## Decisions

### D1: トレンドデータの保存場所 → evolve-state.json

**選択**: 既存の evolve-state.json に `tool_usage_snapshot` フィールドを追加
**理由**: evolve 状態は既に evolve-state.json に集約されている（trigger_summary, calibration_history 等）。新規ファイル不要で後方互換も容易（フィールド無し = 初回扱い）
**代替案**: 別ファイル（tool-usage-history.jsonl）→ ファイル増加、既存パターンと不整合

### D2: line_limit fix のアプローチ → LLM 1パス圧縮

**選択**: 対象ルールファイルを読み込み、LLM に「行数制限内に圧縮」を指示する 1パスアプローチ
**理由**: ルールは自然言語であり、機械的な行削除では意味が壊れる。optimize と同じ LLM パッチパターンを再利用
**LLM 呼び出し方法**: `scripts/rl/fitness/constitutional.py` の `_call_llm()` と同様に、`subprocess.run(["claude", "--print", "-p", prompt])` で Claude CLI を呼び出す。入力はルールファイル全文 + 行数制限、出力は圧縮後の全文
**フォールバック**: LLM 呼び出しが失敗（タイムアウト・非ゼロ終了）した場合、fix をスキップし category を `proposable` に降格する。エラーは `record_outcome()` に `error` フィールドとして記録
**コストガード**: dry-run 時は fix を実行しない（既存の `execute_fixes(dry_run=True)` が fix 関数を呼ばない動作を維持）
**代替案**: 行末結合・空行削除 → 意味が壊れるリスク、空行がない場合に対応不可

### D3: reference type fix → frontmatter 操作のみ

**選択**: SKILL.md の frontmatter に `type: reference` を追加するだけの最小限操作
**理由**: audit の detect_untagged_reference_candidates が既に候補を絞り込んでいる。判定ロジックの重複を避け、fix は「付与」のみに集中
**実装**: `scripts/lib/frontmatter.py` に `update_frontmatter()` 関数を追加。既存の `parse_frontmatter()` のパースロジックを再利用し、frontmatter の更新・書き戻しを行う。frontmatter 無しの場合は先頭に追加
**失敗ハンドリング**: YAML パースエラー → fix スキップ + エラー記録、空ファイル → `fixed=False` 返却

### D4: bootstrap モードの閾値 → BOOTSTRAP_MIN=5

**選択**: 5件以上で簡易分析（承認率・平均スコア・スコア分布）を実行
**理由**: 5件あれば基本統計に最低限の意味がある。相関分析は30件で維持（統計的に有意な相関には必要）
**信頼性の前提**: 5件の基本統計は信頼区間が広いため、レポートに「簡易分析モード」と明記し完全分析との区別を明確化。段階的な信頼度向上（5→10→20→30件）はユーザーに示さない（複雑化を避ける）
**出力**: `status: "bootstrap"` + 簡易統計。evolve レポートでは「簡易分析モード (N/30件)」表示

### D5: threshold 表示 → SKILL.md テンプレート更新

**選択**: evolve SKILL.md の Step 10.2 テンプレートに閾値表示を追加
**理由**: tool_usage_analyzer.py の定数は既に export 済み。レポートテンプレート側の変更のみで完結
**表示形式**: `Bash 割合: 45.4% (目標: ≤40%) — 未達` のように、実績値・目標値・達成/未達を併記。ratio 型指標はパーセントポイント差も表示: `45.4% → 38.2% (↓7.2pp)`

## Risks / Trade-offs

- **[LLM 依存]** line_limit fix が LLM を使うため、dry-run 時に実コスト発生 → **Mitigation**: dry-run では fix 実行しない（既存動作と同じ）。LLM 失敗時は proposable に降格し、エラーを記録
- **[reference type 誤付与]** audit の候補判定が誤っている場合、不要な type: reference が付く → **Mitigation**: VERIFY_DISPATCH で frontmatter 確認 + ユーザー承認フロー（auto_fixable でも確認表示）
- **[bootstrap 統計の信頼性]** 5件では統計的に弱い → **Mitigation**: レポートに「簡易分析」と明記し、完全分析との区別を明確化
- **[YAML パースエラー]** frontmatter の書式が不正な場合 → **Mitigation**: fix スキップ + エラー記録で安全にフォールバック
