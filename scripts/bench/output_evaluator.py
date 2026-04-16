"""TBench2-rl: LLM 出力の3軸採点モジュール。

スパイク (spike_rl_scorer_output_eval.py) の3軸採点ロジックを汎用化。
consideration 系スキル（evolve/reflect/optimize/audit）の出力テキストを
技術・ドメイン・構造の3軸で haiku を使って採点する。

スパイク結果 (2026-04-16):
  - 3軸とも LLM 出力評価に転用可能
  - domain 軸 (0.82) が rl-anything 固有観点を正確評価
  - parse error 時は has_error=True + min_on_error=0.05 で最低値
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────
# AxisScores: 3軸スコアコンテナ
# ─────────────────────────────────────────────────

@dataclass
class AxisScores:
    """3軸採点の結果。各値は 0.0〜1.0。"""

    technical: float
    domain: float
    structure: float
    has_error: bool = False
    # 各軸の詳細（オプション）
    technical_detail: dict = field(default_factory=dict)
    domain_detail: dict = field(default_factory=dict)
    structure_detail: dict = field(default_factory=dict)

    def integrated(self, min_on_error: float = 0.0) -> float:
        """統合スコアを返す。

        重み: technical 40% / domain 40% / structure 20%

        Args:
            min_on_error: has_error=True のとき返す最低値（0.0 以上）。
                         0.0 は「評価不能」、0.05 は「評価エラー」を示す。
        """
        score = self.technical * 0.4 + self.domain * 0.4 + self.structure * 0.2
        if self.has_error:
            return max(score, min_on_error)
        return score

    def to_score_10(self, min_on_error: float = 0.05) -> float:
        """0〜10 スケールに変換した統合スコアを返す。"""
        return round(self.integrated(min_on_error=min_on_error) * 10, 3)


# ─────────────────────────────────────────────────
# プロンプトテンプレート（軸別）
# ─────────────────────────────────────────────────

_TECHNICAL_TEMPLATE = """\
あなたは LLM が生成したスキル出力の技術品質を評価します。

## 評価対象出力テキスト (skill: {skill_name})

{output_text}

## 評価基準（技術品質）

| 観点 | 重み | 基準 |
|------|------|------|
| 明確性 | 30% | 出力が曖昧でないか。「適切に」「必要に応じて」等の曖昧語が少ないか |
| 完全性 | 25% | 必要な情報が含まれているか（観察→診断→提案の流れ）|
| 一貫性 | 20% | 内部矛盾がないか。前後の記述が整合しているか |
| エッジケース | 15% | 例外ケースや空振り（問題なし）の場合の扱いが記述されているか |
| 実行可能性 | 10% | 提案が具体的で実際に実行できる形か |

各観点 0.0〜1.0 で採点し、以下の JSON のみを返してください（マークダウン不要）:

{{"clarity": <float>, "completeness": <float>, "consistency": <float>, "edge_cases": <float>, "testability": <float>, "total": <重み付き平均>, "rationale": "<50字以内の根拠>"}}"""

_DOMAIN_TEMPLATE = """\
あなたは rl-anything プラグインの出力品質を評価します。

rl-anything は Claude Code の「自律進化パイプライン」プラグインで、
スキル/ルールの自己改善（evolve）、修正フィードバック収集（reflect）、
最適化（optimize）、環境診断（audit）を行います。

## 評価対象出力テキスト (skill: {skill_name})

{output_text}

## 評価基準（ドメイン品質 — rl-anything 固有）

| 観点 | 重み | 基準 |
|------|------|------|
| データ根拠 | 30% | セッション数・correction件数等の定量データに基づいているか |
| 診断精度 | 30% | 検出パターンが実際の問題を指摘しているか（ハルシネーションなしか）|
| 提案実用性 | 20% | 提案が具体的で適用可能か（曖昧な「改善しましょう」でないか）|
| 範囲適切性 | 20% | 変更範囲が適切か（大きすぎず小さすぎず）|

