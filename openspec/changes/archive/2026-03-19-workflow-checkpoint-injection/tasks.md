Related: #34

## 1. コアモジュール作成

- [x] 1.1 `scripts/lib/workflow_checkpoint.py` を作成し、`is_workflow_skill(skill_dir)` を実装（frontmatter `type: workflow` 優先 + ヒューリスティクスフォールバック: 基準A+B両方成立 or 基準A+5項目以上で True）
- [x] 1.2 テスト `scripts/tests/test_workflow_checkpoint.py` を作成し、`is_workflow_skill()` のテストを記述（frontmatter判定/ヒューリスティクス判定/非ワークフローの判定）
- [x] 1.3 `CHECKPOINT_CATALOG` を定義（4カテゴリ: infra_deploy, data_migration, external_api, secret_rotation。各エントリに id, category, description, detection_fn, applicability, template）。`_CHECKPOINT_DETECTION_DISPATCH` dict で detection_fn を解決
- [x] 1.4 `get_checkpoint_template(category)` を実装
- [x] 1.5 テスト: `CHECKPOINT_CATALOG` の構造検証と `get_checkpoint_template()` のテスト

## 2. チェックポイントギャップ検出

- [x] 2.1 `detect_checkpoint_gaps(skill_name, skill_dir, project_dir)` を実装（corrections/errors から `last_skill` フィルタで照合、SKILL.md 既存チェック確認、MIN_CHECKPOINT_EVIDENCE=2 閾値、CHECKPOINT_DETECTION_TIMEOUT_SECONDS=5 タイムアウト保護）
- [x] 2.2 confidence スコア計算を実装（BASE_CHECKPOINT_CONFIDENCE=0.5 + min(evidence_count * EVIDENCE_BONUS_PER_COUNT=0.05, MAX_EVIDENCE_BONUS=0.25) + GATE_BONUS=0.1）
- [x] 2.3 applicability gate 統合（infra_deploy → `detect_iac_project()`, data_migration → DB ファイル存在チェック: prisma/schema.prisma, alembic/, migrations/, knex, typeorm, drizzle）
- [x] 2.4 テスト: ギャップ検出のシナリオテスト（ギャップあり/なし/既存チェックあり/evidence不足/テレメトリ不在/タイムアウト）

## 3. evolve-skill 統合

- [x] 3.1 `skill_evolve.py` の `assess_single_skill()` に `workflow_checkpoints` フィールドを追加（`is_workflow_skill()` → True 時のみ `detect_checkpoint_gaps()` 実行）
- [x] 3.2 テスト: ワークフロースキルの assessment に `workflow_checkpoints` が含まれることを検証
- [x] 3.3 `evolve-skill/SKILL.md` のステップにチェックポイント提案表示を追加（Step 3 の assessment 結果表示にチェックポイント情報を含める）

## 4. discover 統合

- [x] 4.1 `discover.py` の `run_discover()` にワークフロースキル走査 + `detect_checkpoint_gaps()` 呼び出しを追加、結果を `workflow_checkpoint_gaps` フィールドに格納
- [x] 4.2 テスト: `run_discover()` の結果に `workflow_checkpoint_gaps` が含まれることを検証

## 5. remediation 統合

- [x] 5.1 `issue_schema.py` に `WORKFLOW_CHECKPOINT_CANDIDATE` 定数 + `make_workflow_checkpoint_issue()` factory 関数を追加
- [x] 5.2 `remediation.py` に `fix_workflow_checkpoint()` + `_verify_workflow_checkpoint()` を追加し、FIX_DISPATCH / VERIFY_DISPATCH に登録
- [x] 5.3 `remediation.py` の `compute_confidence_score()` に WORKFLOW_CHECKPOINT_CANDIDATE の confidence マッピングを追加
- [x] 5.4 テスト: issue 生成→分類→fix→verify のフロー検証

## 6. evolve パイプライン統合

- [x] 6.1 `evolve.py` の Diagnose ステージに workflow_checkpoint_gaps 統合（discover 結果 → issue_schema 変換 → remediation 連携）
- [x] 6.2 evolve レポートに「Workflow Checkpoint Gaps」セクション追加
- [x] 6.3 結合テスト: evolve 全体パイプラインでチェックポイント提案が表示されることを検証
