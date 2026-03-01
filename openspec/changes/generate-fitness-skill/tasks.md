## 1. スキル基盤

- [ ] 1.1 `skills/generate-fitness/` ディレクトリ構成を作成（SKILL.md, scripts/, templates/）
- [ ] 1.2 SKILL.md を作成（frontmatter + `/generate-fitness` トリガー定義 + 実行手順）

## 2. プロジェクト分析（project-analyzer）

- [ ] 2.1 `scripts/analyze-project.py` を作成: CLAUDE.md・rules・skills の自動検出と読み込み
- [ ] 2.2 ドメイン推定ロジックを実装: キーワード頻度分析で game/documentation/bot/general を判定
- [ ] 2.3 品質基準（criteria）抽出ロジックを実装: rules/skills の内容から評価軸・weight・keywords・anti_patterns をJSON出力
- [ ] 2.4 analyze-project.py のテストを作成（各ドメインのサンプル CLAUDE.md でテスト）

## 3. fitness 関数生成（fitness-generator）

- [ ] 3.1 `templates/fitness-template.py` を作成: evaluate関数・main関数のスケルトン
- [ ] 3.2 SKILL.md に生成フロー指示を記述: analyze-project.py 実行 → JSON取得 → Claude CLI でテンプレート穴埋め → ファイル出力
- [ ] 3.3 既存ファイルの .backup リネーム処理の手順を SKILL.md に記述
- [ ] 3.4 生成先ディレクトリ（`scripts/rl/fitness/`）の自動作成手順を SKILL.md に記述

## 4. 統合テスト

- [ ] 4.1 dry-run テスト: analyze-project.py を rl-anything 自身に実行して JSON 出力を確認
- [ ] 4.2 生成テスト: atlas-breeaders 相当のサンプル CLAUDE.md で fitness 関数を生成し、インターフェース準拠を確認
- [ ] 4.3 既存 `--fitness` オプションとの互換確認: 生成された関数を optimize.py から呼び出せることを確認
