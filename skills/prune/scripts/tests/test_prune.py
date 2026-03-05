#!/usr/bin/env python3
"""classify_artifact_origin と prune プラグインスキル除外のテスト。"""
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))

import audit
import prune


class TestClassifyArtifactOrigin:
    """classify_artifact_origin のユニットテスト。"""

    def test_plugin_origin(self):
        """プラグインキャッシュ配下のスキルは plugin と判定される。"""
        path = Path.home() / ".claude" / "plugins" / "cache" / "rl-anything" / "rl-anything" / "0.4.0" / ".claude" / "skills" / "optimize" / "SKILL.md"
        assert audit.classify_artifact_origin(path) == "plugin"

    def test_plugin_origin_with_tilde(self):
        """チルダ付きパスも正しく展開されて plugin と判定される。"""
        path = Path("~/.claude/plugins/cache/rl-anything/rl-anything/0.4.0/.claude/skills/optimize/SKILL.md")
        assert audit.classify_artifact_origin(path) == "plugin"

    def test_global_origin(self):
        """グローバルスキルは global と判定される。"""
        path = Path.home() / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert audit.classify_artifact_origin(path) == "global"

    def test_custom_origin(self):
        """プロジェクトローカルのスキルは custom と判定される。"""
        path = Path("/Users/user/project/.claude/skills/my-skill/SKILL.md")
        assert audit.classify_artifact_origin(path) == "custom"

    def test_rules_always_custom(self):
        """ルールは常に custom と判定される。"""
        path = Path("/Users/user/project/.claude/rules/my-rule.md")
        assert audit.classify_artifact_origin(path) == "custom"

    def test_env_override(self):
        """CLAUDE_PLUGINS_DIR 環境変数でプラグインパスをオーバーライドできる。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGINS_DIR": "/custom/plugins"}):
            path = Path("/custom/plugins/rl-anything/SKILL.md")
            assert audit.classify_artifact_origin(path) == "plugin"

    def test_env_override_does_not_match_default(self):
        """環境変数設定時、デフォルトのプラグインパスは plugin と判定されない。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGINS_DIR": "/custom/plugins"}):
            path = Path.home() / ".claude" / "plugins" / "cache" / "test" / "SKILL.md"
            assert audit.classify_artifact_origin(path) == "custom"

    def test_plugin_installed_skill_in_project_dir(self, tmp_path):
        """プラグインがインストールしたスキルがプロジェクト .claude/skills/ にある場合 plugin と判定される。"""
        # プラグインの installPath にスキルディレクトリを作成
        install_path = tmp_path / "plugins" / "cache" / "my-plugin" / "1.0.0"
        plugin_skills = install_path / ".claude" / "skills" / "plugin-skill-a"
        plugin_skills.mkdir(parents=True)
        (plugin_skills / "SKILL.md").write_text("# test")

        # installed_plugins.json をモック
        installed_plugins = {
            "version": 2,
            "plugins": {
                "my-plugin@marketplace": [
                    {"installPath": str(install_path)}
                ]
            },
        }
        # キャッシュをリセット
        audit._plugin_skill_map_cache = None
        installed_path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
        with mock.patch.object(Path, "read_text", return_value=json.dumps(installed_plugins)):
            with mock.patch.object(Path, "is_dir", return_value=True):
                audit._plugin_skill_map_cache = None
        # 直接キャッシュに dict をセット
        audit._plugin_skill_map_cache = {"plugin-skill-a": "my-plugin", "plugin-skill-b": "my-plugin"}
        try:
            # プロジェクト .claude/skills/ 配下のスキルが plugin 判定される
            project_skill = Path("/Users/user/my-project/.claude/skills/plugin-skill-a/SKILL.md")
            assert audit.classify_artifact_origin(project_skill) == "plugin"

            # 名前が一致しないスキルは custom のまま
            custom_skill = Path("/Users/user/my-project/.claude/skills/my-custom-skill/SKILL.md")
            assert audit.classify_artifact_origin(custom_skill) == "custom"
        finally:
            audit._plugin_skill_map_cache = None

    def test_plugin_installed_skill_name_matching_only_in_claude_skills(self):
        """プラグインスキル名マッチは .claude/skills/ 配下のパスにのみ適用される。"""
        audit._plugin_skill_map_cache = {"optimize": "some-plugin"}
        try:
            # .claude/skills/ 配下でない場所にある同名ディレクトリは custom のまま
            random_path = Path("/Users/user/project/src/optimize/SKILL.md")
            assert audit.classify_artifact_origin(random_path) == "custom"
        finally:
            audit._plugin_skill_map_cache = None

    def test_installed_plugins_json_missing(self):
        """installed_plugins.json が存在しない場合、フォールバックで空セットを返す。"""
        audit._plugin_skill_map_cache = None
        with mock.patch("pathlib.Path.read_text", side_effect=OSError("No such file")):
            names = audit._load_plugin_skill_names()
            assert names == frozenset()
        audit._plugin_skill_map_cache = None

    def test_installed_plugins_json_malformed(self):
        """installed_plugins.json が不正な JSON の場合、フォールバックで空セットを返す。"""
        audit._plugin_skill_map_cache = None
        with mock.patch("pathlib.Path.read_text", return_value="not valid json"):
            names = audit._load_plugin_skill_names()
            assert names == frozenset()
        audit._plugin_skill_map_cache = None

    def test_plugin_skill_names_cache(self):
        """_load_plugin_skill_names のキャッシュが動作する。"""
        audit._plugin_skill_map_cache = {"cached-skill": "cached-plugin"}
        try:
            names = audit._load_plugin_skill_names()
            assert "cached-skill" in names
        finally:
            audit._plugin_skill_map_cache = None

    def test_project_skill_with_plugin_name_classified_as_plugin_in_prune(self, tmp_path):
        """プロジェクト .claude/skills/ 配下のプラグインインストール済みスキルが prune で plugin_unused に分類される。"""
        audit._plugin_skill_map_cache = {"openspec-apply-change": "openspec"}
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        try:
            with mock.patch.object(audit, "DATA_DIR", data_dir):
                usage_file = data_dir / "usage.jsonl"
                usage_file.write_text("")

                # プロジェクトの .claude/skills/ にあるがプラグイン由来のスキル
                plugin_installed = Path("/Users/user/project/.claude/skills/openspec-apply-change/SKILL.md")
                custom_skill = Path("/Users/user/project/.claude/skills/my-custom-skill/SKILL.md")

                artifacts = {
                    "skills": [plugin_installed, custom_skill],
                    "rules": [],
                }

                zero, plugin_unused = prune.detect_zero_invocations(artifacts, days=30)

                # プラグインインストール済みスキルは plugin_unused
                plugin_names = [p["skill_name"] for p in plugin_unused]
                assert "openspec-apply-change" in plugin_names

                # カスタムスキルは zero_invocations
                zero_names = [z["skill_name"] for z in zero]
                assert "my-custom-skill" in zero_names
                assert "openspec-apply-change" not in zero_names
        finally:
            audit._plugin_skill_map_cache = None


