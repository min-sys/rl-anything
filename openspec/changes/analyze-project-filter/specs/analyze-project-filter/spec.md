## ADDED Requirements

### Requirement: analyze.py がプロジェクト名で JSONL データをフィルタする

`analyze.py` は `--project` CLI 引数で指定されたプロジェクト名に基づき、sessions.jsonl の `project_name` フィールドから対象 session_id セットを取得し（MUST）、その session_id セットで usage.jsonl / workflows.jsonl をフィルタしてフィルタ済みデータのみで分析を実行しなければならない（MUST）。

#### Scenario: --project 指定時に該当プロジェクトのデータのみ分析される

- **WHEN** `analyze.py --project my-project` を実行する
- **THEN** sessions.jsonl から `project_name == "my-project"` のレコードの session_id を抽出し、usage.jsonl / workflows.jsonl をその session_id でフィルタして分析レポートを出力する

#### Scenario: --project 未指定時にカレントディレクトリ名がデフォルトになる

- **WHEN** `analyze.py` を引数なしで実行する
- **THEN** カレントディレクトリ名（`Path(os.getcwd()).name`）をプロジェクト名として使用し、そのプロジェクトのデータのみを分析する

#### Scenario: 該当プロジェクトのデータが存在しない場合

- **WHEN** `analyze.py --project nonexistent` を実行し、sessions.jsonl に該当 project_name のレコードがない
- **THEN** 空のデータセットとして分析を実行し、各セクションに「データなし」と表示する

#### Scenario: sessions.jsonl に project_name がないレコードが含まれる場合
- **WHEN** sessions.jsonl に project_name フィールドが存在しないレコード（observe hooks 経由）が含まれる
- **THEN** そのレコードはフィルタ対象外となり、結果に含めてはならない（MUST NOT）

### Requirement: project_name_from_dir を共通モジュールに移動する

`backfill.py` にある `project_name_from_dir()` 関数を `hooks/common.py` に移動し（MUST）、`backfill.py` と `analyze.py` の両方から `common.project_name_from_dir()` として利用可能にしなければならない（MUST）。

#### Scenario: backfill.py と analyze.py が同じプロジェクト名解決ロジックを使用する

- **WHEN** 同じディレクトリから `backfill.py` と `analyze.py` を実行する
- **THEN** 両方が同一の `project_name_from_dir()` 実装を使用し、同じプロジェクト名を返す

#### Scenario: project_name_from_dir が空文字列を返す場合
- **WHEN** 引数がルートディレクトリ（/）や空文字列の場合
- **THEN** 空文字列をプロジェクト名として返し、空文字列一致でフィルタする

### Requirement: SKILL.md の Step 2 コマンドにプロジェクトフィルタを追加する

SKILL.md の Step 2（分析レポート出力）のコマンドに `--project` パラメータを追加し、カレントプロジェクトのデータのみが分析されるようにしなければならない（MUST）。

#### Scenario: SKILL.md のコマンドがプロジェクトフィルタ付きで記載されている

- **WHEN** `/rl-anything:backfill` スキルが Step 2 を実行する
- **THEN** `analyze.py --project "$(basename $(pwd))"` のようにプロジェクト名を渡して実行する
