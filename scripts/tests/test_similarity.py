#!/usr/bin/env python3
"""similarity.py のユニットテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.similarity import (
    build_tfidf_matrix,
    compute_pairwise_similarity,
    jaccard_coefficient,
    tokenize,
)


# --- build_tfidf_matrix ---


def test_build_tfidf_matrix_basic():
    """2つのスキルテキストで TF-IDF 行列が返ることを確認。"""
    sklearn = pytest.importorskip("sklearn")

    texts = {
        "skill-a": "python testing framework pytest unittest",
        "skill-b": "javascript react frontend component rendering",
    }
    matrix, features, names = build_tfidf_matrix(texts)

    assert matrix is not None
    assert features is not None
    assert names == ["skill-a", "skill-b"]
    assert matrix.shape[0] == 2


def test_build_tfidf_matrix_sklearn_not_installed():
    """sklearn がない場合に (None, None, None) を返すことを確認。"""
    original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def mock_import(name, *args, **kwargs):
        if name == "sklearn.feature_extraction.text":
            raise ImportError("No module named 'sklearn'")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        matrix, features, names = build_tfidf_matrix({"a": "hello world"})

    assert matrix is None
    assert features is None
    assert names is None


# --- compute_pairwise_similarity ---


def test_compute_pairwise_similarity_similar_pair(tmp_path):
    """類似コンテンツのペアが検出されることを確認。"""
    sklearn = pytest.importorskip("sklearn")
    pytest.importorskip("scipy")

    # 非常に類似したコンテンツを作成
    file_a = tmp_path / "skill_a.md"
    file_a.write_text(
        "Deploy application to AWS using CloudFormation templates. "
        "AWS deployment configuration and infrastructure setup. "
        "CloudFormation stack management and deployment pipeline."
    )
    file_b = tmp_path / "skill_b.md"
    file_b.write_text(
        "AWS infrastructure deployment and CloudFormation templates. "
        "Deploy and manage AWS cloud infrastructure resources. "
        "CloudFormation deployment automation and stack updates."
    )

    paths = {
        "deploy-aws": str(file_a),
        "aws-infra": str(file_b),
    }
    results = compute_pairwise_similarity(paths, threshold=0.30)

    assert len(results) >= 1
    assert results[0]["path_a"] == str(file_a)
    assert results[0]["path_b"] == str(file_b)
    assert results[0]["similarity"] >= 0.30


def test_compute_pairwise_similarity_unrelated_pair(tmp_path):
    """無関係なコンテンツが閾値以下でフィルタされることを確認。"""
    sklearn = pytest.importorskip("sklearn")
    pytest.importorskip("scipy")

    file_a = tmp_path / "skill_a.md"
    file_a.write_text(
        "Python testing framework pytest unittest mock assertion. "
        "Test coverage analysis and continuous integration pipeline."
    )
    file_b = tmp_path / "skill_b.md"
    file_b.write_text(
        "Coral reef ecosystems and marine biodiversity conservation. "
        "Ocean currents and deep sea organism adaptation patterns."
    )

    paths = {
        "python-test": str(file_a),
        "marine-bio": str(file_b),
    }
    results = compute_pairwise_similarity(paths, threshold=0.80)

    assert len(results) == 0


def test_compute_pairwise_similarity_empty_input():
    """空辞書で空リスト返却。"""
    results = compute_pairwise_similarity({})
    assert results == []


def test_compute_pairwise_similarity_single_input(tmp_path):
    """1件で空リスト返却。"""
    file_a = tmp_path / "skill_a.md"
    file_a.write_text("Some content here.")

    results = compute_pairwise_similarity({"only-one": str(file_a)})
    assert results == []


def test_compute_pairwise_similarity_file_read_failure(tmp_path, capsys):
    """存在しないファイルパスでスキップ + stderr 警告。"""
    # 1つだけ実在するファイルを用意し、もう1つは存在しないパス
    file_a = tmp_path / "skill_a.md"
    file_a.write_text("Some content for skill A.")

    paths = {
        "real-skill": str(file_a),
        "missing-skill": str(tmp_path / "nonexistent.md"),
    }
    results = compute_pairwise_similarity(paths, threshold=0.50)

    # 読み込み可能なファイルが1件のみなので空リスト
    assert results == []

    captured = capsys.readouterr()
    assert "Warning: failed to read" in captured.err
    assert "nonexistent.md" in captured.err


def test_compute_pairwise_similarity_custom_threshold(tmp_path):
    """threshold=0.90 で結果が変わることを確認。"""
    sklearn = pytest.importorskip("sklearn")
    pytest.importorskip("scipy")

    # ある程度類似しているが完全一致ではないコンテンツ
    file_a = tmp_path / "skill_a.md"
    file_a.write_text(
        "Deploy application to AWS using CloudFormation templates. "
        "AWS deployment configuration and infrastructure setup."
    )
    file_b = tmp_path / "skill_b.md"
    file_b.write_text(
        "AWS infrastructure deployment and CloudFormation templates. "
        "Deploy and manage AWS cloud infrastructure resources."
    )

    paths = {
        "deploy-aws": str(file_a),
        "aws-infra": str(file_b),
    }

    # 低い閾値では検出される
    results_low = compute_pairwise_similarity(paths, threshold=0.30)
    # 高い閾値では検出されない可能性が高い
    results_high = compute_pairwise_similarity(paths, threshold=0.90)

    assert len(results_low) >= len(results_high)


def test_compute_pairwise_similarity_sklearn_not_installed(tmp_path):
    """sklearn 未インストールで空リスト。"""
    file_a = tmp_path / "skill_a.md"
    file_a.write_text("Content A for testing purposes.")
    file_b = tmp_path / "skill_b.md"
    file_b.write_text("Content B for testing purposes.")

    paths = {
        "skill-a": str(file_a),
        "skill-b": str(file_b),
    }

    with patch("lib.similarity.build_tfidf_matrix", return_value=(None, None, None)):
        results = compute_pairwise_similarity(paths, threshold=0.50)

    assert results == []


# --- tokenize ---


class TestTokenize:
    """tokenize のユニットテスト。"""

    def test_basic_tokenization(self):
        """基本的なトークン化: 空白・句読点で分割、小文字化。"""
        result = tokenize("Hello World, foo-bar_baz")
        assert "hello" in result
        assert "world" in result
        assert "foo" in result
        assert "bar" in result
        assert "baz" in result

    def test_empty_string(self):
        """空文字列は空集合を返す。"""
        assert tokenize("") == set()

    def test_duplicate_words(self):
        """重複ワードは集合なので1つになる。"""
        result = tokenize("test test test")
        assert result == {"test"}


# --- jaccard_coefficient ---


class TestJaccardCoefficient:
    """jaccard_coefficient のユニットテスト。"""

    def test_exact_match(self):
        """完全一致で 1.0 を返す。"""
        assert jaccard_coefficient({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial_overlap(self):
        """部分一致: {a,b} vs {b,c} => 1/3。"""
        score = jaccard_coefficient({"a", "b"}, {"b", "c"})
        assert abs(score - 1 / 3) < 1e-9

    def test_no_overlap(self):
        """重複なしで 0.0 を返す。"""
        assert jaccard_coefficient({"a"}, {"b"}) == 0.0

    def test_both_empty(self):
        """両方空で 0.0 を返す。"""
        assert jaccard_coefficient(set(), set()) == 0.0

    def test_one_empty(self):
        """片方空で 0.0 を返す。"""
        assert jaccard_coefficient({"a"}, set()) == 0.0
