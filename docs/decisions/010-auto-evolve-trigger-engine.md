# ADR-010: Auto-Evolve Trigger Engine

Date: 2026-03-09
Status: Accepted

## Context

rl-anything は7つの observe hooks でテレメトリを収集し、`/evolve` で Diagnose / Compile / Housekeeping の3ステージパイプラインを実行するが、`/evolve` は手動実行が前提でユーザーが忘れると進化ループが止まる。測定 + 進化パイプラインが整備されたにもかかわらず、「ユーザーが忘れると動かない」状態にあった。

## Decision

- **トリガー評価を `scripts/lib/trigger_engine.py` に共通エンジンとして集約**: session_summary と correction_detect の両方がトリガー判定を行うため、条件評価・クールダウン・設定読み込みを重複させない
- **hook タイプ別出力方式の採用**:
  - Stop hook (async): `pending-trigger.json` にファイル書出し（Stop hook の stdout は Claude コンテキストに入らないため）
  - SessionStart: `restore_state.py` が `pending-trigger.json` を読み取り stdout に出力し、配信後にファイル削除（遅延配信方式）
- **4条件の OR 評価によるトリガー判定**:
  - 前回 evolve からのセッション数 >= 10
  - 前回 evolve からの経過日数 >= 7
  - corrections 蓄積件数 >= 10
  - 前回 audit からの経過日数 >= 30
- **クールダウン**: トリガーメッセージは1セッションにつき最大1回、同一条件の再提案は24時間以上の間隔
- **ユーザー設定は `evolve-state.json` の `trigger_config` キーに統合**: 新規設定ファイルの追加を避け、既存の load/save パターンを活用。未設定時はデフォルト値で動作（zero-config）
- **定期 audit は session-end 評価に統合**: Claude Code の CronCreate はセッションローカルで永続的 cron として使えないため、セッション終了時の条件評価に統合
- **correction トリガーでは `last_skill` フィールドから関連スキルを特定し `/optimize <skill>` を提案**: last_skill が空の場合は汎用の `/evolve` を提案

## Alternatives Considered

- **各 hook に直接トリガーロジックを埋め込む**: 閾値変更時に複数箇所の修正が必要になるため却下。共通エンジンに集約
- **Stop hook で直接 stdout 出力**: Claude コンテキストに入らないため却下。pending-trigger.json 経由の遅延配信方式を採用
- **`trigger-config.json` を新規作成**: 既存の設定ファイルパターン（evolve-state.json に集約）から逸脱するため却下
- **CronCreate で月次 cron を登録**: セッション終了で消失するため実用的でなく却下
- **全トリガーを自動実行**: ユーザー承認なしの自動実行は Graduated Autonomy（Phase 5）の領域。現段階は提案のみ

## Consequences

**良い影響:**
- 進化ループが Zero-Touch 化され、ユーザーが `/evolve` を忘れても適切なタイミングで提案が表示される
- trigger_engine は JSON 読み込み + 比較のみで LLM コストゼロ、パフォーマンス影響は無視できるレベル
- ユーザーが閾値や有効/無効をカスタマイズ可能で、通知疲れを防止できる

**悪い影響:**
- 通知疲れのリスクがある（クールダウン + セッション単位の重複排除で緩和）
- pending-trigger.json が SessionStart まで残留する場合があるが、古い提案が表示されるのみで影響は軽微
- evolve-state.json への書き込みが hooks からも発生するが、トリガー履歴のみに限定して書き込み競合を回避
