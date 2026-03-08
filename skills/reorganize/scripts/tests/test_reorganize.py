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


class TestClustersOutput:
    """クラスタリング出力テスト（マージ候補は prune に一元化済み）。"""

    def test_clusters_output_no_merge_groups(self, tmp_path):
        """出力に clusters と split_candidates が含まれ、merge_groups は含まれない。"""
        scipy = pytest.importorskip("scipy")
        sklearn = pytest.importorskip("sklearn")

        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        # 5つスキルを作成
        skill_paths = []
        contents = [
            "Deploy application to AWS using CloudFormation templates.\nAWS deployment config.\n",
            "AWS infrastructure deployment and CloudFormation templates.\nDeploy resources.\n",
            "Unit testing with pytest framework and test fixtures.\nMock and parametrize.\n",
            "SQL database schema migration and version control.\nPostgreSQL alterations.\n",
            "React component development and state management.\nJavaScript frontend.\n",
        ]
        for i, content in enumerate(contents):
            name = f"skill-{i}"
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"# {name}\n{content}")
            skill_paths.append(skill_md)

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}
        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is False
        assert "clusters" in result
        assert "split_candidates" in result
        assert "merge_groups" not in result
        assert "total_merge_groups" not in result
        assert result["total_clusters"] > 0

    def test_clusters_have_keywords(self, tmp_path):
        """各クラスタに centroid_keywords が含まれる。"""
        scipy = pytest.importorskip("scipy")
        sklearn = pytest.importorskip("sklearn")

        project_dir = tmp_path / "project"
        skills_dir = project_dir / ".claude" / "skills"

        domains = [
            ("cooking-recipes", "# Cooking\nRecipes for Italian pasta and French cuisine.\nBaking bread.\n"),
            ("quantum-physics", "# Quantum\nEntanglement and superposition.\nSchrodinger equation.\n"),
            ("gardening-tips", "# Gardening\nOrganic composting techniques.\nSeasonal planting.\n"),
            ("music-theory", "# Music\nChord progressions and analysis.\nMusical scales.\n"),
            ("marine-biology", "# Marine\nCoral reef ecosystems.\nOcean currents.\n"),
        ]

        skill_paths = []
        for name, content in domains:
            skill_dir = skills_dir / name
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content)
            skill_paths.append(skill_md)

        fake_artifacts = {"skills": skill_paths, "rules": [], "memory": [], "claude_md": []}
        with mock.patch("reorganize.find_artifacts", return_value=fake_artifacts):
            result = reorganize.run_reorganize(str(project_dir))

        assert result["skipped"] is False
        for cluster in result["clusters"]:
            assert "centroid_keywords" in cluster
            assert isinstance(cluster["centroid_keywords"], list)


class TestSplitDetection:
    """split 検出の専用テスト。"""

    def test_300行超検出(self, tmp_path):
        """300行を超えるスキルが split_candidates に含まれる。"""
        skills_dir = tmp_path / ".claude" / "skills"
        long_dir = skills_dir / "long-skill"
        long_dir.mkdir(parents=True)
        long_md = long_dir / "SKILL.md"
        long_md.write_text("# Long\n" + "\n".join(f"line {i}" for i in range(350)))

        artifacts = {"skills": [long_md], "rules": []}
        candidates = reorganize.detect_split_candidates(artifacts)
        assert len(candidates) == 1
        assert candidates[0]["skill_name"] == "long-skill"
        assert candidates[0]["line_count"] > 300

    def test_全スキル300行以下時の空リスト(self, tmp_path):
        """全スキルが300行以下なら空リストを返す。"""
        skills_dir = tmp_path / ".claude" / "skills"
        paths = []
        for name in ["a", "b", "c"]:
            d = skills_dir / name
            d.mkdir(parents=True)
            md = d / "SKILL.md"
            md.write_text(f"# {name}\nShort content.\n")
            paths.append(md)

        artifacts = {"skills": paths, "rules": []}
        candidates = reorganize.detect_split_candidates(artifacts)
        assert candidates == []


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
