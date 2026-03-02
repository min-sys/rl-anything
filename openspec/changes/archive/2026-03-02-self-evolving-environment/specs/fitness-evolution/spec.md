## ADDED Requirements

### Requirement: score-acceptance 相関を追跡しなければならない（MUST）
直近20件の score と human_accepted の相関を計算し、評価関数の精度を監視しなければならない（MUST）。
human_accepted と rejection_reason のデータは genetic-prompt-optimizer の history.jsonl（Single Source of Truth）を参照する（SHALL）。

#### Scenario: 相関低下時の警告
- **WHEN** score-acceptance 相関が 0.50 未満に低下する
- **THEN** 「評価関数の再キャリブレーション推奨」の警告を表示しなければならない（MUST）

#### Scenario: 直近20件に満たない場合のスキップ
- **WHEN** 相関計算に必要なデータが直近20件に満たない
- **THEN** 計算をスキップし次回に持ち越さなければならない（MUST）。不完全なデータでの計算を行ってはならない（MUST NOT）

### Requirement: rejection_reason の頻度分析を行わなければならない（MUST）
genetic-prompt-optimizer の history.jsonl に蓄積された rejection_reason から、欠落している評価軸を検出しなければならない（MUST）。

#### Scenario: 欠落評価軸の検出
- **WHEN** 同じ rejection_reason が3回以上蓄積されている
- **THEN** 現在の評価軸にない新しい軸の追加を提案しなければならない（SHALL）

### Requirement: /rl-anything:evolve-fitness スキルで評価関数の改善を提案しなければならない（MUST）
accept/reject が30件以上蓄積されたら実行可能とする（SHALL）。
相関レポート・軸ドリフト検出・欠落軸提案・anti-pattern 追加を行わなければならない（MUST）。

#### Scenario: 評価関数改善レポートの出力
- **WHEN** ユーザーが `/rl-anything:evolve-fitness` を実行し、30件以上のデータがある
- **THEN** score-acceptance 相関・推奨重み調整・欠落軸・anti-pattern 候補が表示される

#### Scenario: データ不足時
- **WHEN** accept/reject データが30件未満である
- **THEN** 「データ不足」メッセージを表示し、必要なデータ量を案内しなければならない（MUST）

### Requirement: 全変更は人間承認が必須である（MUST）
評価関数の自動変更を行ってはならない（MUST NOT）。提案を提示し、ユーザーが承認したもののみ適用しなければならない（MUST）。

#### Scenario: 承認フロー
- **WHEN** 評価関数の変更が提案される
- **THEN** プレビュー → 承認/却下のフローを経由しなければならない（MUST）
