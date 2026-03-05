## Context

rl-anything の discover は usage.jsonl からスキル/ルールの使用パターンを検出するが、「使うべきだったのに使われなかったスキル」は検出できない。また reflect の `suggest_claude_file()` はキーワードベース（`always/never/prefer` → global）でスコープ判定しており、correction の内容の意味的な判定はしていない。

実際のインシデント: ユーザーが「チャンネル設定」タスクに切り替えた際、`/channel-routing` スキルが存在するにもかかわらず手動で作業した。ユーザー自身が気づいて correction が発生。さらにその correction から生成されたルールのスコープ判定（global vs project）も、たまたまキーワードで正しくなっただけで本質的な判定ではなかった。

### 現行アーキテクチャ

- `discover.py`: usage.jsonl → `detect_behavior_patterns()` → パターン検出 → レポート
- `reflect_utils.py`: `suggest_claude_file()` → キーワードマッチでルーティング先決定
- observe hooks: usage.jsonl にプロンプトカテゴリ・ツール使用を記録（LLM コストゼロ）

## Goals / Non-Goals

**Goals:**
- discover で「スキルのトリガーワードにマッチするプロンプトがあったがスキルが使われなかった」パターンを検出する
- reflect のスコープ判定に「プロジェクト固有性」の判定ロジックを追加する
- 既存の observe hooks のデータ（sessions.jsonl + usage.jsonl）をそのまま活用する（新しいデータ収集不要）

**Non-Goals:**
- observe hook でのリアルタイム警告（LLM コストゼロ原則に反する）
- スキルの自動呼び出し（検出・提案のみ）
- トリガーワードの自動抽出（手動で定義したトリガーワードを使う）

## Decisions

### 1. スキルのトリガーワード取得元

**選択: CLAUDE.md の Skills セクションのトリガーワード記述をパースする**

代替案:
- `.claude/skills/*/` のメタデータから取得 → スキルのディレクトリ構造がプロジェクトごとに異なり、汎用的でない
- LLM でスキル内容からトリガーワード推定 → コストがかかり discover の軽量性に反する

理由: CLAUDE.md の Skills セクションには「トリガーワード」が明記されているケースが多い（例: `トリガー: channel routing, チャンネルマッピング`）。これを正規表現でパースするのが最も軽量で正確。

サポートするトリガーワード記法:
- `トリガー:` / `トリガーワード:`（日本語）
- `Trigger:` / `Triggers:`（英語、大文字小文字不問）
- 正規表現: `(?i)トリガー(?:ワード)?:\s*|triggers?:\s*`

取得フォールバック:
1. CLAUDE.md の Skills セクションからトリガーワード行をパース
2. なければスキル名自体をトリガーワードとして使用

### 2. missed skill 検出アルゴリズム

**選択: sessions.jsonl の user_prompts × スキルトリガーワードのキーワードマッチ + usage.jsonl でスキル使用実績を突合**

データソース選定理由: `usage.jsonl` の `prompt` フィールドは Agent レコードのみ（先頭200字）に存在し、通常の Skill レコードにはプロンプトがない。一方 `sessions.jsonl` の `user_prompts` はセッション内の全ユーザー入力を保持しており、カバレッジが高い。

```
Step 1: sessions.jsonl から user_prompts を取得
        → トリガーワードとキーワードマッチ
        → 「このセッションでスキルXが該当する」候補リスト作成

Step 2: usage.jsonl から同一 session_id のスキル使用実績を取得

Step 3: 候補 - 実績 = missed skill opportunities

Step 4: 頻度閾値（MISSED_SKILL_THRESHOLD）でフィルタリング
```

スキル名正規化: 突合時に先頭 `/` 除去、`plugin-name:` prefix 除去で表記揺れを吸収する（例: `/channel-routing`, `rl-anything:channel-routing`, `channel-routing` を同一視）。

project フィルタリング: 既存の `query_usage()` と同じ project フィルタを `query_sessions()` にも適用する（`--project-dir` / `--include-unknown` フラグ踏襲）。

sessions.jsonl 未生成時（backfill 未実行）: missed skill 検出をスキップし、レポートに `"No sessions.jsonl found (run backfill first), skipping missed skill detection"` と表示する。

代替案:
- LLM でセマンティック一致判定 → コスト高
- プロンプト embedding + cosine similarity → 依存関係追加、過剰
- usage.jsonl の prompt フィールドのみ使用 → Agent レコード以外にプロンプトがなく検出漏れが多い

理由: トリガーワードは人間が設計した「このスキルが該当する」キーワードなので、単純なキーワードマッチで十分。false positive は discover のレポートレベルなので許容可能。

### 3. reflect スコープ判定の改善

**選択: プロジェクト固有シグナルの検出ロジックを追加**

現行の `suggest_claude_file()` は `always/never/prefer` → global にルーティングする。以下のシグナルがある場合はプロジェクト固有と判定して project rule にルーティングする:

- correction テキストにプロジェクト固有のスキル名が含まれる（CLAUDE.md のスキル一覧と照合）
- correction テキストにプロジェクト固有のパス（`src/`, `app/` 等）が含まれる
- correction テキストにプロジェクト固有の技術スタック名が含まれる（CLAUDE.md から抽出）

判定順序: **プロジェクト固有シグナル → キーワードベース global → デフォルト**

代替案:
- LLM で意味判定 → reflect は対話的なので LLM コスト許容だが、`suggest_claude_file()` はバッチ呼び出しされるため重い
- ユーザーに毎回聞く → UX 低下

理由: キーワードベースの global 判定の前にプロジェクト固有シグナルチェックを挟むことで、既存ロジックを壊さずに精度を向上できる。

### 4. discover レポートへの統合

**選択: 既存レポートに `missed_skill_opportunities` セクションを追加**

```
=== Missed Skill Opportunities ===
  /channel-routing (3 sessions): triggers matched ["チャンネル", "bot追加"]
  /deploy-check (1 session): triggers matched ["デプロイ確認"]
```

## Risks / Trade-offs

- **[False positive] トリガーワードの偶発マッチ** → Mitigation: セッション内でスキルが実際に使われたかを確認し、使われていた場合は除外。また閾値（2セッション以上）で頻度フィルタ
- **[トリガーワード未定義] CLAUDE.md にトリガーワードが記載されていないスキル** → Mitigation: スキル名自体をフォールバックトリガーとして使用。検出精度は下がるが見落としは減る
- **[reflect 判定精度] プロジェクト固有シグナルの誤判定** → Mitigation: 判定結果は suggest であり最終的にユーザーが対話で確認する。判定に自信がない場合は both（global + project）の選択肢を提示

## Configuration

| 設定値 | 定義箇所 | デフォルト | 根拠 |
|--------|---------|-----------|------|
| 頻度閾値 | `MISSED_SKILL_THRESHOLD = 2` in `discover.py` | 2セッション以上 | 既存 `BEHAVIOR_THRESHOLD = 5` と同パターンの定数定義 |
| トリガーワード正規表現 | `TRIGGER_PATTERN` in `scripts/lib/skill_triggers.py` | `(?i)トリガー(?:ワード)?:\s*\|triggers?:\s*` | テストで網羅可能 |
| スキル名正規化 | `normalize_skill_name()` in `scripts/lib/skill_triggers.py` | 先頭 `/` 除去、`plugin-name:` prefix 除去 | スキル名表記揺れの吸収 |
| プロジェクト固有パス判定 | `detect_project_signals()` in `reflect_utils.py` | 実ディレクトリ存在チェック（ハードコードリスト不要） | 実在するパスのみを固有シグナルとみなす |
