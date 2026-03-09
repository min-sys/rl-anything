## ADDED Requirements

### Requirement: prefix 付きセクション名にマッチする

`diagnose_claudemd()` のスキルセクション検出は、見出しの先頭に任意の prefix がある場合でもマッチしなければならない（MUST）。例: `## Key Skills`, `## Available Skills`, `## Project Skills`。

#### Scenario: prefix 付き英語セクション名にマッチする
- **WHEN** CLAUDE.md に `## Key Skills` という見出しがある
- **THEN** Skills セクションとして認識され、`claudemd_missing_section` は検出されない

#### Scenario: prefix 付き日本語セクション名にマッチする
- **WHEN** CLAUDE.md に `## 主要スキル` という見出しがある
- **THEN** Skills セクションとして認識され、`claudemd_missing_section` は検出されない

#### Scenario: 単語境界で誤マッチしない
- **WHEN** CLAUDE.md に `## Skillset Overview` という見出しがある
- **THEN** Skills セクションとして認識されない（`\b` ワードバウンダリで区別）

#### Scenario: 標準的なセクション名は引き続きマッチする
- **WHEN** CLAUDE.md に `## Skills` という見出しがある
- **THEN** Skills セクションとして認識される（既存動作を維持）
