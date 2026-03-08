Related: #21

## Context

evolve パイプラインの Diagnose ステージは現在 Skill レイヤーのみを診断対象としている:
- **discover**: usage.jsonl ベースのパターン検出（error/rejection/behavior）+ Jaccard 照合
- **audit collect_issues()**: 行数超過、陳腐化参照（Memory のみ）、重複候補、ハードコード値（Skill/Rules）
- **reorganize**: TF-IDF + クラスタリングによる split 検出

coherence.py（Gap 1 Phase 0）が Coverage/Consistency/Completeness/Efficiency の 4 軸でレイヤー横断的な静的分析を行っているが、診断結果（具体的な問題リスト）としては出力されておらず、evolve の remediation パイプラインに流れていない。

## Goals / Non-Goals

**Goals:**
- Rules / Memory / Hooks / CLAUDE.md の 4 レイヤーに診断ロジックを追加し、collect_issues() の統一フォーマットで問題を出力する
- coherence.py の詳細チェック結果を診断モジュールから再利用し、重複実装を避ける
- evolve.py の Diagnose ステージに全レイヤー診断を統合し、Compile ステージ（remediation）に渡す
- remediation.py が新レイヤーの issue type を分類・処理できるようにする

**Non-Goals:**
- 全レイヤーの **Compile**（パッチ自動生成）は Gap 2 Phase 3 の scope — 本 change では診断 + 問題リスト出力まで
- Subagents レイヤーの診断（観測データが不十分なため後回し）
- テレメトリベースの診断（Gap 1 Phase 1 の scope）— 本 change は静的分析のみ
- corrections.jsonl ベースのルール改善（reflect の scope）

## Decisions

### D1: レイヤー別診断モジュールを scripts/lib/ に配置する

**決定**: 各レイヤーの診断ロジックを `scripts/lib/layer_diagnose.py` に統合モジュールとして実装する。

**代替案**: レイヤーごとに独立ファイル（rules_diagnose.py, memory_diagnose.py 等）→ 却下。各診断関数は 30-80 行程度の見込みで、ファイル分割のオーバーヘッドが利点を上回る。

**理由**: 共通の issue フォーマット（`{"type", "file", "detail", "source"}`）を1ファイルで一貫管理でき、共通ユーティリティ（パス解決、レイヤー検出）も共有できる。

### D2: coherence.py の詳細チェック結果をアダプターパターンで再利用する

**決定**: coherence.py の `compute_coherence_score()` を呼び出し、返却される details dict（`orphan_rules`, `skill_existence.missing`, `memory_paths.stale`, `rule_compliance.issues`, `claude_md_size` 等）を layer_diagnose.py 内のアダプター関数で issue フォーマットに変換する。coherence.py 自体は変更しない。

**代替案**: coherence.py の `_check_*()` 内部関数を抽出して共有 → 却下。内部関数の抽出はリグレッションリスクを増やし、coherence.py のテスト維持コストが上がる。

**理由**: coherence.py の score_*() は既に details dict で十分な情報を返しており、アダプターで変換するだけで診断結果として利用できる。責務の分離も維持される。

### D3: issue type の命名規則

**決定**: 既存の issue type（`line_limit_violation`, `stale_ref`, `duplicate`, `hardcoded_value`, `near_limit`）に加え、レイヤープレフィックス付きの新 type を追加する:
- Rules: `orphan_rule`（スキルから参照されない孤立ルール）, `rule_conflict`（矛盾するルール）, `stale_rule`（参照先が存在しないルール）
- Memory: `stale_memory`（陳腐化エントリ）, `memory_duplicate`（重複セクション）
- Hooks: `hooks_unconfigured`（hooks 設定なし）
- CLAUDE.md: `claudemd_phantom_ref`（言及された Skill/Rule が存在しない）

**理由**: 既存の `stale_ref` 等と衝突せず、remediation.py で issue type ベースの分岐が明確になる。

### D4: collect_issues() を拡張する（新関数ではなく）

**決定**: 既存の `audit.collect_issues()` に新レイヤーの診断呼び出しを追加する。

**代替案**: 新たに `collect_all_issues()` を作成 → 却下。evolve.py は既に `collect_issues()` を呼んでおり、呼び出し元の変更が不要になる。

**理由**: 後方互換性を維持しつつ診断範囲を拡大できる。返り値フォーマットは同一。

### D5: hooks の診断は settings.json の設定存在チェックのみ

**決定**: Hooks の診断は `.claude/settings.json` の hooks 設定存在チェックのみとする。テレメトリベース診断（エラー率、未使用検出）は将来の change で対応する。

**代替案**: errors.jsonl / usage.jsonl の hook 関連レコードを突合してエラー率・未使用検出 → 却下。errors.jsonl には hook イベント名（PreToolUse 等）が記録されておらず、`tool_name` のみ。sessions.jsonl にも hook 実行記録なし。spec 通りの実装は不可能。

**理由**: 観測データが不足しており、テレメトリベース診断の信頼性が担保できない。データ拡充後に別 change として対応する。

## Risks / Trade-offs

- **[Risk] collect_issues() の肥大化** → layer_diagnose.py に実装を委譲し、collect_issues() は呼び出しのみ（1レイヤーあたり 3-5 行）
- **[Risk] 偽陽性（orphan_rule 等で実際は使われているルールを誤検出）** → confidence_score を低め（0.4-0.6）に設定し、proposable/manual_required に分類される設計
- **[Trade-off] Subagents レイヤーを除外** → 観測データが不十分で信頼性のある診断ができないため、テレメトリ蓄積後に Phase 3 以降で対応
