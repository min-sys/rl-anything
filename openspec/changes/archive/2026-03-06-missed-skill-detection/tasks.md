## 1. スキルトリガーワード抽出

- [x] 1.1 CLAUDE.md の Skills セクションからスキル名とトリガーワードを抽出する関数 `extract_skill_triggers()` を `scripts/lib/` に作成
- [x] 1.2 トリガーワード未記載時のフォールバック（スキル名自体を使用）を実装
- [x] 1.3 `extract_skill_triggers()` のユニットテスト作成（トリガーワード記法バリエーション含む）
- [x] 1.4 `telemetry_query.py` に `query_sessions()` を追加（sessions.jsonl の user_prompts/user_intents 取得、project フィルタ対応）

## 2. Missed Skill 検出ロジック

- [x] 2.1 `detect_missed_skills()` 関数を `discover.py` に追加: sessions.jsonl の user_prompts × トリガーワード突合 + usage.jsonl のスキル使用実績との session_id 照合
- [x] 2.2 セッション内でスキルが使われた場合の除外ロジック実装（スキル名正規化: 先頭 `/` 除去、`plugin-name:` prefix 除去）
- [x] 2.3 頻度閾値フィルタリング（`MISSED_SKILL_THRESHOLD = 2` 定数、デフォルト2セッション以上）実装
- [x] 2.4 `detect_missed_skills()` のユニットテスト作成
- [x] 2.5 sessions.jsonl 未生成時のフォールバック（スキップ + メッセージ表示）

## 3. Discover レポート統合

- [x] 3.1 discover レポートに `missed_skill_opportunities` セクションを追加
- [x] 3.2 CLAUDE.md 未検出時のスキップメッセージ実装
- [x] 3.3 レポート出力のユニットテスト作成

## 4. Reflect スコープ判定改善

- [x] 4.1 `detect_project_signals()` 関数を `reflect_utils.py` に追加: CLAUDE.md のスキル一覧照合 + correction テキスト内パスのプロジェクトルート実在チェック
- [x] 4.2 `suggest_claude_file()` のルーティング優先順位を変更: guardrail → プロジェクト固有シグナル → モデル名 → always/never/prefer
- [x] 4.3 既存の `suggest_claude_file()` テストが通ることを確認（リグレッション防止）
- [x] 4.4 新しいスコープ判定のユニットテスト作成（project-specific skill、generic always、mixed case）

## 5. 結合テスト

- [x] 5.1 discover の missed skill 検出 → レポート出力の E2E テスト
- [x] 5.2 reflect のスコープ判定が既存テストと新規テストの両方でパスすることを確認
