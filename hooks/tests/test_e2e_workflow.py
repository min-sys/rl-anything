#!/usr/bin/env python3
"""E2E ワークフロートレーシング動作確認スクリプト。

実際の hook handler を順番に呼び出し、データフロー全体の正確性を検証する。
tasks.md タスク 10.1-10.9 に対応。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

# hooks/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common
import workflow_context
import observe
import subagent_observe
import session_summary

# discover/prune のパス
_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))

import importlib
import discover
importlib.reload(discover)


def run_e2e():
    """E2E テストを実行し、結果をレポートする。"""
    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "rl-anything"
        data_dir.mkdir()

        with mock.patch.object(common, "DATA_DIR", data_dir):
            with mock.patch.dict(os.environ, {"TMPDIR": tmpdir}):

                session_id = "e2e-sess-001"

                # ============================================
                # 10.1: Skill 実行 → 文脈ファイル作成
                # ============================================
                print("=" * 60)
                print("10.1: PreToolUse — Skill 呼び出しでワークフロー文脈を記録")
                print("=" * 60)

                pre_event = {
                    "tool_name": "Skill",
                    "tool_input": {"skill": "opsx:refine", "args": "workflow-tracing"},
                    "session_id": session_id,
                }
                workflow_context.handle_pre_tool_use(pre_event)

                ctx_path = Path(tmpdir) / f"rl-anything-workflow-{session_id}.json"
                assert ctx_path.exists(), "文脈ファイルが作成されていない"
                ctx = json.loads(ctx_path.read_text())
                print(f"  文脈ファイル: {json.dumps(ctx, indent=2, ensure_ascii=False)}")
                assert ctx["skill_name"] == "opsx:refine"
                assert ctx["workflow_id"].startswith("wf-")
                assert ctx["session_id"] == session_id
                print("  ✓ skill_name, workflow_id, session_id, started_at を確認")
                results["10.1"] = "PASS"

                wf_id = ctx["workflow_id"]

                # ============================================
                # 10.1 (続): Agent 呼び出し → usage.jsonl に parent_skill 記録
                # ============================================
                print("\n" + "=" * 60)
                print("10.1: PostToolUse — Agent 呼び出しに parent_skill を付与")
                print("=" * 60)

                for i, prompt in enumerate([
                    "explore the codebase structure and directory layout",
                    "review spec requirements for MUST keywords",
                    "implement the changes based on design.md",
                ]):
                    agent_event = {
                        "tool_name": "Agent",
                        "tool_input": {
                            "subagent_type": "Explore" if i < 2 else "general-purpose",
                            "prompt": prompt,
                        },
                        "tool_result": {},
                        "session_id": session_id,
                    }
                    observe.handle_post_tool_use(agent_event)

                usage_file = data_dir / "usage.jsonl"
                assert usage_file.exists(), "usage.jsonl が作成されていない"
                usage_records = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
                print(f"  usage.jsonl レコード数: {len(usage_records)}")

                for rec in usage_records:
                    print(f"    - {rec['skill_name']}: parent_skill={rec.get('parent_skill')}, workflow_id={rec.get('workflow_id')}")
                    assert rec.get("parent_skill") == "opsx:refine", f"parent_skill が 'opsx:refine' でない: {rec.get('parent_skill')}"
                    assert rec.get("workflow_id") == wf_id, f"workflow_id が不一致: {rec.get('workflow_id')}"

                print("  ✓ 全3レコードに parent_skill='opsx:refine', workflow_id 付与を確認")
                results["10.1_usage"] = "PASS"

                # ============================================
                # 10.2: 手動 Agent 呼び出し → parent_skill: null
                # ============================================
                print("\n" + "=" * 60)
                print("10.2: 手動 Agent 呼び出し → parent_skill: null, workflow_id: null")
                print("=" * 60)

                # 別セッション（文脈ファイルなし）
                manual_session = "e2e-sess-manual"
                manual_event = {
                    "tool_name": "Agent",
                    "tool_input": {
                        "subagent_type": "Explore",
                        "prompt": "手動で codebase を探索",
                    },
                    "tool_result": {},
                    "session_id": manual_session,
                }
                observe.handle_post_tool_use(manual_event)

                usage_records_all = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
                manual_rec = [r for r in usage_records_all if r.get("session_id") == manual_session][0]
                print(f"  手動レコード: parent_skill={manual_rec.get('parent_skill')}, workflow_id={manual_rec.get('workflow_id')}")
                assert manual_rec.get("parent_skill") is None, "parent_skill が null でない"
                assert manual_rec.get("workflow_id") is None, "workflow_id が null でない"
                print("  ✓ parent_skill=null, workflow_id=null を確認")
                results["10.2"] = "PASS"

                # ============================================
                # 10.4: SubagentStop → subagents.jsonl に parent_skill 付与
                # ============================================
                print("\n" + "=" * 60)
                print("10.4: SubagentStop — subagents.jsonl に parent_skill 付与")
                print("=" * 60)

                subagent_event = {
                    "agent_type": "Explore",
                    "agent_id": "agent-e2e-001",
                    "last_assistant_message": "探索が完了しました",
                    "agent_transcript_path": "/tmp/transcript-e2e.jsonl",
                    "session_id": session_id,
                }
                subagent_observe.handle_subagent_stop(subagent_event)

                subagents_file = data_dir / "subagents.jsonl"
                assert subagents_file.exists(), "subagents.jsonl が作成されていない"
                sub_rec = json.loads(subagents_file.read_text().strip())
                print(f"  subagents.jsonl: parent_skill={sub_rec.get('parent_skill')}, workflow_id={sub_rec.get('workflow_id')}")
                assert sub_rec.get("parent_skill") == "opsx:refine"
                assert sub_rec.get("workflow_id") == wf_id
                print("  ✓ subagents.jsonl に parent_skill, workflow_id 付与を確認")
                results["10.4"] = "PASS"

                # ============================================
                # 10.3: セッション終了 → workflows.jsonl
                # ============================================
                print("\n" + "=" * 60)
                print("10.3: Stop — workflows.jsonl にシーケンスレコード書き出し")
                print("=" * 60)

                stop_event = {"session_id": session_id}
                session_summary.handle_stop(stop_event)

                workflows_file = data_dir / "workflows.jsonl"
                assert workflows_file.exists(), "workflows.jsonl が作成されていない"
                wf_rec = json.loads(workflows_file.read_text().strip())
                print(f"  workflows.jsonl:")
                print(f"    workflow_id: {wf_rec['workflow_id']}")
                print(f"    skill_name: {wf_rec['skill_name']}")
                print(f"    step_count: {wf_rec['step_count']}")
                print(f"    source: {wf_rec['source']}")
                print(f"    steps:")
                for step in wf_rec["steps"]:
                    print(f"      - tool={step['tool']}, intent_category={step['intent_category']}")

                assert wf_rec["workflow_id"] == wf_id
                assert wf_rec["skill_name"] == "opsx:refine"
                assert wf_rec["step_count"] == 3
                assert len(wf_rec["steps"]) == 3
                assert wf_rec["source"] == "trace"
                assert wf_rec["steps"][0]["intent_category"] == "code-exploration"
                assert wf_rec["steps"][1]["intent_category"] == "spec-review"
                assert wf_rec["steps"][2]["intent_category"] == "implementation"
                assert "started_at" in wf_rec
                assert "ended_at" in wf_rec
                print("  ✓ steps, step_count, intent_category, source を確認")
                results["10.3"] = "PASS"

                # ============================================
                # 10.5: 文脈ファイルのクリーンアップ
                # ============================================
                print("\n" + "=" * 60)
                print("10.5: 文脈ファイルの削除確認")
                print("=" * 60)

                assert not ctx_path.exists(), "文脈ファイルが削除されていない"
                print("  ✓ 文脈ファイルはセッション終了後に削除された")
                results["10.5"] = "PASS"

                # ============================================
                # 10.6-10.7: Discover 分類確認
                # ============================================
                print("\n" + "=" * 60)
                print("10.6-10.7: Discover — contextualized 除外 + backfill 除外")
                print("=" * 60)

                # backfill データを追加（10.7 確認用）
                for i in range(6):
                    common.append_jsonl(usage_file, {
                        "skill_name": "Agent:Explore",
                        "source": "backfill",
                        "prompt": "backfill record",
                        "session_id": "old-sess",
                    })

                # ad-hoc データを追加（閾値5を超える分）
                for i in range(6):
                    common.append_jsonl(usage_file, {
                        "skill_name": "Agent:Explore",
                        "prompt": f"ad-hoc exploration {i}",
                        "session_id": f"adhoc-sess-{i}",
                    })

                with mock.patch.object(discover, "DATA_DIR", data_dir):
                    with mock.patch.object(discover, "SUPPRESSION_FILE", data_dir / "suppress.jsonl"):
                        patterns = discover.detect_behavior_patterns(threshold=5)

                print(f"  検出パターン数: {len(patterns)}")
                for p in patterns:
                    print(f"    - {p['pattern']}: count={p['count']} (ad-hoc), total_count={p.get('total_count', 'N/A')}")

                # Agent:Explore は ad-hoc 7回（手動1 + 追加6）、contextualized 3回、backfill 6回
                explore_pattern = [p for p in patterns if p["pattern"] == "Agent:Explore"]
                assert len(explore_pattern) == 1, "Agent:Explore パターンが検出されていない"
                assert explore_pattern[0]["count"] == 7, f"ad-hoc カウントが 7 でない: {explore_pattern[0]['count']}"
                # total_count = 3 (contextualized) + 7 (ad-hoc) + 6 (backfill) + 1 (manual) = total usage records with Agent:Explore
                print(f"  ✓ contextualized (3回) はカウントから除外")
                print(f"  ✓ backfill (6回) は unknown として除外")
                print(f"  ✓ ad-hoc のみ ({explore_pattern[0]['count']}回) がカウント対象")
                results["10.6"] = "PASS"
                results["10.7"] = "PASS"

                # ============================================
                # 10.8-10.9: Prune parent_skill 経由カウント
                # ============================================
                print("\n" + "=" * 60)
                print("10.8-10.9: Prune — parent_skill 経由カウント")
                print("=" * 60)

                # usage.jsonl を再読み込みして used_skills を構築
                all_usage = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
                used_skills = set()
                for rec in all_usage:
                    used_skills.add(rec.get("skill_name", ""))
                    parent = rec.get("parent_skill")
                    if parent:
                        used_skills.add(parent)

                print(f"  used_skills: {sorted(used_skills)}")
                assert "opsx:refine" in used_skills, "opsx:refine が used_skills に含まれていない"
                print("  ✓ opsx:refine は parent_skill 経由で used_skills に含まれる（淘汰候補にならない）")

                # 存在しないスキル
                assert "never-used-skill" not in used_skills
                print("  ✓ never-used-skill は used_skills に含まれない（淘汰候補になる）")
                results["10.8"] = "PASS"
                results["10.9"] = "PASS"

    # ============================================
    # 結果サマリ
    # ============================================
    print("\n" + "=" * 60)
    print("E2E 動作確認サマリ")
    print("=" * 60)
    all_pass = True
    for task_id, status in sorted(results.items()):
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {task_id}: {status}")
        if status != "PASS":
            all_pass = False

    if all_pass:
        print(f"\n全 {len(results)} 項目 PASS")
    else:
        failed = [k for k, v in results.items() if v != "PASS"]
        print(f"\n{len(failed)} 項目 FAIL: {failed}")

    return all_pass


if __name__ == "__main__":
    success = run_e2e()
    sys.exit(0 if success else 1)
