Related: #27

## Context

verification_catalog.py は検証知見を VERIFICATION_CATALOG リストとして管理し、discover → evolve → remediation パイプラインで未導入ルールを自動提案する仕組みを持つ。現在は `data-contract-verification` の1エントリのみ。

issue #27 では、テスト検証時に「正パスのみ確認・副作用未確認」パターンが繰り返されることが報告された。verification.md ルールへの1行追加は完了済みだが、discover/reflect でこのパターンを自動検出しルール提案する仕組みが未整備。

## Goals / Non-Goals

**Goals:**
- verification_catalog に `side-effect-verification` エントリを追加し、DB操作・メッセージキュー・Webhook 等の共有リソースアクセスパターンからルール適用を判定
- reflect_utils.py に corrections ベースの副作用見落としパターン検出を追加し、ルーティング精度を向上
- 既存の discover → evolve → remediation パイプラインにそのまま乗る設計

**Non-Goals:**
- テスト自体の自動生成（副作用チェックテストを自動生成するのは別 change）
- corrections.jsonl のスキーマ変更
- 既存 `data-contract-verification` エントリの修正

## Decisions

### D1: 検出関数のアプローチ — regex ベース静的解析

副作用リスクのある共有リソースアクセスパターンを regex で検出する。

**検出パターン（3カテゴリ）:**

| カテゴリ | Python パターン例 | TypeScript パターン例 |
|---------|------------------|---------------------|
| DB 操作 | `session.add`, `cursor.execute`, `.commit()`, `INSERT INTO` | `prisma.*.create`, `.save()`, `knex.*insert` |
| メッセージキュー | `sqs.send_message`, `publish(`, `channel.basic_publish` | `sendMessage`, `.publish(`, `channel.sendToQueue` |
| 外部 API/Webhook | `requests.post`, `httpx.post`, `aiohttp.*post`, `slack_client` | `fetch(`, `axios.post`, `webhook` |

**代替案と却下理由:**
- AST 解析: 精度は高いが実装コストとタイムアウトリスクが大。regex の confidence 上限 0.7 + LLM escalation で十分
- corrections のみベース: 過去データ依存でコールドスタート問題。静的解析と併用する

### D2: ルールテンプレート — プロジェクト固有の副作用チェックリスト

検出された共有リソースカテゴリに応じて、テンプレート内のチェック項目を動的に選択する。

```markdown
# 副作用チェック
テスト検証時、正パスに加えて副作用を確認する: 意図しない書き込み・状態残留・再帰的トリガー。
```

3行以内のルール。具体的なチェック項目は検出 evidence に基づき LLM escalation で補完。

### D3: corrections パターン検出 — reflect_utils の suggest_claude_file 拡張

reflect_utils.py の `suggest_claude_file()` で、corrections メッセージに副作用関連キーワードが含まれる場合、verification ルールへのルーティング confidence を上げる。

**ルーティング優先度**: guardrail(1) → project signals(2) → **副作用検出(3)** → model(4) → ...
- project signals が `True` を返した場合、副作用チェックはスキップする（PJ固有ルーティング優先）

新関数 `detect_side_effect_correction()` として分離し、`suggest_claude_file()` から呼び出す。

**キーワード設計（FP抑制）:**

| 種類 | パターン | 備考 |
|------|---------|------|
| 日本語単純 | 「副作用」「残留」「意図しない」「再帰的」 | 「再帰」単体は除外（再帰関数の文脈で FP） |
| 日本語複合 | `pending.*(?:残留\|table\|テーブル)` | 「pending」単体は汎用的すぎるため複合パターン化 |
| 英語 | `side effect`, `unintended`, `residual`, `recursive`, `leftover` | |

削除キーワード:
- 「トップレベル投稿」: 特定 PJ 固有すぎるため除外
- 「pending」単体: 汎用的すぎるため複合パターンに変更
- 「再帰」単体: 「再帰的」のみ残留

キーワードは定数リスト `_SIDE_EFFECT_KEYWORDS_JA` / `_SIDE_EFFECT_KEYWORDS_EN` / `_SIDE_EFFECT_COMPOUND_PATTERNS` として管理する。

## Risks / Trade-offs

- **regex の偽陽性**: `requests.post` が API クライアントのテストコード内に多数あるプロジェクトで過剰検出 → テストファイル除外フィルタ + `confidence` 上限 0.7 + `llm_escalation_prompt` で緩和
- **3行ルール制約**: 副作用チェックの詳細を1ルールに収めきれない → ルールは原則のみ、具体チェック項目は LLM escalation prompt に含める
- **カタログ肥大化**: エントリ追加で MAX_CATALOG_ENTRIES (10) に近づく → 現在2エントリ目なので当面問題なし
