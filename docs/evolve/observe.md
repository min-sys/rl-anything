# Phase 1: Observe（観測）

環境の使用状況を静かに記録する。ユーザーの開発体験への影響はゼロ。

## 3つの観測レイヤー

```
Layer A: 環境観測（async hooks — 常時・自動）
  スキル使用回数、ファイルパス、エラー、セッション要約、ワークフロー、修正フィードバック

Layer B: 最適化観測（execution telemetry — optimize/rl-loop 実行時）
  変異戦略タグ、CoT 評価 reason、人間却下理由

Layer C: ユーザーフィードバック（/feedback コマンド — 手動・オプトイン）
  外部ユーザーからの構造化フィードバック → GitHub Issues
```

---

## Layer A: 環境観測 hooks（7個）

7つの hooks がセッションライフサイクル全体をカバー。LLM 呼び出しなし。

### Hook 設定

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/correction_detect.py\"",
        "timeout": 5000
      }]
    }],
    "PreToolUse": [{
      "matcher": "Skill",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/workflow_context.py\"",
        "timeout": 5000
      }]
    }],
    "PostToolUse": [{
      "matcher": "Skill|Agent",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/observe.py\"",
        "timeout": 5000
      }]
    }],
    "SubagentStop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/subagent_observe.py\"",
        "timeout": 5000
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/session_summary.py\"",
        "timeout": 5000
      }]
    }],
    "PreCompact": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/save_state.py\"",
        "timeout": 5000
      }]
    }],
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/restore_state.py\"",
        "timeout": 5000
      }]
    }]
  }
}
```

### 7 hooks の役割

| Hook | イベント | 処理内容 | 出力先 |
|------|---------|---------|--------|
| `observe.py` | PostToolUse | Skill/Agent 使用記録、エラー記録 | `usage.jsonl`, `errors.jsonl`, `usage-registry.jsonl` |
| `correction_detect.py` | UserPromptSubmit | CJK/英語 26パターンの修正フィードバック検出 | `corrections.jsonl` |
| `subagent_observe.py` | SubagentStop | サブエージェント完了データ記録 | `subagents.jsonl` |
| `workflow_context.py` | PreToolUse | Skill 呼び出し時にワークフロー文脈を書き出し | `$TMPDIR/rl-anything-workflow-*.json` |
| `save_state.py` | PreCompact | コンテキスト圧縮前に進化状態 + corrections をチェックポイント | `checkpoint.json` |
| `restore_state.py` | SessionStart | チェックポイントから進化状態を復元 | stdout |
| `session_summary.py` | Stop | セッション要約 + ワークフローシーケンス記録 | `sessions.jsonl`, `workflows.jsonl` |

### ワークフロートレーシング

```
[SessionStart]  restore_state が checkpoint を復元
       ↓
[UserPromptSubmit]  correction_detect が修正パターンを検出 → corrections.jsonl
       ↓
[PreToolUse]    workflow_context が Skill 呼び出しに workflow_id を付与
       ↓
[PostToolUse]   observe が Skill/Agent 使用を記録（workflow_id 付き）
       ↓
[SubagentStop]  subagent_observe がサブエージェント完了を記録
       ↓
[PreCompact]    save_state が進化状態 + corrections をチェックポイント
       ↓
