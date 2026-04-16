"""rl-scorer エージェント出力のスキーマ定義とバリデーション。

rl-scorer が返すべき JSON 構造を型付きで表現し、
キー欠損・型不正を早期に検出する。
"""
from __future__ import annotations
from dataclasses import dataclass, field


class ScorerValidationError(ValueError):
    """rl-scorer の出力が期待スキーマを満たさない。"""
    def __init__(self, msg: str, raw: dict):
        super().__init__(msg)
        self.raw = raw


@dataclass(frozen=True)
class AxisResult:
    """単一軸のスコア結果。total は 0.0〜1.0。"""
    total: float
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if not (0.0 <= self.total <= 1.0):
            # frozen dataclass なので object.__setattr__ は使えないが、
            # __post_init__ で ValueError を raise するのは問題ない
            raise ScorerValidationError(
                f"total={self.total!r} は範囲 [0, 1] 外です",
                raw=self.detail,
            )


@dataclass(frozen=True)
class ScorerOutput:
    """rl-scorer エージェントの統合出力スキーマ。"""
    technical: AxisResult
    domain_quality: AxisResult
    structure: AxisResult
    integrated_score: float
    summary: str
    improvements: list

    def __post_init__(self):
        if not (0.0 <= self.integrated_score <= 1.0):
            raise ScorerValidationError(
                f"integrated_score={self.integrated_score!r} は範囲 [0, 1] 外です",
                raw={},
            )


def validate_scorer_output(raw: dict) -> ScorerOutput:
    """raw dict を ScorerOutput に変換。欠損・型エラーは ScorerValidationError を raise。

    Args:
        raw: rl-scorer が返した JSON をパースした dict

    Returns:
        バリデーション済みの ScorerOutput

    Raises:
        ScorerValidationError: 必須キー欠損・型変換失敗・範囲外の場合
    """
    if not isinstance(raw, dict):
        raise ScorerValidationError("raw は dict でなければなりません", raw={})
    improvements_raw = raw.get("improvements", [])
    if not isinstance(improvements_raw, list):
        raise ScorerValidationError(
            "improvements は list でなければなりません（str 含む非 list 型は不可）", raw=raw
        )
    if not all(isinstance(x, str) for x in improvements_raw):
        raise ScorerValidationError(
            "improvements の各要素は str でなければなりません", raw=raw
        )
    try:
        summary_val = raw["summary"]
        if not isinstance(summary_val, str):
            raise ScorerValidationError(
                f"summary は str でなければなりません: {summary_val!r}", raw=raw
            )
        return ScorerOutput(
            technical=AxisResult(
                total=float(raw["technical"]["total"]),
                detail=dict(raw["technical"]),
            ),
            domain_quality=AxisResult(
                total=float(raw["domain_quality"]["total"]),
                detail=dict(raw["domain_quality"]),
            ),
            structure=AxisResult(
                total=float(raw["structure"]["total"]),
                detail=dict(raw["structure"]),
            ),
            integrated_score=float(raw["integrated_score"]),
            summary=summary_val,
            improvements=list(improvements_raw),
        )
    except ScorerValidationError:
        # AxisResult.__post_init__ や ScorerOutput.__post_init__ が raise する
        # ScorerValidationError を、下の ValueError ハンドラで誤捕捉しないよう再 raise
        raise
    except KeyError as e:
        raise ScorerValidationError(f"必須キーが欠損: {e}", raw=raw) from e
    except (TypeError, ValueError) as e:
        raise ScorerValidationError(f"型変換失敗: {e}", raw=raw) from e
