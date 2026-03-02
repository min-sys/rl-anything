## ADDED Requirements

### Requirement: プロジェクト構成ファイルの自動検出
analyze-project.py はカレントディレクトリから CLAUDE.md、`.claude/rules/*.md`、`.claude/skills/*/SKILL.md` を自動検出し、読み込み可能なファイル一覧を返さなければならない（MUST）。ファイルが存在しない場合はスキップしなければならない（MUST）。

#### Scenario: 全ファイルが存在する場合
- **WHEN** CLAUDE.md, `.claude/rules/`, `.claude/skills/` がすべて存在する
- **THEN** 全ファイルを読み込み、分析対象として返さなければならない（MUST）

#### Scenario: CLAUDE.md のみ存在する場合
- **WHEN** CLAUDE.md は存在するが rules/ と skills/ が存在しない
- **THEN** CLAUDE.md のみを分析対象とし、エラーなく動作しなければならない（MUST）

#### Scenario: いずれのファイルも存在しない場合
- **WHEN** CLAUDE.md も rules/ も skills/ も存在しない
- **THEN** エラーメッセージ「プロジェクト構成ファイルが見つかりません」を stderr に出力し、終了コード 1 で終了しなければならない（MUST）

### Requirement: 運用知見ファイル（pitfalls.md）の検出
analyze-project.py はスキルディレクトリ内の `references/pitfalls.md` を検出し、存在する場合はその内容を anti_patterns の追加ソースとして取り込まなければならない（MUST）。存在しない場合はスキップし、通常通り動作しなければならない（MUST）。

#### Scenario: pitfalls.md が存在する場合
- **WHEN** 分析対象スキルの `references/pitfalls.md` が存在する
- **THEN** ファイル内容をパースし、記載されている失敗パターン・回避策を `anti_patterns` フィールドに追加しなければならない（MUST）。CLAUDE.md 等から抽出した anti_patterns とマージする

#### Scenario: pitfalls.md が存在しない場合
- **WHEN** `references/pitfalls.md` が存在しない
- **THEN** anti_patterns は CLAUDE.md・rules・skills からの抽出のみで構成し、エラーなく動作しなければならない（MUST）

#### Scenario: 複数スキルに pitfalls.md がある場合
- **WHEN** `.claude/skills/` 配下の複数スキルにそれぞれ `references/pitfalls.md` が存在する
- **THEN** 全 pitfalls.md の内容を収集し、重複を除去して anti_patterns にマージしなければならない（MUST）

### Requirement: ドメイン特性の推定
分析結果として、プロジェクトのドメイン種別と品質基準をJSON形式で stdout に出力しなければならない（MUST）。

#### Scenario: ドメイン推定の出力形式
- **WHEN** analyze-project.py を実行する
- **THEN** 以下のJSON構造を stdout に出力しなければならない（MUST）: `{"domain": "<種別>", "criteria": [{"name": "<基準名>", "description": "<説明>", "weight": <0.0-1.0>}], "keywords": ["<検出すべきキーワード>"], "anti_patterns": ["<検出すべきアンチパターン>"]}`

#### Scenario: ゲームプロジェクトの推定
- **WHEN** CLAUDE.md に「ゲーム」「冒険」「キャラクター」等のゲーム関連語彙が含まれる
- **THEN** domain を "game" と推定し、没入感・世界観語彙・ナラティブ品質を criteria に含めなければならない（MUST）

#### Scenario: ドキュメント基盤プロジェクトの推定
- **WHEN** CLAUDE.md に「ドキュメント」「reference」「handbook」等の語彙が含まれる
- **THEN** domain を "documentation" と推定し、front matter・source コメント・構造整合性を criteria に含めなければならない（MUST）

#### Scenario: Bot/対話プロジェクトの推定
- **WHEN** CLAUDE.md に「Slack Bot」「対話」「personality」「RAG」等の語彙が含まれる
- **THEN** domain を "bot" と推定し、パーソナリティ適合・応答品質・トーン一貫性を criteria に含めなければならない（MUST）

#### Scenario: ドメイン判定がどのカテゴリにも閾値を超えない場合
- **WHEN** ドメイン判定に使用するキーワードがどのカテゴリ（game/documentation/bot）にも閾値を超えない
- **THEN** `"domain": "general"` をフォールバックとして出力しなければならない（MUST）。criteria はデフォルトの汎用品質軸（clarity, completeness, structure, practicality）を使用しなければならない（MUST）
