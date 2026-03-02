## 1. スキル基盤

- [x] 1.1 `skills/generate-fitness/` ディレクトリ構成を作成（SKILL.md, scripts/, templates/）
- [x] 1.2 SKILL.md を作成（frontmatter + `/generate-fitness` トリガー定義 + 実行手順）

## 2. プロジェクト分析（project-analyzer）

- [x] 2.1 `scripts/analyze-project.py` を作成: CLAUDE.md・rules・skills の自動検出と読み込み
- [x] 2.2 ドメイン推定ロジックを実装: キーワード頻度分析で game/documentation/bot/general を判定
- [x] 2.3 keywords 抽出: CLAUDE.md・rules・skills からキーワード頻度分析を実装
- [x] 2.4 criteria 構築: ドメインに応じた品質軸・重み・アンチパターン定義を実装
- [x] 2.5 JSON 出力統合: keywords + criteria をJSON形式で統合出力するロジックを実装
- [x] 2.6 pitfalls.md 検出: `.claude/skills/*/references/pitfalls.md` の存在確認と内容パース → anti_patterns へのマージを実装
- [x] 2.7 analyze-project.py のテストを作成（各ドメインのサンプル CLAUDE.md でテスト、pitfalls.md あり/なしの両ケース含む）

## 3. fitness 関数生成（fitness-generator）

- [x] 3.1 `templates/fitness-template.py` を作成: evaluate関数・main関数のスケルトン
- [x] 3.2 SKILL.md に生成フロー指示を記述: analyze-project.py 実行 → JSON取得 → Claude CLI でテンプレート穴埋め → ファイル出力
- [x] 3.3 既存ファイルの .backup リネーム処理の手順を SKILL.md に記述
- [x] 3.4 生成先ディレクトリ（`scripts/rl/fitness/`）の自動作成手順を SKILL.md に記述

## 4. 統合テスト

- [x] 4.1 dry-run テスト: analyze-project.py を rl-anything 自身に実行して JSON 出力を確認
- [ ] 4.2 生成テスト: atlas-breeaders 相当のサンプル CLAUDE.md で fitness 関数を生成し、インターフェース準拠を確認（スキップ: Claude CLI の実行環境制約）
- [ ] 4.3 既存 `--fitness` オプションとの互換確認: 生成された関数を optimize.py から呼び出せることを確認（スキップ: Claude CLI の実行環境制約）
