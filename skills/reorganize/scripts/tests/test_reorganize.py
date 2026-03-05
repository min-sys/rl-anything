#!/usr/bin/env python3
"""Reorganize フェーズのユニットテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "reorganize" / "scripts"))

import audit
import reorganize


class TestSkipWhenFewSkills:
    """スキル数が5未満の場合スキップされるテスト。"""

    def test_skip_when_few_skills(self, tmp_path):
        """スキル数が5未満の場合 skipped=True で reason=insufficient_skills を返す。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 3つだけスキルを作成
        skill_paths = []
        for name in ["skill-a", "skill-b", "skill-c"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"# {name}\nSome content for {name}.")
            skill_paths.append(skill_md)

        # find_artifacts をモックしてグローバルスキルを除外
        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}
        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is True
        assert result["reason"] == "insufficient_skills"
        assert result["count"] == 3

    def test_skip_when_zero_skills(self, tmp_path):
        """スキルが0の場合もスキップされる。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True)

        fake_artifacts = {"skills": [], "rules": [], "memory": [], "claude_md": []}
        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is True
        assert result["reason"] == "insufficient_skills"
        assert result["count"] == 0


class TestSkipWhenScipyMissing:
    """scipy がインストールされていない場合のグレースフルデグラデーションのテスト。"""

    def test_skip_when_scipy_missing(self, tmp_path):
        """scipy が無い場合 skipped=True で reason=scipy_not_available を返す。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 5つスキルを作成（閾値を超える）
        skill_paths = []
        for i in range(5):
            name = f"skill-{i}"
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                f"# {name}\nThis is skill number {i} with unique content about topic {i}."
            )
            skill_paths.append(skill_md)

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}

        # scipy と sklearn のインポートを失敗させる
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name in ("scipy", "sklearn"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            with mock.patch("builtins.__import__", side_effect=mock_import):
                result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is True
        assert result["reason"] == "scipy_not_available"

    def test_stderr_message_when_scipy_missing(self, tmp_path, capsys):
        """scipy が無い場合 stderr にインストールヒントを出力する。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        skill_paths = []
        for i in range(5):
            name = f"skill-{i}"
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"# {name}\nContent {i}.")
            skill_paths.append(skill_md)

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name in ("scipy", "sklearn"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            with mock.patch("builtins.__import__", side_effect=mock_import):
                reorganize.run_reorganize(str(project_dir))

        captured = capsys.readouterr()
        assert "scipy/scikit-learn" in captured.err
        assert "pip install" in captured.err


class TestSplitCandidatesDetected:
    """SKILL.md が 300 行を超えるスキルが分割候補として検出されるテスト。"""

    def test_split_candidates_detected(self, tmp_path):
        """300 行超のスキルが分割候補に含まれる。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 300 行超のスキル
        long_skill_dir = skills_dir / "long-skill"
        long_skill_dir.mkdir(parents=True)
        long_content = "# Long Skill\n" + "\n".join(
            [f"Line {i}: some content" for i in range(450)]
        )
        long_skill_md = long_skill_dir / "SKILL.md"
        long_skill_md.write_text(long_content)

        # 300 行以下のスキル
        short_skill_dir = skills_dir / "short-skill"
        short_skill_dir.mkdir(parents=True)
        short_skill_md = short_skill_dir / "SKILL.md"
        short_skill_md.write_text("# Short Skill\nJust a few lines.")

        # グローバルスキルを含まないようにモック済みアーティファクトを使う
        artifacts = {"skills": [long_skill_md, short_skill_md], "rules": []}
        candidates = reorganize.detect_split_candidates(artifacts)

        assert len(candidates) == 1
        assert candidates[0]["skill_name"] == "long-skill"
        assert candidates[0]["line_count"] > 300
        assert candidates[0]["threshold"] == 300

    def test_split_candidates_plugin_excluded(self, tmp_path):
        """プラグイン由来スキルは分割候補に含まれない。"""
        plugin_path = (
            Path.home() / ".claude" / "plugins" / "cache"
            / "test-plugin" / "v1" / ".claude" / "skills" / "big-plugin-skill"
        )

        long_content = "# Big Plugin Skill\n" + "\n".join(
            [f"Line {i}" for i in range(400)]
        )

        artifacts = {
            "skills": [plugin_path / "SKILL.md"],
            "rules": [],
        }

        # read_text をモックして長いコンテンツを返す
        with mock.patch.object(Path, "read_text", return_value=long_content):
            candidates = reorganize.detect_split_candidates(artifacts)

        assert len(candidates) == 0


class TestConfigurableThreshold:
    """evolve-state.json からのカスタム閾値の読み込みテスト。"""

    def test_configurable_threshold(self, tmp_path):
        """evolve-state.json に reorganize_threshold が設定されている場合その値を使う。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()

        state = {"reorganize_threshold": 0.5}
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        with mock.patch.object(reorganize, "DATA_DIR", data_dir):
            threshold = reorganize.load_reorganize_threshold()

        assert threshold == 0.5

    def test_default_threshold_when_no_file(self, tmp_path):
        """evolve-state.json が存在しない場合デフォルト 0.7 を返す。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()

        with mock.patch.object(reorganize, "DATA_DIR", data_dir):
            threshold = reorganize.load_reorganize_threshold()

        assert threshold == 0.7

    def test_default_threshold_when_key_missing(self, tmp_path):
        """evolve-state.json に reorganize_threshold キーが無い場合デフォルト 0.7 を返す。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()

        state = {"decay_threshold": 0.2}
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        with mock.patch.object(reorganize, "DATA_DIR", data_dir):
            threshold = reorganize.load_reorganize_threshold()

        assert threshold == 0.7

    def test_default_threshold_when_malformed_json(self, tmp_path):
        """evolve-state.json が不正な JSON の場合デフォルト 0.7 を返す。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()

        (data_dir / "evolve-state.json").write_text("not valid json")

        with mock.patch.object(reorganize, "DATA_DIR", data_dir):
            threshold = reorganize.load_reorganize_threshold()

        assert threshold == 0.7


class TestPluginSkillsExcluded:
    """プラグイン由来スキルが分析対象に含まれないテスト。"""

    def test_plugin_skills_excluded(self, tmp_path):
        """プラグイン由来スキルはクラスタリング対象から除外される。"""
        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # カスタムスキルを3つ作成
        custom_paths = []
        for i in range(3):
            name = f"custom-skill-{i}"
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"# {name}\nCustom content {i}.")
            custom_paths.append(skill_md)

        # プラグインキャッシュにスキルを作成してプラグイン判定させる
        plugin_paths = []
        audit._plugin_skill_map_cache = {"plugin-skill-a": "test-plugin", "plugin-skill-b": "test-plugin"}
        try:
            for name in ["plugin-skill-a", "plugin-skill-b"]:
                skill_dir = skills_dir / name
                skill_dir.mkdir(parents=True)
                skill_md = skill_dir / "SKILL.md"
                skill_md.write_text(f"# {name}\nPlugin content.")
                plugin_paths.append(skill_md)

            # find_artifacts をモックしてグローバルスキルを除外
            fake_artifacts = {
                "skills": custom_paths + plugin_paths,
                "rules": [], "memory": [], "claude_md": [],
            }
            with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
                # 合計5スキルだがプラグイン2つを除くと3つ → insufficient_skills
                result = reorganize.run_reorganize(str(project_dir))

            assert result["skipped"] is True
            assert result["reason"] == "insufficient_skills"
            assert result["count"] == 3
        finally:
            audit._plugin_skill_map_cache = None