各観点 0.0〜1.0 で採点し、以下の JSON のみを返してください（マークダウン不要）:

{{"data_grounding": <float>, "diagnostic_accuracy": <float>, "proposal_utility": <float>, "scope_fit": <float>, "total": <重み付き平均>, "rationale": "<50字以内の根拠>"}}"""

_STRUCTURE_TEMPLATE = """\
あなたは LLM が生成したスキル出力の構造品質を評価します。

## 評価対象出力テキスト (skill: {skill_name})

{output_text}

## 評価基準（構造品質）

| 観点 | 重み | 基準 |
|------|------|------|
| フォーマット | 25% | Markdown が適切に使われているか。見出し・リストが構造化されているか |
| 長さ | 25% | 適切な長さか（短すぎず冗長でもない。100〜500行が目安）|
| 具体例 | 25% | 例示・コードブロック・コマンドが含まれているか |
| 完結性 | 25% | 出力が途中で切れていないか。次のアクションが明示されているか |

各観点 0.0〜1.0 で採点し、以下の JSON のみを返してください（マークダウン不要）:

{{"format": <float>, "length": <float>, "examples": <float>, "completeness": <float>, "total": <重み付き平均>, "rationale": "<50字以内の根拠>"}}"""


# ─────────────────────────────────────────────────
# OutputEvaluator
# ─────────────────────────────────────────────────

class OutputEvaluator:
    """consideration スキルの LLM 出力を3軸採点する。

    Args:
        system_context: CLAUDE.md + rules の現在コンテンツ（harness_hash 計算用）
        model:          採点に使う Claude モデル
        timeout_sec:    haiku 呼び出しのタイムアウト（秒）
    """

    def __init__(
        self,
        system_context: str = "",
        model: str = "haiku",
        timeout_sec: int = 60,
    ) -> None:
        self.system_context = system_context
        self.model = model
        self.timeout_sec = timeout_sec

    def evaluate(self, skill_name: str, output_text: str) -> AxisScores:
        """出力テキストを3軸で採点し AxisScores を返す。

        内部で haiku を3回呼ぶ（各軸1回）。失敗軸は has_error=True。
        """
        technical = self._score_axis(
            _TECHNICAL_TEMPLATE.format(skill_name=skill_name, output_text=output_text),
            key="total",
        )
        domain = self._score_axis(
            _DOMAIN_TEMPLATE.format(skill_name=skill_name, output_text=output_text),
            key="total",
        )
        structure = self._score_axis(
            _STRUCTURE_TEMPLATE.format(skill_name=skill_name, output_text=output_text),
            key="total",
        )

        any_error = any(v is None for v in [technical, domain, structure])

        return AxisScores(
            technical=technical[0] if technical else 0.0,
            domain=domain[0] if domain else 0.0,
            structure=structure[0] if structure else 0.0,
            has_error=any_error,
            technical_detail=technical[1] if technical else {},
            domain_detail=domain[1] if domain else {},
            structure_detail=structure[1] if structure else {},
        )

    def _score_axis(self, prompt: str, key: str = "total") -> Optional[tuple[float, dict]]:
        """haiku でプロンプトを実行し (score, detail_dict) を返す。失敗時は None。"""
        raw = self._call_haiku(prompt)
        if raw is None:
            return None
        parsed = self._parse_json(raw)
        if not isinstance(parsed, dict):
            return None
        # key が存在しない場合は検証失敗として None を返す（サイレントに 0.0 にしない）
        if key not in parsed:
            return None
        try:
            score = float(parsed[key])
            score = max(0.0, min(1.0, score))
        except (TypeError, ValueError):
            return None
        return (score, parsed)

    def _call_haiku(self, prompt: str) -> Optional[str]:
        """haiku で採点プロンプトを実行し stdout を返す。"""
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", self.model],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        """JSON をパース。マークダウンコードブロックを除去してから試みる。"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # JSON 断片抽出
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return None
