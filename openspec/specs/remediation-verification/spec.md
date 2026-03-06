## ADDED Requirements

### Requirement: Fix verification
修正実行後、対象ファイルに対して該当する検出関数を再実行し、元の問題が解消されたことを確認する（SHALL）。

#### Scenario: Stale reference removed successfully
- **WHEN** 陳腐化参照の行が削除された
- **THEN** 対象ファイルに対して `_extract_paths_outside_codeblocks()` を再実行し、当該参照が検出されないことを確認する

#### Scenario: Line count reduced below limit
- **WHEN** reference 切り出しによりスキルの行数が削減された
- **THEN** 対象ファイルに対して行数を再計測し、制限値以下であることを確認する

#### Scenario: Fix did not resolve the issue
- **WHEN** 修正実行後の再検証で元の問題が残存している
- **THEN** 「修正が不完全です。手動対応が必要です」と表示し、残存する問題の詳細を出力する。result = "incomplete" が記録される

### Requirement: Regression check
修正が副作用を起こしていないことを検証する（SHALL）。Fix verification とは独立した検証ステップとして実行する。

#### Scenario: Markdown heading structure preserved after line deletion
- **WHEN** MEMORY ファイルから陳腐化参照の行を削除した
- **THEN** 削除後のファイルの見出し構造（## セクション）が削除前と同じであることを確認する

#### Scenario: Reference link validity after extraction
- **WHEN** スキルのセクションを reference ファイルに切り出した
- **THEN** 元ファイルから reference ファイルへの参照リンクが有効であることを確認する

#### Scenario: Markdown format integrity after blank line removal
- **WHEN** ファイルから空行を除去した
- **THEN** Markdown のリスト・コードブロック・テーブルのフォーマットが崩れていないことを確認する

#### Scenario: Regression detected triggers rollback
- **WHEN** regression check で副作用（構造破壊、リンク切れ、フォーマット崩壊）が検出された
- **THEN** 修正をロールバック（修正前の内容に復元）し、当該問題を manual_required に格上げする。result = "rolled_back" が記録される

### Requirement: Verification scope limitation
再検証は修正が実行されたファイルのみを対象とする（SHALL）。全体の audit 再実行は行わない。

#### Scenario: Only modified files are re-checked
- **WHEN** 3つの MEMORY ファイルのうち1つの陳腐化参照を修正した
- **THEN** 修正されたファイルのみが fix verification と regression check の対象となり、他の2ファイルは再検証されない

### Requirement: Verification result summary
Remediation フェーズの最後に、修正結果のサマリを表示する（SHALL）。

#### Scenario: All fixes successful
- **WHEN** 全ての修正が fix verification と regression check を通過した
- **THEN** 「Remediation 完了: N件修正、全て検証済み」と表示する

#### Scenario: Partial fixes with rollback
- **WHEN** 一部の修正が成功し、一部がロールバックまたはスキップされた
- **THEN** 「Remediation 完了: N件修正 / M件スキップ / K件ロールバック（要手動対応）」と表示する