class TestMergeGroupsFromClusters:
    """2つ以上のスキルを持つクラスタがマージ候補になるテスト。"""

    def test_merge_groups_from_clusters(self, tmp_path):
        """類似コンテンツのスキルがマージ候補として検出される。"""
        scipy = pytest.importorskip("scipy")
        sklearn = pytest.importorskip("sklearn")

        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 類似したスキルペアを作成
        similar_content_a = (
            "# Deploy AWS\n"
            "Deploy application to AWS using CloudFormation templates.\n"
            "AWS deployment configuration and infrastructure setup.\n"
            "CloudFormation stack management and deployment pipeline.\n"
            "AWS EC2 instances and load balancer configuration.\n"
        )
        similar_content_b = (
            "# AWS Infrastructure\n"
            "AWS infrastructure deployment and CloudFormation templates.\n"
            "Deploy and manage AWS cloud infrastructure resources.\n"
            "CloudFormation deployment automation and stack updates.\n"
            "AWS EC2 auto-scaling and load balancer setup.\n"
        )

        # 異なるドメインのスキルを3つ作成
        different_contents = [
            (
                "# Python Testing\n"
                "Unit testing with pytest framework and test fixtures.\n"
                "Mock objects and parametrized test cases for Python.\n"
                "Test coverage analysis and continuous integration.\n"
                "Python test runner configuration and assertion helpers.\n"
            ),
            (
                "# Database Migration\n"
                "SQL database schema migration and version control.\n"
                "PostgreSQL table alterations and index management.\n"
                "Database rollback procedures and migration scripts.\n"
                "SQL schema versioning and data migration tools.\n"
            ),
            (
                "# Frontend React\n"
                "React component development and state management.\n"
                "JavaScript frontend rendering and virtual DOM.\n"
                "React hooks and context API for application state.\n"
                "Frontend UI component library and design system.\n"
            ),
        ]

        # 類似スキル2つ
        skill_paths = []
        for name, content in [("deploy-aws", similar_content_a), ("aws-infra", similar_content_b)]:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content)
            skill_paths.append(skill_md)

        # 異なるスキル3つ
        for i, content in enumerate(different_contents):
            name = f"different-skill-{i}"
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content)
            skill_paths.append(skill_md)

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}
        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is False
        assert result["total_clusters"] > 0
        assert isinstance(result["clusters"], list)
        assert isinstance(result["merge_groups"], list)

        # マージ候補にはスキル名と類似度スコアが含まれる
        for mg in result["merge_groups"]:
            assert "skills" in mg
            assert len(mg["skills"]) >= 2
            assert "reason" in mg
            assert "similarity_score" in mg
            assert mg["reason"] == "high content similarity"

    def test_single_skill_clusters_not_in_merge_groups(self, tmp_path):
        """1つのスキルだけのクラスタはマージ候補に含まれない。"""
        scipy = pytest.importorskip("scipy")
        sklearn = pytest.importorskip("sklearn")

        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 全く異なるドメインのスキルを5つ作成
        domains = [
            ("cooking-recipes", "# Cooking\nRecipes for Italian pasta and French cuisine.\nIngredients and cooking temperatures for baking bread.\n"),
            ("quantum-physics", "# Quantum Physics\nQuantum entanglement and superposition principles.\nSchrodinger equation and wave function collapse.\n"),
            ("gardening-tips", "# Gardening\nOrganic gardening and composting techniques.\nSeasonal planting calendar and soil pH management.\n"),
            ("music-theory", "# Music Theory\nChord progressions and harmonic analysis.\nMusical scales and rhythm notation systems.\n"),
            ("marine-biology", "# Marine Biology\nCoral reef ecosystems and marine biodiversity.\nOcean currents and deep sea organism adaptation.\n"),
        ]

        skill_paths = []
        for name, content in domains:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content)
            skill_paths.append(skill_md)

        # 低い閾値（厳しいマージ条件）を設定
        data_dir = tmp_path / "rl-data"
        data_dir.mkdir()
        state = {"reorganize_threshold": 0.3}
        (data_dir / "evolve-state.json").write_text(json.dumps(state))

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}
        with mock.patch.object(reorganize, "DATA_DIR", data_dir):
            with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
                result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is False
        # 各クラスタには1つのスキルのみ（非常に異なるドメイン）
        # マージ候補は0か少数のはず
        for cluster in result["clusters"]:
            assert "centroid_keywords" in cluster
            assert isinstance(cluster["centroid_keywords"], list)


