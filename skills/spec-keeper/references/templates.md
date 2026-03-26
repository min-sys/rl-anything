# spec-keeper テンプレート集

SKILL.md から参照される。init / adr コマンドで使用する。

## SPEC.md テンプレート: MVP積み上げ型

ゲーム、新規プロダクトなど機能を段階的に追加するプロジェクト向け。

```markdown
# SPEC.md — {プロジェクト名}

Last updated: {YYYY-MM-DD} by /spec-keeper

## Overview

{1段落: プロジェクトの目的、対象ユーザー、コア体験}

## Tech Stack

{主要な技術スタック。フレームワーク、言語、主要ライブラリ}

## Current Capabilities

{MVP/バージョンごとの機能一覧。各機能は1行で what + how}

- MVP1: {機能名}（{実装概要}）
- MVP2: {機能名}（{実装概要}）

## Architecture

{主要コンポーネントと責務の概要。ディレクトリ構造との対応}

## Key Design Decisions

{ADR へのリンク付き一覧。ADR がまだない場合は主要な判断を箇条書き}

## Current Limitations / Known Issues

{意図的に未実装のもの、既知のバグ、技術的負債}

## Next

{次に予定している変更。gstack の design doc へのリンクがあれば含める}
```

## SPEC.md テンプレート: 頻繁改善型

API、インフラ、Bot など既存サービスの改善・運用が主体のプロジェクト向け。

```markdown
# SPEC.md — {プロジェクト名}

Last updated: {YYYY-MM-DD} by /spec-keeper

## Overview

{1段落: サービスの目的、対象ユーザー}

## Tech Stack

{言語、フレームワーク、主要ライブラリ}

## System Architecture

{インフラ構成の概要。AWS サービス、外部連携、デプロイ構成}

## API / Interface Spec

{主要なエンドポイント、コマンド、入出力の概要}

## Infrastructure

{AWS 構成、環境変数、デプロイプロセス、CI/CD}

## Key Design Decisions

{ADR へのリンク付き一覧}

## Recent Changes

{直近 5-10 件の変更サマリー。新しい順}

- {YYYY-MM-DD}: {変更内容}（{ADR リンクがあれば}）

## Current Limitations / Known Issues

## Next
```

## ADR テンプレート

```markdown
# ADR-{NNN}: {タイトル}

Date: {YYYY-MM-DD}
Status: Accepted
Related: {GitHub Issue があれば #番号}

## Context

{なぜこの判断が必要になったか。背景と制約}

## Decision

{何を決めたか。具体的な選択}

## Alternatives Considered

{検討した代替案とそれを選ばなかった理由}

### {代替案A}

{概要と不採用理由}

### {代替案B}

{概要と不採用理由}

## Consequences

{この判断の結果、何が変わるか}

- **良い影響**: {メリット}
- **悪い影響**: {トレードオフ、将来の制約}
```

## Layer Split Guide

SPEC.md が 100行を超えた場合、L1（単一ファイル）→ L2（hot + cold）へ昇格する際の分割ルール。

### SPEC.md (hot) に残すもの

全タスクで毎回必要になる情報のみ:

- Overview（1段落）
- Tech Stack（箇条書き）
- Architecture / System Architecture **サマリー**（1段落 + 概念図。コンポーネント詳細は cold）
- API / Interface Spec **コマンド表のみ**（パラメータ詳細は cold）
- Current Capabilities **サマリー**（1行/機能。実装詳細は cold）
- Key Design Decisions（カテゴリ1行サマリー + ADR リンク）
- Recent Changes（直近5件）
- Current Limitations / Known Issues（箇条書き）
- Next（箇条書き）

### spec/ に移動するもの（優先順位順）

特定タスクでのみ必要な詳細情報:

1. **Architecture 詳細** → `spec/architecture.md`（コンポーネントツリー、モジュール一覧、データフロー図）
2. **API / Interface 詳細** → `spec/api.md`（パラメータ、レスポンス例、エンドポイント詳細）
3. **Capabilities 詳細** → `spec/capabilities.md`（機能ごとの実装説明。MVP積み上げ型向け）
4. **Infrastructure 詳細** → `spec/infrastructure.md`（環境構成、デプロイ手順。頻繁改善型向け）

最も行数の多いセクションから順に移動し、SPEC.md (hot) が 60行以下になるまで繰り返す。

### ポインタフォーマット

SPEC.md から cold ファイルへの参照:

```markdown
## Architecture

3層パイプライン構成（Observe → Diagnose/Compile → Report）。

詳細は [spec/architecture.md](spec/architecture.md) を参照。
```

## Cold ファイルテンプレート

spec/ 配下の各ファイルで使う共通フォーマット:

```markdown
# {セクション名}

> このファイルは SPEC.md から分離された詳細仕様です。
> 概要は [SPEC.md](../SPEC.md) を参照してください。

Last updated: {YYYY-MM-DD}

{詳細内容}
```
