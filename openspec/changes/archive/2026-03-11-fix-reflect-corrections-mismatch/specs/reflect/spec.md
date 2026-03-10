## MODIFIED Requirements

### Requirement: Semantic validation (default enabled, batch)
セマンティック検証はデフォルト有効。全 pending corrections を1回の `claude -p` 呼び出しでバッチ検証し、偽陽性を除去する（MUST）。`--skip-semantic` で無効化可能。フォールバック時は `is_learning=True` でパススルーし、全件除外してはならない（MUST NOT）。

#### Scenario: Semantic validation filters false positive
- **WHEN** "いや、今日は天気がいい" が regex で検出され、semantic 検証を実行する
- **THEN** `is_learning: false` と判定されフィルタされる

#### Scenario: Batch validation of multiple corrections
- **WHEN** pending corrections が 5件あり、semantic 検証を実行する
- **THEN** 5件を1回の `claude -p` 呼び出しでまとめて検証し、各 correction に `is_learning` 判定を返す

#### Scenario: Semantic validation skipped
- **WHEN** `/reflect --skip-semantic` を実行する
- **THEN** LLM 検証をスキップし、regex 検出結果のみで処理する

#### Scenario: Batch size exceeds limit
- **WHEN** pending corrections が 30件あり、semantic 検証を実行する
- **THEN** 20件ずつ2バッチに分割して `claude -p` を呼び出す

#### Scenario: Semantic validation JSON parse failure
- **WHEN** `claude -p` のレスポンスが不正な JSON（パース失敗、件数不一致等）である
- **THEN** 全件を `is_learning=True` としてパススルーし（MUST）、stderr に警告を出力する。全件を `is_learning=False` として除外してはならない（MUST NOT）

#### Scenario: Semantic validation unavailable
- **WHEN** `claude -p` の呼び出しがタイムアウトする
- **THEN** 全件を `is_learning=True` としてパススルーし（MUST）、警告を表示する