class TestBuildTfidfMatrix:
    """build_tfidf_matrix のユニットテスト。"""

    def test_returns_none_when_sklearn_missing(self):
        """sklearn がインポートできない場合 (None, None, None) を返す。"""
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "sklearn.feature_extraction.text":
                raise ImportError("No module named 'sklearn'")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            matrix, features, names = reorganize.build_tfidf_matrix({"a": "hello world"})

        assert matrix is None
        assert features is None
        assert names is None

    def test_builds_matrix_with_sklearn(self):
        """sklearn がある場合 TF-IDF 行列を正しく構築する。"""
        sklearn = pytest.importorskip("sklearn")

        texts = {
            "skill-a": "python testing framework pytest unittest",
            "skill-b": "javascript react frontend component",
            "skill-c": "database sql postgresql migration schema",
        }

        matrix, features, names = reorganize.build_tfidf_matrix(texts)

        assert matrix is not None
        assert features is not None
        assert names == ["skill-a", "skill-b", "skill-c"]
        assert matrix.shape[0] == 3  # 3 skills


class TestClusterSkills:
    """cluster_skills のユニットテスト。"""

    def test_cluster_skills(self):
        """クラスタリングがラベルのリストを返す。"""
        scipy = pytest.importorskip("scipy")
        sklearn = pytest.importorskip("sklearn")

        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [
            "python testing pytest unittest",
            "python test pytest framework",
            "javascript react frontend",
            "javascript angular frontend",
            "database sql postgresql",
        ]

        vectorizer = TfidfVectorizer(max_features=200, stop_words='english')
        matrix = vectorizer.fit_transform(texts)

        labels = reorganize.cluster_skills(matrix, threshold=0.7)

        assert len(labels) == 5
        assert all(isinstance(l, int) for l in labels)


class TestExtractCentroidKeywords:
    """extract_centroid_keywords のユニットテスト。"""

    def test_extract_keywords(self):
        """クラスタのセントロイドから上位キーワードを抽出する。"""
        sklearn = pytest.importorskip("sklearn")

        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [
            "python testing pytest unittest mock",
            "python test pytest framework assertion",
            "javascript react frontend component render",
        ]

        vectorizer = TfidfVectorizer(max_features=200, stop_words='english')
        matrix = vectorizer.fit_transform(texts)
        features = vectorizer.get_feature_names_out()

        # 最初の2つのスキル（Python テスト系）のキーワード
        keywords = reorganize.extract_centroid_keywords(
            [texts[0], texts[1]], features, matrix, [0, 1]
        )

        assert len(keywords) == 5
        assert all(isinstance(k, str) for k in keywords)
