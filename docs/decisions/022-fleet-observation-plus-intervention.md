# ADR-022: rl-anything を fleet 化する（観測＋介入を同一プラグインに統合）

Date: 2026-04-23
Status: Accepted
Related: Issue #68、PR #83（Phase 1 MVP）、design doc: `~/.gstack/projects/min-sys-rl-anything/matsukaze-takashi-main-design-20260422-140954.md`

## Context

rl-anything は個別 PJ に対する「自律進化 / フィードバック / 直接パッチ最適化」の3柱で設計されてきたが、日常運用で「`cd pj && claude /rl-anything:audit` を 5-6 PJ 繰り返すのが面倒 → 結果ほとんどの PJ で rl-anything が未導入のまま放置」という pain が顕在化した（P1: "混ざっている"）。SPEC.md L75 の記載（「PR #38 が cross-project audit の基盤」）は実態と異なり、PR #38 は FileChanged hook + MEMORY.md + userConfig の別内容だった。横串の観測・介入基盤は未実装である。

office-hours セッションで 3 アプローチを比較した:

| Approach | 範囲 | Size / Risk | ハイライト |
|----------|------|-------------|-----------|
| A: MINIMAL VIABLE | `bin/rl-fleet status` のみ、段階移行 | S / Low | 失敗ゼロリスク、Phase 2 再判断 |
| **B: FULL FLEET（採用）** | `rl-fleet {status,evolve-all,reflect-all,audit-all}` を Phase 分けで全実装 | L / Med-High（Phase 内訳: P1=S/Low, P2=M/Low-Med, P3=M/Med-High） | pain 根本解決、単一プラグイン |
| C: LATERAL（自走型） | SessionStart/Stop hook で各 PJ が自分を維持 | M / Low | 手動実行 pain は消えるが横串可視性が弱い |

Office-hours 推奨は A → B 段階移行（YAGNI + リスク最小化）だった。reviewer 2 名（senior-engineer + rl-anything-advisor）も「Phase 2 以降は別プラグイン化検討ライン」を推奨した。

## Decision

**Approach B（FULL FLEET）を採用し、rl-anything の「4 本目の柱」として fleet 観測・介入を正式追加する。**

両 reviewer の慎重ラインを越える選択のため、**必須ガード**を Phase 別に組み込む:

### Phase 1 から適用（本 PR で実装済み）
1. **冪等性**: `status` は副作用ゼロ（subprocess 読み取り + `fleet-runs/<ts>.jsonl` 追記のみ）
2. **subprocess timeout**: 各 PJ の audit 呼び出しは 10 秒 timeout。TIMEOUT と STALE は区別表示
3. **error isolation**: 1 PJ の returncode 非ゼロ / 破損 JSON で他 PJ の処理を停止しない。該当 PJ は `AUDIT_ERROR` 表示
4. **settings.json retry**: parse 失敗時は 100ms sleep 後 1 回 retry。それでも駄目なら全 PJ を NOT_ENABLED 表示
5. **auth コンテキスト**: fleet は read-only 操作のみ。git push / gh API を呼ぶ PJ 操作は対象外
6. **subprocess grandchildren kill**: `start_new_session=True` + `os.killpg(SIGTERM→SIGKILL)` で timeout 時の孤児プロセスを確実に終了（post-review 対応）
7. **symlink ガード**: `enumerate_projects` は symlink を除外し任意パスへの audit trampoline を防ぐ（post-review 対応）
8. **duplicate basename ガード**: 同一 basename の PJ は `growth-state-<basename>.json` cache 衝突するため、`collect_fleet_status` で事前検知し該当 PJ を `AUDIT_ERROR` 扱い（post-review 対応）

### Phase 2 から追加
9. **最大並列数制限**: `--parallel 2` デフォルト（`ThreadPoolExecutor`）
10. **per-PJ abort**: 1 PJ 失敗時は in-flight PJ は自然完了 → 新規 PJ 投入を停止

### Phase 3 から追加
11. **dry-run default**: `evolve-all` / `reflect-all` は `--apply` なしで dry-run 表示のみ
12. **PJ 単位 opt-in**: 各対象 PJ に `.claude/fleet-opt-in` 空マーカーファイルを要求（誤爆防止）

## Alternatives

### Approach A — MINIMAL VIABLE のみ（段階移行）
- **棄却理由**: "面倒" pain の半分しか解決しない。観測のみでは介入までのフリクションが残る。Reviewer 推奨だったが、pain の実体を知るユーザー自身が「rl-anything ごと拡張」を明示選択した
- **保留した良さ**: Phase 1 単体で価値を提供できる構造は採用した。Phase 1 完了後に Phase 2/3 を再審議するゲートを明記

### Approach C — LATERAL（SessionStart/Stop hook で自走）
- **棄却理由**: 「手動実行が面倒」の根本は直撃するが、横串可視性が弱く休眠 PJ の検出ができない。fleet 構想の核（観測＋可視化）とズレる
- **残す余地**: 自走型 hook は Phase 3 以降の補完として将来検討可能

### 別プラグイン化（Reviewer 推奨ライン）
- **棄却理由**: 観測層と介入層の配布・バージョニングを分けるとユーザーが追跡すべき表面積が増える。単一プラグインで必須ガードを初期実装することでリスク抑制を選択
- **補償策**: 必須ガード 1-12 を Phase 別に厳格適用。Phase 3 の介入層は dry-run default + opt-in マーカー必須で二重防御

## Consequences

**肯定側**
- 6 PJ の env_score / growth level / 導入状況が単一コマンドで可視化
- 未導入 PJ が可視化されることで rl-anything 普及の内部フリクションが減少
- 「全 PJ を一括で最新の gstack / CC 新機能に追従させる」が将来視野に入る
- rl-anything が「per-PJ 自己進化」から「fleet 自己進化」に昇格し、柱構造が 3 → 4 本化

**否定側・リスク**
- 副作用拡散: Phase 3 の介入層は複数 PJ を同時に変更する。rollback 設計の複雑化
- テスト 2 倍: per-PJ テスト + fleet 全体テストが両方必要
- 配布単位の肥大化: 観測を使わないユーザーも fleet コードを受け取る
- **audit.py の duckdb バグ**: Phase 1 実装中に発見（`usage.jsonl` クエリで `Conversion Error: Malformed JSON`）。fleet は `AUDIT_ERROR` として surface するが、実運用時に ENABLED PJ の env_score が表示されないため、別 issue で根本修正を追跡する必要あり

**観測可能性**
- fleet-run ログ（`<DATA_DIR>/fleet-runs/<ts>.jsonl`）で全実行の状態スナップショットが残り、介入層（Phase 3）の前後比較が可能
- Phase 1 完了時点で perf を実測し（目標 3s / 6 PJ）、超過時は `growth-state-<slug>.json` 直読みキャッシュで短縮するフォローアップを明記

## 実装ステータス

- **Phase 1 (PR #83)**: `bin/rl-fleet status` + `scripts/lib/fleet.py` + 33 unit tests — merged
- **Phase 2**: `audit-all --parallel` + global rules × PJ CLAUDE.md 整合性チェック — 未着手
- **Phase 3**: `reflect-all` / `evolve-all` dry-run + `--apply` + `rollback <ts>` — 未着手
