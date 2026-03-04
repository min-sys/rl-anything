## Context

v0.15.5 で audit に Memory Health（パス存在チェック + 肥大化警告）を追加したが、「MEMORY の記述内容がコードベースの実態と整合しているか」は検証できない。docs-platform で full-regen が差分更新に最適化済みなのに MEMORY に未反映 → AI がフルリジェネ前提でコスト試算する事故が発生。Claude Code Max（サブスク）なら LLM コストを気にせず検証できるため、LLM ベースのセマンティック検証を導入する。

現在の関連コンポーネント:
- `skills/audit/scripts/audit.py`: `build_memory_health_section()` — ルールベース検証
- `scripts/reflect_utils.py`: `read_auto_memory()`, `read_all_memory_entries()` — MEMORY 読み取り
- `.claude/skills/openspec-archive-change/SKILL.md`: archive ワークフロー定義

## Goals / Non-Goals

**Goals:**
- MEMORY の各セクションをコードベースの実態と LLM で突合し、陳腐化・誤解リスクを検出する
- openspec archive 時に MEMORY 更新ドラフトを自動生成し、知識の断片化を防止する
- project auto-memory と global memory の両方を検証対象にする

**Non-Goals:**
- MEMORY の自動書き換え（必ずユーザー承認を経る）
- LLM 以外の手法での意味的検証（精度が不十分）
- root CLAUDE.md（`./CLAUDE.md`）、ローカル rules（`.claude/rules/`）の内容検証
- Mem0 や外部メモリ管理ツールの導入

## Decisions

### D1: LLM 検証の実行方式 — SKILL.md のステップとして実行

**選択**: audit の SKILL.md に Step として LLM 検証を追加し、Claude Code 自身が LLM として検証を実行する。
**却下案**: audit.py 内で subprocess や API で LLM を呼ぶ → Claude Code Max の場合、自分自身が LLM なのでわざわざ API を叩く必要がない。audit.py はデータ収集（MEMORY セクション抽出 + コードベース grep 結果の収集）に徹し、Claude Code が SKILL.md のステップに従って判断する。

**理由**:
- Claude Code Max はサブスクで LLM コストゼロ → 自身のコンテキストで直接検証するのが最もシンプル
- audit.py に LLM 依存を入れるとテストが困難になる
- スキルのステップとして定義すれば、検証ロジックの変更が SKILL.md の編集だけで済む

### D2: MEMORY セクション抽出 — reflect_utils.py にセクション分割、audit.py にコンテキスト収集

**選択**: セクション分割ヘルパー `split_memory_sections(content, file_path)` を `scripts/reflect_utils.py` に配置し、audit.py と archive-memory-sync 両方から利用可能にする。コンテキスト収集 `build_memory_verification_context()` は audit.py に追加。MEMORY の各セクション（`## ` 見出し単位）を分割し、各セクションのキーワードで `grep -r` した結果（関連ファイルのスニペット）を収集して、検証用コンテキストを構造化 JSON で出力する。

**構造**:
```json
{
  "sections": [
    {
      "file": "MEMORY.md",
      "heading": "doc-ci-cd-pipeline",
      "content": "- full-regen は差分更新済み ...",
      "line_range": [11, 19],
      "codebase_evidence": [
        {"file": "doc-full-regen.yml", "snippet": "...git diff based..."},
        {"file": "detect-changes/action.yml", "snippet": "..."}
      ],
      "archive_mentions": ["optimize-fullregen-cost", "optimize-doc-regen"]
    }
  ]
}
```

### D3: archive-memory-sync — SKILL.md のステップとして追加

**選択**: openspec-archive-change の SKILL.md に Step 4.5（Memory Sync）を追加。archive 対象の proposal.md を読み取り、現在の MEMORY.md と突合して更新ドラフトを提示する。ユーザー承認後に MEMORY を更新。

**却下案**: 別の独立スキルにする → archive ワークフローの中で自然に実行されるべきで、別スキルだと忘れられるリスクがある。

### D4: global memory の検証方法

**選択**: 既存の `read_all_memory_entries()` を利用し、`tier == "global"` でフィルタして global memory を取得する。新規関数は追加せず、DRY 原則を維持する。audit 実行時の PJ コンテキストで検証する（global memory はどの PJ でも共通だが、検証はそのときのコードベースに対して行う）。

**却下案**: `read_global_memory()` を reflect_utils.py に新規追加 → `read_all_memory_entries()` が既に 8 層メモリ（global 含む）を `{tier, path, content}` で返しており、`tier == "global"` フィルタで同等の結果が得られる。DRY 違反になるため不採用。

### D5: 検証結果の表現 — 3段階判定

**選択**: 各 MEMORY セクションに対して以下の3段階で判定を出力:
- `CONSISTENT`: コードベースと整合している
- `MISLEADING`: 正確だが誤解を招く表現がある（書き換え案を提示）
- `STALE`: コードベースと矛盾している（更新/削除を推奨）

## Risks / Trade-offs

**LLM 判定のばらつき** → SKILL.md のプロンプトに具体的な判定基準（チェックリスト）を含める。判定に迷う場合は MISLEADING 寄りに判定し、ユーザーに確認を促す。

**コンテキストウィンドウの圧迫** → MEMORY セクション + codebase_evidence を全件一度に流すとコンテキストを圧迫する。セクションごとに逐次検証し、結果をサマリーとして蓄積する。

**archive スキルの肥大化** → Memory Sync ステップは5行程度の追加で、既存のフローを壊さない。ユーザーがスキップ可能にする。

**global memory の false positive** → global memory は汎用的な記述が多く、特定 PJ のコードベースと突合すると「見つからない」になりやすい。global memory は「PJ 固有の記述がある場合のみ」チェック対象にする。

## Open Questions

- archive-memory-sync で MEMORY を更新した場合、git commit の対象にすべきか？（auto-memory は .gitignore されている）