class TestExtractSkillSummary:
    """extract_skill_summary のユニットテスト。"""

    def test_extract_from_skill_md(self, tmp_path):
        """SKILL.md から description を抽出する。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: my-skill\ndescription: A useful skill\n---\n# Body")
        assert prune.extract_skill_summary(skill_md) == "A useful skill"

    def test_extract_from_directory(self, tmp_path):
        """ディレクトリパスからも SKILL.md を見つけて抽出する。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Dir test\n---\n")
        assert prune.extract_skill_summary(skill_dir) == "Dir test"

    def test_extract_nonexistent(self, tmp_path):
        """存在しないパスでは空文字を返す。"""
        assert prune.extract_skill_summary(tmp_path / "nonexistent" / "SKILL.md") == ""

    def test_extract_multiline_description(self, tmp_path):
        """multiline description では1行目のみ返す。"""
        skill_dir = tmp_path / "multi"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: multi\ndescription: |\n  Line one.\n  Line two.\n---\n"
        )
        assert prune.extract_skill_summary(skill_dir / "SKILL.md") == "Line one."


class TestSuggestRecommendation:
    """suggest_recommendation のユニットテスト。"""

    def test_archive_keyword_debug(self):
        """name に "debug" → archive推奨。"""
        info = {"skill_name": "debug-helper", "description": "", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "archive推奨"

    def test_archive_keyword_temp(self):
        """description に "temp" → archive推奨。"""
        info = {"skill_name": "foo", "description": "A temp script", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "archive推奨"

    def test_archive_keyword_hotfix(self):
        """name に "hotfix" → archive推奨。"""
        info = {"skill_name": "hotfix-123", "description": "", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "archive推奨"

    def test_keep_keyword_daily(self):
        """description に "daily" → keep推奨。"""
        info = {"skill_name": "report", "description": "daily report generator", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "keep推奨"

    def test_keep_keyword_pipeline(self):
        """description に "pipeline" → keep推奨。"""
        info = {"skill_name": "ci", "description": "CI pipeline helper", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "keep推奨"

    def test_keep_by_trigger_count(self):
        """Trigger が3個以上 → keep推奨。"""
        info = {"skill_name": "foo", "description": "generic", "trigger_count": 3}
        assert prune.suggest_recommendation(info) == "keep推奨"

    def test_unknown(self):
        """いずれにも該当しない → 要確認。"""
        info = {"skill_name": "foo", "description": "something", "trigger_count": 1}
        assert prune.suggest_recommendation(info) == "要確認"

    def test_archive_takes_priority(self):
        """archive と keep の両方のキーワードがある場合、archive が優先。"""
        info = {"skill_name": "debug-daily", "description": "", "trigger_count": 0}
        assert prune.suggest_recommendation(info) == "archive推奨"


class TestMergeDuplicates:
    """merge_duplicates のユニットテスト。"""

    @pytest.fixture
    def patch_data_dir(self, tmp_path):
        """テスト用の DATA_DIR を作成。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        with mock.patch.object(audit, "DATA_DIR", data_dir):
            yield data_dir

    @pytest.fixture
    def project_with_skills(self, tmp_path):
        """テスト用プロジェクトとスキルを作成。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # スキルを作成
        for name in ["alpha", "beta", "gamma", "delta"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}")

        (project_dir / ".claude" / "rules").mkdir(parents=True)
        return project_dir

    def _write_usage(self, data_dir, entries):
        """usage.jsonl にエントリを書き込むヘルパー。"""
        lines = [json.dumps(e) for e in entries]
        (data_dir / "usage.jsonl").write_text("\n".join(lines))

    def test_primary_by_usage_count(self, patch_data_dir, project_with_skills):
        """使用回数が多いスキルが primary になる。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "beta", "timestamp": now},
        ])

        primary, secondary, p_count, s_count = prune.determine_primary("alpha", "beta")
        assert primary == "alpha"
        assert secondary == "beta"
        assert p_count == 3
        assert s_count == 1

    def test_primary_alphabetical_on_equal_count(self, patch_data_dir, project_with_skills):
        """使用回数が同じ場合、アルファベット順で早い方が primary。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "beta", "timestamp": now},
            {"skill_name": "gamma", "timestamp": now},
        ])

        primary, secondary, p_count, s_count = prune.determine_primary("gamma", "beta")
        assert primary == "beta"
        assert secondary == "gamma"
        assert p_count == 1
        assert s_count == 1

    def test_pinned_skill_skipped(self, patch_data_dir, project_with_skills):
        """pin されたスキルのペアは skipped_pinned になる。"""
        # alpha に .pin を作成
        pin_file = project_with_skills / ".claude" / "skills" / "alpha" / ".pin"
        pin_file.write_text("")

        self._write_usage(patch_data_dir, [])

        duplicate_candidates = [
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                "threshold": 0.80,
            }
        ]

        result = prune.merge_duplicates(
            duplicate_candidates, project_dir=str(project_with_skills)
        )
        assert len(result["merge_proposals"]) == 1
        assert result["merge_proposals"][0]["status"] == "skipped_pinned"

    def test_plugin_skill_skipped(self, patch_data_dir, project_with_skills):
        """プラグイン由来スキルのペアは skipped_plugin になる。"""
        self._write_usage(patch_data_dir, [])

        audit._plugin_skill_map_cache = {"alpha": "some-plugin"}
        try:
            duplicate_candidates = [
                {
                    "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                    "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                    "threshold": 0.80,
                }
            ]

            result = prune.merge_duplicates(
                duplicate_candidates, project_dir=str(project_with_skills)
            )
            assert len(result["merge_proposals"]) == 1
            assert result["merge_proposals"][0]["status"] == "skipped_plugin"
        finally:
            audit._plugin_skill_map_cache = None

    def test_reorganize_dedup(self, patch_data_dir, project_with_skills):
        """同じペアが duplicate_candidates と reorganize の両方に含まれる場合、1回だけ処理される。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
        ])

        duplicate_candidates = [
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                "threshold": 0.80,
            }
        ]
        reorganize_merge_groups = [
            {"skills": ["alpha", "beta"]}
        ]

        result = prune.merge_duplicates(
            duplicate_candidates,
            reorganize_merge_groups=reorganize_merge_groups,
            project_dir=str(project_with_skills),
        )
        # 同じペアなので 1 件のみ
        assert result["total_proposals"] == 1
        assert len(result["merge_proposals"]) == 1

    def test_suppressed_pair_skipped(self, patch_data_dir, project_with_skills):
        """suppression 済みペアが skipped_suppressed になる。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "beta", "timestamp": now},
        ])

        # suppression ファイルに alpha::beta を登録
        suppression_file = patch_data_dir / "discover-suppression.jsonl"
        suppression_file.write_text(
            json.dumps({"pattern": "alpha::beta", "type": "merge"}) + "\n"
        )

        duplicate_candidates = [
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                "threshold": 0.80,
            }
        ]

        with mock.patch("discover.SUPPRESSION_FILE", suppression_file):
            result = prune.merge_duplicates(
                duplicate_candidates, project_dir=str(project_with_skills)
            )
        assert len(result["merge_proposals"]) == 1
        assert result["merge_proposals"][0]["status"] == "skipped_suppressed"

    def test_unsuppressed_pair_proposed(self, patch_data_dir, project_with_skills):
        """suppression 未登録ペアが従来通り proposed になる。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "beta", "timestamp": now},
        ])

        # suppression ファイルは空（または別のペアのみ）
        suppression_file = patch_data_dir / "discover-suppression.jsonl"
        suppression_file.write_text(
            json.dumps({"pattern": "gamma::delta", "type": "merge"}) + "\n"
        )

        duplicate_candidates = [
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                "threshold": 0.80,
            }
        ]

        with mock.patch("discover.SUPPRESSION_FILE", suppression_file):
            result = prune.merge_duplicates(
                duplicate_candidates, project_dir=str(project_with_skills)
            )
        assert len(result["merge_proposals"]) == 1
        assert result["merge_proposals"][0]["status"] == "proposed"

    def test_mixed_suppressed_and_proposed(self, patch_data_dir, project_with_skills):
        """suppressed ペアと非 suppressed ペアが混在する結合テスト。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "beta", "timestamp": now},
            {"skill_name": "gamma", "timestamp": now},
            {"skill_name": "delta", "timestamp": now},
        ])

        # alpha::beta のみ suppression 登録
        suppression_file = patch_data_dir / "discover-suppression.jsonl"
        suppression_file.write_text(
            json.dumps({"pattern": "alpha::beta", "type": "merge"}) + "\n"
        )

        duplicate_candidates = [
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "alpha" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "beta" / "SKILL.md"),
                "threshold": 0.80,
            },
            {
                "path_a": str(project_with_skills / ".claude" / "skills" / "gamma" / "SKILL.md"),
                "path_b": str(project_with_skills / ".claude" / "skills" / "delta" / "SKILL.md"),
                "threshold": 0.80,
            },
        ]

        with mock.patch("discover.SUPPRESSION_FILE", suppression_file):
            result = prune.merge_duplicates(
                duplicate_candidates, project_dir=str(project_with_skills)
            )
        assert result["total_proposals"] == 2
        statuses = {p["primary"]["skill_name"] + "::" + p["secondary"]["skill_name"]: p["status"]
                     for p in result["merge_proposals"]}
        # alpha::beta は suppressed
        ab_key = next(k for k in statuses if "alpha" in k and "beta" in k)
        assert statuses[ab_key] == "skipped_suppressed"
        # gamma::delta は proposed
        gd_key = next(k for k in statuses if "gamma" in k and "delta" in k)
        assert statuses[gd_key] == "proposed"

    def test_reorganize_pairs_filtered_by_similarity(self, patch_data_dir, project_with_skills):
        """reorganize 由来ペアが類似度フィルタで skipped_low_similarity になる。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._write_usage(patch_data_dir, [
            {"skill_name": "alpha", "timestamp": now},
            {"skill_name": "beta", "timestamp": now},
            {"skill_name": "gamma", "timestamp": now},
        ])

        reorganize_merge_groups = [
            {"skills": ["alpha", "beta", "gamma"]}
        ]

        # filter_merge_group_pairs をモックして alpha-beta のみ通過させる
        with mock.patch("prune.filter_merge_group_pairs") as mock_filter:
            mock_filter.return_value = [frozenset(["alpha", "beta"])]
            result = prune.merge_duplicates(
                [],
                reorganize_merge_groups=reorganize_merge_groups,
                project_dir=str(project_with_skills),
            )

        # alpha-beta は proposed、alpha-gamma と beta-gamma は skipped_low_similarity
        statuses = {}
        for p in result["merge_proposals"]:
            key = p["primary"]["skill_name"] + "::" + p["secondary"]["skill_name"]
            statuses[key] = p["status"]

        ab_key = next(k for k in statuses if "alpha" in k and "beta" in k)
        assert statuses[ab_key] == "proposed"

        skipped = [p for p in result["merge_proposals"] if p["status"] == "skipped_low_similarity"]
        assert len(skipped) == 2  # alpha-gamma, beta-gamma

    def test_run_prune_includes_merge_result(self, patch_data_dir, tmp_path):
        """run_prune の戻り値に merge_result キーが存在する。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude" / "skills").mkdir(parents=True)
        (project_dir / ".claude" / "rules").mkdir(parents=True)

        (patch_data_dir / "usage.jsonl").write_text("")

        result = prune.run_prune(str(project_dir))
        assert "merge_result" in result
        assert "merge_proposals" in result["merge_result"]
        assert "total_proposals" in result["merge_result"]


