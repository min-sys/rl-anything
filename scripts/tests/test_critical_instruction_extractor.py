"""critical_instruction_extractor のテスト。

extract_critical_lines / rephrase_to_calm / detect_instruction_violation の
単体テスト18本。TDD First — 実装前にテストを書く。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

# scripts/lib を import パスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from critical_instruction_extractor import (
    CRITICAL_KEYWORDS,
    CRITICAL_SECTION_HEADERS,
    KEYWORD_OVERLAP_FALLBACK_MIN,
    LLM_JUDGE_TIMEOUT_SECONDS,
    OPPOSING_VERBS,
    REPHRASE_CONFIDENCE_MIN,
    REPHRASE_HUMAN_REVIEW_MIN,
    SYNONYM_VERBS,
    CriticalInstruction,
    Violation,
    detect_instruction_violation,
    extract_critical_lines,
    rephrase_to_calm,
)

# ── extract_critical_lines ──────────────────────────────


class TestExtractCriticalLines:
    """extract_critical_lines の5パス。"""

    def test_keyword_match(self):
        """MUST/禁止等のキーワードを含む行を抽出する。"""
        content = """\
## Usage
Run the skill.

## Important Rules
- You MUST move old items to CHANGELOG.md
- Regular instruction here
- 古い項目は禁止事項として削除してはいけない
"""
        result = extract_critical_lines(content)
        assert len(result) >= 2
        assert all(isinstance(r, CriticalInstruction) for r in result)
        # MUST を含む行が抽出される
        must_lines = [r for r in result if "MUST" in r.original or "禁止" in r.original]
        assert len(must_lines) >= 1

    def test_section_header_match(self):
        """## Important, ## 注意 等のセクション見出し配下の行を抽出する。"""
        content = """\
## 注意事項
- old items は CHANGELOG に移動すること
- 削除は行わないこと

## Usage
Regular content here.
"""
        result = extract_critical_lines(content)
        assert len(result) >= 1
        # 「注意事項」セクション配下の行が抽出される
        assert any("移動" in r.original or "削除" in r.original for r in result)

    def test_conditional_instruction(self):
        """「〜の場合は必ず〜」のような条件付き指示を抽出する。"""
        content = """\
## Rules
- エラーの場合は必ずログを記録すること
- 通常の処理を実行する
"""
        result = extract_critical_lines(content)
        assert len(result) >= 1
        assert any("必ず" in r.original for r in result)

    def test_empty_when_no_critical(self):
        """critical キーワードがないスキルでは空リストを返す。"""
        content = """\
## Usage
Run the command and check the output.
Regular instructions only.
"""
        result = extract_critical_lines(content)
        assert result == []

    def test_bilingual_content(self):
        """日英混在のスキルで両言語の critical 行を抽出する。"""
        content = """\
## Rules
- You must always check the output
- 結果は必ず確認すること
- This is a regular line
"""
        result = extract_critical_lines(content)
        assert len(result) >= 2
        langs = {r.language for r in result}
        assert "en" in langs or "ja" in langs


# ── rephrase_to_calm ────────────────────────────────────


class TestRephraseToCalm:
    """rephrase_to_calm の5パス。"""

    @mock.patch("critical_instruction_extractor.subprocess.run")
    def test_auto_adopt_high_confidence(self, mock_run):
        """confidence >= 0.80 → 自動採用。"""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout='{"rephrased": "古い項目は削除ではなく移動する", "confidence": 0.90}',
        )
        text, confidence, action = rephrase_to_calm(
            "You MUST NOT delete old items", language="en"
        )
        assert confidence >= REPHRASE_CONFIDENCE_MIN
        assert action == "auto"
        assert len(text) > 0

    @mock.patch("critical_instruction_extractor.subprocess.run")
    def test_human_gate_medium_confidence(self, mock_run):
        """confidence 0.60-0.80 → 人間確認ゲート。"""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout='{"rephrased": "items should be moved", "confidence": 0.70}',
        )
        text, confidence, action = rephrase_to_calm(
            "NEVER delete items", language="en"
        )
        assert REPHRASE_HUMAN_REVIEW_MIN <= confidence < REPHRASE_CONFIDENCE_MIN
        assert action == "human_review"

    @mock.patch("critical_instruction_extractor.subprocess.run")
    def test_reject_low_confidence(self, mock_run):
        """confidence < 0.60 → リフレーズ不採用、元の指示を使用。"""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout='{"rephrased": "something wrong", "confidence": 0.40}',
        )
        text, confidence, action = rephrase_to_calm(
            "You MUST check output", language="en"
        )
        assert action == "reject"
        assert text == "You MUST check output"  # 元の指示がそのまま

    @mock.patch("critical_instruction_extractor.subprocess.run")
    def test_timeout_fallback(self, mock_run):
        """LLM タイムアウト → 元の指示を使用。"""
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="claude", timeout=30)
        text, confidence, action = rephrase_to_calm(
            "禁止: 削除してはいけない", language="ja"
        )
        assert action == "reject"
        assert text == "禁止: 削除してはいけない"

    @mock.patch("critical_instruction_extractor.subprocess.run")
    def test_language_preservation(self, mock_run):
        """日本語の指示は日本語でリフレーズされる。"""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout='{"rephrased": "古い項目は CHANGELOG に移動する", "confidence": 0.85}',
        )
        text, confidence, action = rephrase_to_calm(
            "古い項目は絶対に削除してはいけない", language="ja"
        )
        assert action == "auto"
        # 日本語が含まれていることを確認
        assert any(ord(c) > 0x3000 for c in text)


