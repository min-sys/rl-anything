"""scorer_schema モジュールのユニットテスト。"""

import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from scorer_schema import AxisResult, ScorerOutput, ScorerValidationError, validate_scorer_output


# ─────────────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────────────

def _make_raw(
    technical_total: float = 0.8,
    domain_quality_total: float = 0.75,
    structure_total: float = 0.9,
    integrated_score: float = 0.8,
    summary: str = "良好な出力です",
    improvements: list | None = None,
    include_improvements: bool = True,
) -> dict:
    raw = {
        "technical": {"total": technical_total, "clarity": 0.8},
        "domain_quality": {"total": domain_quality_total, "data_grounding": 0.7},
        "structure": {"total": structure_total, "format": 0.9},
        "integrated_score": integrated_score,
        "summary": summary,
    }
    if include_improvements:
        raw["improvements"] = improvements if improvements is not None else ["改善点A"]
    return raw


# ─────────────────────────────────────────────────
# 正常系
# ─────────────────────────────────────────────────

class TestValidateScorerOutputNormal:
    """正常系: 正しい raw dict → ScorerOutput が返る。"""

    def test_正常系_ScorerOutputが返る(self):
        raw = _make_raw()
        result = validate_scorer_output(raw)
        assert isinstance(result, ScorerOutput)
        assert isinstance(result.technical, AxisResult)
        assert isinstance(result.domain_quality, AxisResult)
        assert isinstance(result.structure, AxisResult)

    def test_正常系_スコア値が正しく設定される(self):
        raw = _make_raw(technical_total=0.8, domain_quality_total=0.75, structure_total=0.9, integrated_score=0.8)
        result = validate_scorer_output(raw)
        assert result.technical.total == 0.8
        assert result.domain_quality.total == 0.75
        assert result.structure.total == 0.9
        assert result.integrated_score == 0.8

    def test_正常系_summaryが文字列として設定される(self):
        raw = _make_raw(summary="テスト出力")
        result = validate_scorer_output(raw)
        assert result.summary == "テスト出力"

    def test_正常系_improvementsがリストとして設定される(self):
        raw = _make_raw(improvements=["改善点A", "改善点B"])
        result = validate_scorer_output(raw)
        assert result.improvements == ["改善点A", "改善点B"]

    def test_正常系_detailに元のdictが含まれる(self):
        raw = _make_raw()
        result = validate_scorer_output(raw)
        assert result.technical.detail["clarity"] == 0.8


# ─────────────────────────────────────────────────
# キー欠損
# ─────────────────────────────────────────────────

class TestValidateScorerOutputMissingKey:
    """キー欠損: ScorerValidationError を raise する。"""

    def test_technicalキー欠損(self):
        raw = _make_raw()
        del raw["technical"]
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "欠損" in str(exc_info.value)

    def test_domain_qualityキー欠損(self):
        raw = _make_raw()
        del raw["domain_quality"]
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_structureキー欠損(self):
        raw = _make_raw()
        del raw["structure"]
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_integrated_scoreキー欠損(self):
        raw = _make_raw()
        del raw["integrated_score"]
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_summaryキー欠損(self):
        raw = _make_raw()
        del raw["summary"]
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_技術軸のtotalキー欠損(self):
        raw = _make_raw()
        del raw["technical"]["total"]
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_ScorerValidationErrorにrawが含まれる(self):
        raw = _make_raw()
        del raw["technical"]
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        # raw が ScorerValidationError に保存されていることを確認
        assert exc_info.value.raw is not None


# ─────────────────────────────────────────────────
# 型エラー
# ─────────────────────────────────────────────────

