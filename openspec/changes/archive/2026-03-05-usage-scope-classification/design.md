## Context

`hooks/observe.py` が usage.jsonl に記録する Skill/Agent 利用データを、evolve/discover/audit が集計してレポート生成する。現状 scope 情報がないため、openspec 系などのプラグインツールがPJ固有パターンを覆い隠す。

## Goals / Non-Goals

**Goals:**
- レポート生成時にプラグインスキルを動的検出し、PJ固有とプラグイン利用を分離表示
- openspec のスキル名変更にも自動追従（ハードコード prefix 不要）
- OpenSpec ワークフローの分析機能を追加

**Non-Goals:**
- observe.py への scope フィールド追加（レポート生成時に動的分類で十分）
- TF-IDF による自動重み付け（将来拡張として残す）
- usage-registry.jsonl の廃止やスキーマ変更

## Decisions

### 1. ハードコード prefix → 動的プラグインスキャン

| 方式 | メリット | デメリット |
|---|---|---|
| ~~prefix マッチ~~ | シンプル | スキル名変更で壊れる |
| **動的プラグインスキャン** | 自動追従、正確 | installed_plugins.json 読み込みコスト（キャッシュで軽減） |

`_load_plugin_skill_map()` が `installed_plugins.json` を読み込み、`{skill_name: plugin_name}` マッピングを構築。結果はモジュールレベルでキャッシュ。

**理由**: openspec は外部団体が管理しており、update でスキル名変更がありうる。動的検出なら自動追従。

### 2. 分類タイミング: レポート生成時（not 記録時）

observe.py にハードコード prefix を持たせず、レポート生成時に `_load_plugin_skill_map()` で動的分類。

**理由**: openspec update 後も過去データを正しく再分類できる（後方互換問題なし）。

### 3. _BUILTIN_TOOLS は維持（直交する別軸）

`_BUILTIN_TOOLS`（Agent:*, commit）は「システム自動発動ツール」の除外リスト。scope（ツール出自）とは直交する概念なのでそのまま維持。

## Risks / Trade-offs

- [プラグイン未インストール] installed_plugins.json が存在しない環境ではフィルタが効かない → 既存と同じ挙動（全スキルが project 扱い）
- [キャッシュ鮮度] プラグイン install/uninstall 後、同一プロセス内ではキャッシュが古い → audit/evolve は毎回新プロセスで実行されるため実害なし