[Stop]          session_summary がセッション要約 + ワークフローシーケンスを出力
```

### 記録データ

| データ | 記録先 | 用途 |
|--------|--------|------|
| 使用されたスキル名 + 回数 | usage.jsonl | Prune の判断材料 |
| 触られたファイルパス | usage.jsonl | ルールの活性度判定 |
| ツールエラー | errors.jsonl | 新ルール/スキル候補の発見 |
| セッション要約 | sessions.jsonl | パターン分析の入力 |
| ワークフローシーケンス | workflows.jsonl | Skill→Agent の構造分析 |
| サブエージェント完了データ | subagents.jsonl | エージェント戦略分析 |
| グローバルスキル使用プロジェクト | usage-registry.jsonl | cross-PJ 判定 |
| 修正フィードバック | corrections.jsonl | Reflect でルール/CLAUDE.md に反映 |

---

## Layer B: 最適化観測（execution telemetry）

optimize / rl-loop 実行時に自動記録される。

### 記録データ

| データ | 記録先 | 用途 |
|--------|--------|------|
| 変異戦略タグ (`mutation`/`crossover`/`elite`) | result.json の `strategy` フィールド | どの戦略が効くか学習 |
| CoT 評価の reason テキスト | result.json の `cot_reasons` フィールド | なぜそのスコアか理解 |
| 人間却下理由 | history.jsonl の `rejection_reason` フィールド | 「何がダメか」のパターン |

### 実装変更

`Individual` クラスに2フィールド追加:

```python
class Individual:
    # 既存
    content: str
    fitness: float

    # 追加
    strategy: str = ""           # "mutation" / "crossover" / "elite"
    cot_reasons: dict = {}       # {"clarity": "reason...", "completeness": "reason..."}
```

`history.jsonl` に1フィールド追加:

```json
{
  "loop": 1,
  "baseline": 0.62,
  "best": 0.78,
  "accepted": true,
  "rejection_reason": null
}
```

人間却下時にオプションで理由を入力可能。入力しなければ `null`。

### evolve での活用

- **戦略別 fitness 改善幅** → 次回 optimize で有効な戦略の配分を自動調整
- **却下理由の蓄積** → Discover で「避けるべきパターン」として新ルール候補に
- **CoT reason の傾向** → fitness 関数自体の改善材料に

---

## Layer C: ユーザーフィードバック（`/feedback`）

外部ユーザーが rl-anything プラグインに対してフィードバックを送る仕組み。

### コマンド

```
/rl-anything:feedback
```

### フロー

```
1. gh auth status でチェック → 未認証なら案内して中断
2. カテゴリ選択（UX改善 / 機能提案 / バグ / パフォーマンス / その他）
3. ドメイン自動検出（CLAUDE.md から推定）+ 確認
4. スコア変化（result.json / history.jsonl から自動取得、あれば）
5. 良かった点 / 困った点（自由記述）
6. Issue 本文をプレビュー表示
7. ユーザー確認後に gh issue create -R shohu/rl-anything --label feedback
```

### プライバシー保護

Issue 本文に含めない:
- スキルファイルの内容
- ファイルパス
- プロジェクト名
- 環境変数

含めてよい:
- スコア数値
- ドメイン種別
- 世代数 / 集団サイズのパラメータ

### 送信失敗時のフォールバック

`gh issue create` が失敗した場合、フィードバック内容を
`~/.claude/rl-anything/feedback-drafts/` にローカル保存。

---

## データストレージ

```
~/.claude/rl-anything/
├── usage.jsonl           # Layer A: スキル/エージェント使用記録
├── errors.jsonl          # Layer A: ツールエラー
├── sessions.jsonl        # Layer A: セッション要約
├── workflows.jsonl       # Layer A: ワークフローシーケンス
├── subagents.jsonl       # Layer A: サブエージェント完了データ
├── usage-registry.jsonl  # Layer A: グローバルスキル使用レジストリ
├── corrections.jsonl     # Layer A: 修正フィードバック
├── workflow_stats.json   # workflow_analysis.py が出力
├── checkpoint.json       # PreCompact hook で保存される進化状態
├── archive/              # Prune で退避されたアーティファクト
│   ├── skills/
│   └── rules/
├── feedback-drafts/      # ローカル保存フィードバック
└── history/              # evolve 実行履歴
    └── 2026-03-02.json
```

optimize / rl-loop のテレメトリ (Layer B) は既存の `result.json` / `history.jsonl` に追記。

---

## 設計原則

- **async hook のみ** → 開発体験に影響ゼロ
- **JSONL 追記** → 低コスト、後から集計可能
- **環境観測（Layer A）で LLM 呼び出しなし** → 観測フェーズでAPI消費しない
- **最適化観測（Layer B）は既存フローに乗せる** → optimize/rl-loop のデータ拡張のみ
- **フィードバック（Layer C）は完全オプトイン** → ユーザーが明示的に実行した場合のみ