class TestValidateScorerOutputTypeError:
    """型エラー: total が文字列 "N/A" → ScorerValidationError。"""

    def test_technical_totalが文字列NA(self):
        raw = _make_raw()
        raw["technical"]["total"] = "N/A"
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "型変換失敗" in str(exc_info.value)

    def test_domain_quality_totalが文字列(self):
        raw = _make_raw()
        raw["domain_quality"]["total"] = "invalid"
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_integrated_scoreが文字列(self):
        raw = _make_raw()
        raw["integrated_score"] = "N/A"
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_technicalがNone(self):
        raw = _make_raw()
        raw["technical"] = None
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_summaryがNoneのときScorerValidationError(self):
        """str(None)='None' でサイレント通過せず ScorerValidationError を raise する。"""
        raw = _make_raw()
        raw["summary"] = None
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "str" in str(exc_info.value)


# ─────────────────────────────────────────────────
# 範囲外
# ─────────────────────────────────────────────────

class TestValidateScorerOutputOutOfRange:
    """範囲外: integrated_score=1.5 → ScorerValidationError。"""

    def test_integrated_scoreが1超(self):
        raw = _make_raw(integrated_score=1.5)
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "範囲" in str(exc_info.value)

    def test_integrated_scoreが負(self):
        raw = _make_raw(integrated_score=-0.1)
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_technical_totalが範囲外(self):
        raw = _make_raw(technical_total=1.5)
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_integrated_scoreが境界値0(self):
        """境界値 0.0 は有効。"""
        raw = _make_raw(integrated_score=0.0)
        result = validate_scorer_output(raw)
        assert result.integrated_score == 0.0

    def test_integrated_scoreが境界値1(self):
        """境界値 1.0 は有効。"""
        raw = _make_raw(integrated_score=1.0)
        result = validate_scorer_output(raw)
        assert result.integrated_score == 1.0


# ─────────────────────────────────────────────────
# improvements 欠損
# ─────────────────────────────────────────────────

class TestValidateScorerOutputImprovements:
    """improvements 欠損: 空リストで補完される。"""

    def test_improvementsキーなし_空リストで補完(self):
        raw = _make_raw(include_improvements=False)
        result = validate_scorer_output(raw)
        assert result.improvements == []

    def test_improvements空リスト(self):
        raw = _make_raw(improvements=[])
        result = validate_scorer_output(raw)
        assert result.improvements == []

    def test_improvements複数要素(self):
        raw = _make_raw(improvements=["改善A", "改善B", "改善C"])
        result = validate_scorer_output(raw)
        assert len(result.improvements) == 3

    def test_improvements文字列はエラー(self):
        """improvements が文字列のとき charlist に化けず ScorerValidationError を raise する。"""
        raw = _make_raw(include_improvements=False)
        raw["improvements"] = "改善点A"  # list でなく str
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(raw)

    def test_improvements非文字列要素はエラー(self):
        """improvements のリスト要素が str でないとき ScorerValidationError を raise する。"""
        raw = _make_raw(improvements=["改善A", 123, None])
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "str" in str(exc_info.value)


# ─────────────────────────────────────────────────
# raw 入力ガード
# ─────────────────────────────────────────────────

class TestValidateScorerOutputInputGuard:
    """raw が dict でない場合 / AxisResult の範囲外エラーが正しく伝播する。"""

    def test_rawがNoneのときScorerValidationError(self):
        """raw=None を渡した場合、AttributeError でなく ScorerValidationError を raise。"""
        with pytest.raises(ScorerValidationError):
            validate_scorer_output(None)  # type: ignore

    def test_rawがリストのときScorerValidationError(self):
        with pytest.raises(ScorerValidationError):
            validate_scorer_output([1, 2, 3])  # type: ignore

    def test_AxisResult範囲外エラーが元メッセージを保持(self):
        """ScorerValidationError が except ValueError に飲み込まれず、
        元の '範囲 [0, 1] 外です' メッセージが保持されることを確認。"""
        raw = _make_raw(technical_total=1.5)
        with pytest.raises(ScorerValidationError) as exc_info:
            validate_scorer_output(raw)
        assert "範囲" in str(exc_info.value) or "1.5" in str(exc_info.value)
