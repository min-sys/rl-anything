Related: #21

## Why

現在の evolve パイプラインの Diagnose ステージは **Skill レイヤーのみ** を診断対象としている（discover: usage.jsonl ベースのパターン検出、audit: collect_issues による構造問題検出、reorganize: split 検出）。roadmap の As-is 表が示す通り、Rules / Memory / Hooks / CLAUDE.md の 4 レイヤーは観測データは一部あるが診断メカニズムが不在で、問題（陳腐化、矛盾、肥大化、未使用）が検出されないまま蓄積する。Gap 2 Phase 2 として、Diagnose を全レイヤーに拡張し、後続の Compile ステージ（Gap 2 Phase 3）で全レイヤーのパッチを生成する基盤を作る。

## What Changes

- **Diagnose ステージにレイヤー別診断モジュールを追加**: Rules / Memory / Hooks / CLAUDE.md の 4 レイヤーそれぞれに専用の診断ロジックを実装し、Skill 診断と統一フォーマットで問題リストを出力する
- **audit の collect_issues() を拡張**: 現在は Skill + Memory のみ対象の collect_issues() に Rules / Hooks / CLAUDE.md の診断を追加する
- **evolve.py の Diagnose ステージに統合**: 新しいレイヤー別診断結果を evolve.py の phases に統合し、Compile ステージ（remediation）に渡す
- **remediation.py の対応レイヤー拡張**: 新しい issue type（rule_*, hook_*, claudemd_*）を分類・修正できるようにする
- **coherence.py の診断結果との統合**: Coherence Score の各軸で検出した詳細を診断結果として活用する

## Capabilities

### New Capabilities
- `rules-diagnose`: Rules レイヤーの診断（孤立ルール検出、矛盾検出、陳腐化検出）
- `memory-diagnose`: Memory レイヤーの診断（陳腐化エントリ検出、重複セクション検出、参照整合性チェック）
- `hooks-diagnose`: Hooks レイヤーの診断（settings.json の hooks 設定存在チェック）
- `claudemd-diagnose`: CLAUDE.md レイヤーの診断（セクション整合性チェック、言及されたスキル/ルールの実在確認）

### Modified Capabilities
- `diagnose-stage`: 既存の Skill 中心 Diagnose にレイヤー別診断結果を統合する
- `remediation-engine`: 新しいレイヤー由来の issue type を分類・処理できるようにする

## Impact

- **scripts/lib/layer_diagnose.py**: レイヤー別診断モジュール（diagnose_rules / diagnose_memory / diagnose_hooks / diagnose_claudemd を統合）。coherence.py の `compute_coherence_score()` 結果を issue フォーマットに変換するアダプター関数を含む
- **skills/audit/scripts/audit.py**: collect_issues() の拡張、find_artifacts() の Hooks / CLAUDE.md 対応
- **skills/evolve/scripts/evolve.py**: Diagnose ステージの出力にレイヤー別診断結果を追加
- **skills/evolve/scripts/remediation.py**: 新 issue type の confidence_score / rationale 追加
- **skills/evolve/SKILL.md**: Diagnose ステージの手順にレイヤー別診断の表示・対話フローを追加