class TestCleanupCorrections:
    """cleanup_corrections のユニットテスト。"""

    @pytest.fixture
    def patch_data_dir(self, tmp_path):
        """テスト用の DATA_DIR を作成（audit と prune 両方をパッチ）。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        with mock.patch.object(audit, "DATA_DIR", data_dir), \
             mock.patch("prune.DATA_DIR", data_dir):
            yield data_dir

    def _make_correction(self, reflect_status="pending", decay_days=90, age_days=0):
        """テスト用 correction レコードを生成する。"""
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
        return json.dumps({
            "correction_type": "test",
            "matched_patterns": ["test"],
            "message": "test message",
            "last_skill": "my-skill",
            "confidence": 0.70,
            "decay_days": decay_days,
            "sentiment": "negative",
            "routing_hint": "correction",
            "guardrail": False,
            "reflect_status": reflect_status,
            "extracted_learning": "",
            "project_path": "/test",
            "timestamp": ts,
            "session_id": "sess-001",
            "source": "backfill",
        })

    def test_expired_applied_removed(self, patch_data_dir):
        """decay_days 超過の applied レコードが削除される。"""
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            self._make_correction(reflect_status="applied", decay_days=30, age_days=60) + "\n"
        )

        result = prune.cleanup_corrections()
        assert result["removed"] == 1
        assert result["kept"] == 0

    def test_expired_skipped_removed(self, patch_data_dir):
        """decay_days 超過の skipped レコードが削除される。"""
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            self._make_correction(reflect_status="skipped", decay_days=30, age_days=60) + "\n"
        )

        result = prune.cleanup_corrections()
        assert result["removed"] == 1
        assert result["kept"] == 0

    def test_pending_preserved(self, patch_data_dir):
        """pending レコードは decay_days 超過でも削除されない。"""
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            self._make_correction(reflect_status="pending", decay_days=30, age_days=60) + "\n"
        )

        result = prune.cleanup_corrections()
        assert result["removed"] == 0
        assert result["kept"] == 1

    def test_not_expired_preserved(self, patch_data_dir):
        """decay_days 未超過のレコードは削除されない。"""
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            self._make_correction(reflect_status="applied", decay_days=90, age_days=10) + "\n"
        )

        result = prune.cleanup_corrections()
        assert result["removed"] == 0
        assert result["kept"] == 1

    def test_mixed_records(self, patch_data_dir):
        """複数レコードが混在する場合の正しい処理。"""
        corrections_file = patch_data_dir / "corrections.jsonl"
        lines = [
            self._make_correction(reflect_status="applied", decay_days=30, age_days=60),  # 削除
            self._make_correction(reflect_status="skipped", decay_days=30, age_days=60),  # 削除
            self._make_correction(reflect_status="pending", decay_days=30, age_days=60),  # 保持
            self._make_correction(reflect_status="applied", decay_days=90, age_days=10),  # 保持
        ]
        corrections_file.write_text("\n".join(lines) + "\n")

        result = prune.cleanup_corrections()
        assert result["removed"] == 2
        assert result["kept"] == 2

    def test_no_file(self, patch_data_dir):
        """corrections.jsonl が存在しない場合。"""
        result = prune.cleanup_corrections()
        assert result["removed"] == 0
        assert result["kept"] == 0


class TestPrunePluginExclusion:
    """プラグインスキルが淘汰対象から除外されるテスト。"""

    @pytest.fixture
    def patch_data_dir(self, tmp_path):
        """テスト用の DATA_DIR を作成。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        with mock.patch.object(audit, "DATA_DIR", data_dir):
            yield data_dir

    def test_plugin_skill_excluded_from_zero_invocations(self, patch_data_dir):
        """プラグイン由来スキルは zero_invocations に含まれない。"""
        plugin_path = Path.home() / ".claude" / "plugins" / "cache" / "test-plugin" / "v1" / ".claude" / "skills" / "my-plugin-skill" / "SKILL.md"
        custom_path = Path("/Users/user/project/.claude/skills/my-custom-skill/SKILL.md")

        artifacts = {
            "skills": [plugin_path, custom_path],
            "rules": [],
        }

        # 空の usage.jsonl を作成（両方とも未使用）
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text("")

        zero, plugin_unused = prune.detect_zero_invocations(artifacts, days=30)

        # カスタムスキルは zero_invocations に含まれる
        zero_names = [z["skill_name"] for z in zero]
        assert "my-custom-skill" in zero_names

        # プラグインスキルは zero_invocations に含まれない
        assert "my-plugin-skill" not in zero_names

        # プラグインスキルは plugin_unused に含まれる
        plugin_names = [p["skill_name"] for p in plugin_unused]
        assert "my-plugin-skill" in plugin_names

    def test_run_prune_has_plugin_unused_key(self, patch_data_dir, tmp_path):
        """run_prune の戻り値に plugin_unused キーが存在する。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".claude" / "skills").mkdir(parents=True)
        (project_dir / ".claude" / "rules").mkdir(parents=True)

        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text("")

        result = prune.run_prune(str(project_dir))
        assert "plugin_unused" in result
        assert isinstance(result["plugin_unused"], list)