# ── detect_instruction_violation ────────────────────────


class TestDetectInstructionViolation:
    """detect_instruction_violation の8パス。"""

    def test_opposing_verb_match(self):
        """対立動詞検出 (move vs delete) → 確定違反。"""
        correction = {
            "message": "削除じゃなくて移動して",
            "correction_type": "stop",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="古い項目は CHANGELOG.md へ移動すること",
                rephrased="古い項目は CHANGELOG.md へ移動する",
                language="ja",
                source_line=10,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        assert result is not None
        assert isinstance(result, Violation)
        assert result.match_type == "opposing_verb"

    def test_synonym_verb_no_violation(self):
        """同義動詞 (move vs transfer) → 非違反。"""
        correction = {
            "message": "transfer ではなく move にして",
            "correction_type": "stop",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="You must move items",
                rephrased="Items should be moved",
                language="en",
                source_line=5,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        # move と transfer は同義なので違反ではない
        assert result is None

    @mock.patch("critical_instruction_extractor._call_llm_judge")
    def test_llm_judge_violation(self, mock_judge):
        """LLM Judge → 違反判定。"""
        mock_judge.return_value = {"is_violation": True, "confidence": 0.85, "reason": "指示に反している"}
        correction = {
            "message": "CHANGELOG を上書きしないで",
            "correction_type": "no",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="CHANGELOG への追記のみ行うこと",
                rephrased="CHANGELOG は追記のみ",
                language="ja",
                source_line=15,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        assert result is not None
        assert result.match_type == "llm_judge"

    @mock.patch("critical_instruction_extractor._call_llm_judge")
    def test_llm_judge_no_violation(self, mock_judge):
        """LLM Judge → 非違反判定。"""
        mock_judge.return_value = {"is_violation": False, "confidence": 0.80, "reason": "関連なし"}
        correction = {
            "message": "フォーマットを変えて",
            "correction_type": "stop",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="You must move items to CHANGELOG",
                rephrased="Items should be moved to CHANGELOG",
                language="en",
                source_line=5,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        assert result is None

    @mock.patch("critical_instruction_extractor._call_llm_judge")
    def test_llm_judge_failure_keyword_fallback_flagged(self, mock_judge):
        """LLM Judge 失敗 + keyword overlap >= 3 → 「要確認」フラグ。"""
        mock_judge.return_value = None  # 失敗
        # 対立動詞を含まないが、keyword overlap が十分な correction
        correction = {
            "message": "CHANGELOG file output items format wrong",
            "correction_type": "stop",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="output items into CHANGELOG file correctly",
                rephrased="output items into CHANGELOG file",
                language="en",
                source_line=5,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        # keyword overlap が十分なので「要確認」
        assert result is not None
        assert result.match_type == "keyword_overlap"
        assert result.needs_review is True

    @mock.patch("critical_instruction_extractor._call_llm_judge")
    def test_llm_judge_failure_low_keyword_no_violation(self, mock_judge):
        """LLM Judge 失敗 + keyword overlap < 3 → 非違反。"""
        mock_judge.return_value = None  # 失敗
        correction = {
            "message": "もっと丁寧にして",
            "correction_type": "stop",
            "last_skill": "commit",
        }
        instructions = [
            CriticalInstruction(
                original="You must move items to CHANGELOG",
                rephrased="Items should be moved to CHANGELOG",
                language="en",
                source_line=5,
            )
        ]
        result = detect_instruction_violation(correction, instructions)
        assert result is None

    def test_opposing_verb_bidirectional(self):
        """対立動詞ペアは双方向で検出される。"""
        # instruction に delete、correction に move が言及
        correction = {
            "message": "移動して、削除しないで",
            "correction_type": "stop",
            "last_skill": "cleanup",
        }
        instructions = [
            CriticalInstruction(
                original="不要なファイルは削除すること",
                rephrased="不要なファイルは削除する",
                language="ja",
                source_line=20,
            )
        ]
        # instruction は「削除」、correction は「移動して削除しないで」→ 矛盾検出
        result = detect_instruction_violation(correction, instructions)
        assert result is not None
        assert result.match_type == "opposing_verb"

    @mock.patch("critical_instruction_extractor._call_llm_judge")
    def test_false_positive_prevention_with_synonyms(self, mock_judge):
        """同義動詞ペアが false positive を防ぐ。"""
        mock_judge.return_value = {"is_violation": False, "confidence": 0.80, "reason": "同義"}
        correction = {
            "message": "generate ではなく create にして",
            "correction_type": "stop",
            "last_skill": "scaffold",
        }
        instructions = [
            CriticalInstruction(
                original="You must create the file first",
                rephrased="Create the file first",
                language="en",
                source_line=3,
            )
        ]
        # create と generate は同義なので対立動詞では検出されない
        # LLM Judge も非違反と判定
        result = detect_instruction_violation(correction, instructions)
        assert result is None
