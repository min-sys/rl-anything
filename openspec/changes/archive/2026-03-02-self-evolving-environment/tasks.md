## 1. 環境観測 hooks（Observe）

- [x] 1.0 ~/.claude/rl-anything/ ディレクトリの初期化スクリプト（ディレクトリ作成 + .gitignore）
- [x] 1.1 hooks/observe.py — PostToolUse async hook（使用スキル・ファイルパス・エラー記録）
- [x] 1.2 hooks/observe.py — global スキル使用時にプロジェクトパスも usage-registry.jsonl に記録
- [x] 1.3 hooks/session_summary.py — Stop async hook（セッション要約を sessions.jsonl に追記）
- [x] 1.4 hooks/save_state.py — PreCompact async hook（進化状態のチェックポイント保存）
- [x] 1.5 hooks/restore_state.py — SessionStart compact hook（チェックポイントからの状態復元）
- [x] 1.6 hooks.json に全 hook 定義を追加
- [x] 1.7 observe hooks のスモークテスト

## 2. 最適化テレメトリ（genetic-prompt-optimizer 拡張）

- [x] 2.1 Individual クラスに strategy フィールド追加 + to_dict() 更新
- [x] 2.2 mutate() → strategy = "mutation"、crossover() → strategy = "crossover"
- [x] 2.3 next_generation() エリート選出時 → strategy = "elite"
- [x] 2.4 Individual クラスに cot_reasons フィールド追加
- [x] 2.5 _llm_evaluate() から reason テキストを cot_reasons に保存
- [x] 2.6 history.jsonl に human_accepted フィールド追加
- [x] 2.7 history.jsonl に rejection_reason フィールド追加
- [x] 2.8 人間 accept/reject 時のオプション理由入力 UI
- [x] 2.9 telemetry フィールドのテスト（strategy, cot_reasons, rejection_reason, human_accepted）。既存テスト test_optimizer.py のフィクスチャ更新を含む

## 3. フィードバックコマンド

- [x] 3.1 skills/feedback/SKILL.md — /rl-anything:feedback スキル作成
- [x] 3.2 gh 認証チェックフロー実装
- [x] 3.3 対話フロー（カテゴリ → ドメイン → スコア → 自由記述）
- [x] 3.4 プライバシー保護ルール（スキル内容・パスを含めない）
- [x] 3.5 Issue 本文生成 → プレビュー → 送信
- [x] 3.6 送信失敗時のローカル保存フォールバック
- [x] 3.7 .github/ISSUE_TEMPLATE/feedback.yml 作成
- [x] 3.8 .github/ISSUE_TEMPLATE/config.yml（blank_issues_enabled: false）

## 4. 健康診断 + レポート（Audit / Report）

- [x] 4.1 全 skills / rules / memory の棚卸しスクリプト
- [x] 4.2 行数チェック（CLAUDE.md 200行、rules 3行、SKILL.md 500行、MEMORY.md 200行、memory 120行）
- [x] 4.3 usage.jsonl からの使用状況集計
- [x] 4.4 Global ↔ Project 重複検出（LLM ベースの意味的類似度判定。閾値 80%）。共通ユーティリティ関数として実装し、prune（5.4）でも再利用する
- [x] 4.5 Scope Advisory レポート（Usage Registry ベース）
- [x] 4.6 scripts/aggregate-runs.py（クロスラン集計：戦略別有効性・スコア推移）
- [x] 4.7 1画面レポート出力
- [x] 4.8 skills/audit/SKILL.md — /rl-anything:audit スキル作成

## 5. 淘汰（Prune）

- [x] 5.1 dead glob 検出（rules の paths 対象がマッチするか検査）
- [x] 5.2 zero invocation 検出（usage.jsonl ベース、30日ルール）
- [x] 5.3 global スキルの安全判断（Usage Registry で cross-PJ 使用状況確認）
- [x] 5.4 重複検出（4.4 で実装した意味的類似度の共通ユーティリティ関数を再利用）
- [x] 5.5 アーカイブ処理（.claude/rl-anything/archive/ へ移動）
- [x] 5.6 アーカイブ提案 + 人間承認フロー
- [x] 5.7 復元コマンド
- [x] 5.8 skills/prune/SKILL.md — /rl-anything:prune スキル作成
- [x] 5.9 復元失敗時のエラーハンドリング（archive にファイルが存在しない場合）

## 6. 発見（Discover）

- [x] 6.1 繰り返し行動パターンの検出（usage + sessions、5+閾値）
- [x] 6.2 繰り返しエラーパターンの検出（errors、3+閾値）
- [x] 6.3 繰り返し却下理由の検出（rejection_reason、3+閾値）
- [x] 6.4 スコープ配置判断ロジック（global / project / plugin）
- [x] 6.5 スキル候補の生成（SKILL.md 500行バリデーション付き）
- [x] 6.6 ルール候補の生成（3行バリデーション付き）
- [x] 6.7 claude-reflect データの取り込み（オプション、未インストール時はスキップ）
- [x] 6.8 skills/discover/SKILL.md — /rl-anything:discover スキル作成

## 7. 統合（Evolve オーケストレーター）

前提: セクション 1-6 が完了していること。

- [x] 7.1 Observe データ確認 → Discover → Optimize → Prune → Report の統合フロー
- [x] 7.2 観測データ量による自動スキップ判定（前回 evolve 実行以降のセッション数が3未満 / 10観測未満）
- [x] 7.3 --dry-run モード（レポートのみ、変更なし）
- [x] 7.4 連続実行時のべき等性（前回以降の新規データのみ処理）
- [x] 7.5 skills/evolve/SKILL.md — /rl-anything:evolve スキル作成

## 8. 評価関数の自己成長

- [x] 8.1 score-acceptance 相関の計算（直近20件）
- [x] 8.2 相関低下時（< 0.50）の再キャリブレーション警告
- [x] 8.3 rejection_reason の頻度分析 → 欠落評価軸の提案
- [x] 8.4 CoT reason のパターン分析 → 評価軸の重み調整提案
- [x] 8.5 adversarial probe: ゲーミング候補を生成して fitness の脆弱性検出
- [x] 8.6 skills/evolve-fitness/SKILL.md — /rl-anything:evolve-fitness スキル作成
- [x] 8.7 全変更の人間承認フロー

## 9. 肥大化制御の自動化

- [x] 9.1 既存の _regression_gate()（optimize.py:410）を共通ユーティリティとして抽出し、全パイプラインのサイズバリデーションで再利用する
- [x] 9.2 evolve 実行時の bloat check（CLAUDE.md, MEMORY.md, rules 総数, skills 総数）
- [x] 9.3 分割提案の自動生成（MEMORY.md → トピック別ファイル）
- [x] 9.4 Usage Registry: global スキル/ルールの使用状況をプロジェクト横断で追跡
- [x] 9.5 Scope Advisor: Usage Registry ベースのスコープ最適化提案
- [x] 9.6 Plugin Bundling 提案: 常に一緒に使われるスキル群の plugin 化推奨
