## MODIFIED Requirements

### Requirement: evolve passes project context to discover
evolve.py は `--project-dir` 引数を discover の全検出関数に `project_root` として伝播する MUST。`load_claude_reflect_data()` は `reflect_status == "pending"` のレコードのみを返す MUST。

#### Scenario: evolve with project-dir
- **WHEN** `evolve.py --project-dir /Users/foo/atlas-breeaders` が実行される
- **THEN** discover の `detect_behavior_patterns()` および `detect_error_patterns()` に `project_root` が渡され、PJ スコープでフィルタリングされる

#### Scenario: reflect_data_count は pending のみをカウントする
- **WHEN** corrections.jsonl に7件のレコードがあり、うち4件が `reflect_status: "pending"`、3件が `reflect_status: "applied"` である
- **THEN** evolve の `reflect_data_count` は 4 を報告する（MUST）。applied/skipped レコードを含めてはならない（MUST NOT）
