#!/usr/bin/env python3
"""semantic_detector.py のユニットテスト。"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.semantic_detector import (
    BATCH_SIZE,
    _extract_json_array,
    detect_contradictions,
    semantic_analyze,
    validate_corrections,
)


# --- _extract_json_array ---


def test_extract_json_direct():
    text = '[{"index": 0, "is_learning": true}]'
    result = _extract_json_array(text)
    assert result == [{"index": 0, "is_learning": True}]


def test_extract_json_in_code_block():
    text = '```json\n[{"index": 0, "is_learning": false}]\n```'
    result = _extract_json_array(text)
    assert result == [{"index": 0, "is_learning": False}]


def test_extract_json_with_surrounding_text():
    text = 'Here is the result:\n[{"index": 0, "is_learning": true}]\nDone.'
    result = _extract_json_array(text)
    assert result == [{"index": 0, "is_learning": True}]


def test_extract_json_invalid():
    result = _extract_json_array("not json at all")
    assert result is None


# --- semantic_analyze ---


def _make_corrections(n):
    return [{"message": f"correction {i}"} for i in range(n)]


def _mock_subprocess_success(items):
    """items 数に応じた成功レスポンスを返す mock を作成。"""
    response = json.dumps([
        {"index": i, "is_learning": True, "extracted_learning": f"learning {i}"}
        for i in range(len(items))
    ])
    mock_result = MagicMock()
    mock_result.stdout = response
    mock_result.returncode = 0
    return mock_result


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_basic(mock_run):
    corrections = _make_corrections(3)
    response = json.dumps([
        {"index": 0, "is_learning": True, "extracted_learning": "learn 0"},
        {"index": 1, "is_learning": False, "extracted_learning": None},
        {"index": 2, "is_learning": True, "extracted_learning": "learn 2"},
    ])
    mock_run.return_value = MagicMock(stdout=response, returncode=0)

    results = semantic_analyze(corrections)
    assert len(results) == 3
    assert results[0]["is_learning"] is True
    assert results[1]["is_learning"] is False
    assert results[2]["extracted_learning"] == "learn 2"
    mock_run.assert_called_once()


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_batch_split(mock_run):
    """20件超のときに複数バッチに分割されることを確認。"""
    corrections = _make_corrections(25)

    def side_effect(*args, **kwargs):
        # コマンドのプロンプトから件数を推定
        prompt = args[0][-1] if args[0] else kwargs.get("args", [""])[-1]
        # 各バッチの件数を計算
        call_count = mock_run.call_count
        if call_count <= 1:
            batch_size = 20
        else:
            batch_size = 5
        response = json.dumps([
            {"index": i, "is_learning": True, "extracted_learning": None}
            for i in range(batch_size)
        ])
        return MagicMock(stdout=response, returncode=0)

    mock_run.side_effect = side_effect

    results = semantic_analyze(corrections)
    assert len(results) == 25
    assert mock_run.call_count == 2


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_json_parse_failure(mock_run):
    """JSON パース失敗時にフォールバック（全件 is_learning=True）。"""
    corrections = _make_corrections(3)
    mock_run.return_value = MagicMock(stdout="invalid json response", returncode=0)

    results = semantic_analyze(corrections)
    assert len(results) == 3
    assert all(r["is_learning"] is True for r in results)


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_timeout(mock_run):
    """タイムアウト時にフォールバック（is_learning=True）。"""
    corrections = _make_corrections(3)
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)

    results = semantic_analyze(corrections)
    assert len(results) == 3
    assert all(r["is_learning"] is True for r in results)


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_count_mismatch_partial_success(mock_run):
    """レスポンス件数が不一致のとき partial success: マッチ分は LLM 判定、残りは is_learning=True。"""
    corrections = _make_corrections(3)
    response = json.dumps([
        {"index": 0, "is_learning": False, "extracted_learning": None},
    ])
    mock_run.return_value = MagicMock(stdout=response, returncode=0)

    results = semantic_analyze(corrections)
    assert len(results) == 3
    # index 0 は LLM の判定 (False) を適用
    assert results[0]["is_learning"] is False
    # index 1, 2 は未マッチのため is_learning=True でパススルー
    assert results[1]["is_learning"] is True
    assert results[2]["is_learning"] is True


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_empty_response(mock_run):
    """LLM が空リストを返した場合、全件 is_learning=True でパススルー。"""
    corrections = _make_corrections(3)
    mock_run.return_value = MagicMock(stdout="[]", returncode=0)

    results = semantic_analyze(corrections)
    assert len(results) == 3
    assert all(r["is_learning"] is True for r in results)


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_partial_success_multiple(mock_run):
    """7件中5件返却の partial success: マッチ分は LLM 判定、残り2件は is_learning=True。"""
    corrections = _make_corrections(7)
    response = json.dumps([
        {"index": 0, "is_learning": True, "extracted_learning": "l0"},
        {"index": 1, "is_learning": False, "extracted_learning": None},
        {"index": 3, "is_learning": True, "extracted_learning": "l3"},
        {"index": 4, "is_learning": False, "extracted_learning": None},
        {"index": 6, "is_learning": True, "extracted_learning": "l6"},
    ])
    mock_run.return_value = MagicMock(stdout=response, returncode=0)

    results = semantic_analyze(corrections)
    assert len(results) == 7
    assert results[0]["is_learning"] is True
    assert results[1]["is_learning"] is False
    assert results[2]["is_learning"] is True   # unmatched → True
    assert results[3]["is_learning"] is True
    assert results[4]["is_learning"] is False
    assert results[5]["is_learning"] is True   # unmatched → True
    assert results[6]["is_learning"] is True


@patch("lib.semantic_detector.subprocess.run")
def test_semantic_analyze_empty(mock_run):
    results = semantic_analyze([])
    assert results == []
    mock_run.assert_not_called()


# --- validate_corrections ---


@patch("lib.semantic_detector.subprocess.run")
def test_validate_corrections_success(mock_run):
    corrections = _make_corrections(2)
    response = json.dumps([
        {"index": 0, "is_learning": True, "extracted_learning": "l0"},
        {"index": 1, "is_learning": False, "extracted_learning": None},
    ])
    mock_run.return_value = MagicMock(stdout=response, returncode=0)

    results = validate_corrections(corrections)
    assert len(results) == 2
    assert results[0]["is_learning"] is True
    assert results[1]["is_learning"] is False


@patch("lib.semantic_detector.subprocess.run")
def test_validate_corrections_fallback_on_exception(mock_run):
    """例外時に全件 is_learning=True のフォールバック。"""
    corrections = _make_corrections(3)
    mock_run.side_effect = Exception("unexpected error")

    results = validate_corrections(corrections)
    assert len(results) == 3
    assert all(r["is_learning"] is True for r in results)


@patch("lib.semantic_detector.subprocess.run")
def test_validate_corrections_fallback_on_timeout(mock_run):
    """タイムアウト時のフォールバック（is_learning=True）。"""
    corrections = _make_corrections(2)
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)

    results = validate_corrections(corrections)
    assert len(results) == 2
    assert all(r["is_learning"] is True for r in results)


# --- detect_contradictions ---


def test_detect_contradictions_empty_input():
    """空リストで空リスト返却、LLM 未呼出。"""
    with patch("lib.semantic_detector.subprocess.run") as mock_run:
        result = detect_contradictions([])
        assert result == []
        mock_run.assert_not_called()


def test_detect_contradictions_single_input():
    """1件で空リスト返却、LLM 未呼出。"""
    with patch("lib.semantic_detector.subprocess.run") as mock_run:
        result = detect_contradictions(_make_corrections(1))
        assert result == []
        mock_run.assert_not_called()


@patch("lib.semantic_detector.subprocess.run")
def test_detect_contradictions_success(mock_run):
    """LLM 成功時に矛盾ペアが返ること。"""
    corrections = [
        {"message": "日本語で応答して"},
        {"message": "英語で応答して"},
        {"message": "コード例を多めに"},
    ]
    response = json.dumps([
        {"pair": [0, 1], "reason": "言語指定が矛盾している"},
    ])
    mock_run.return_value = MagicMock(stdout=response, returncode=0)

    result = detect_contradictions(corrections)
    assert len(result) == 1
    assert result[0]["pair"] == [0, 1]
    assert "矛盾" in result[0]["reason"] or len(result[0]["reason"]) > 0
    mock_run.assert_called_once()


@patch("lib.semantic_detector.subprocess.run")
def test_detect_contradictions_llm_failure(mock_run, capsys):
    """LLM 失敗時に空リスト + stderr 警告。"""
    corrections = _make_corrections(3)
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)

    result = detect_contradictions(corrections)
    assert result == []

    captured = capsys.readouterr()
    assert "Warning: contradiction detection failed" in captured.err


@patch("lib.semantic_detector.subprocess.run")
def test_validate_corrections_fallback_is_true(mock_run):
    """フォールバック時 is_learning=True であることを確認。"""
    corrections = _make_corrections(5)
    # 全失敗ケース: 例外発生
    mock_run.side_effect = Exception("unexpected failure")

    results = validate_corrections(corrections)
    assert len(results) == 5
    assert all(r["is_learning"] is True for r in results)
    assert all(r["extracted_learning"] is None for r in results)


# --- BATCH_SIZE ---


def test_batch_size_is_20():
    assert BATCH_SIZE == 20
