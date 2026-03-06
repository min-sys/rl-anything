"""classify_prompt() の conversation サブカテゴリテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common


class TestConversationSubcategories:
    """conversation サブカテゴリの分類テスト。"""

    def test_approval_hai(self):
        assert common.classify_prompt("はい") == "conversation:approval"

    def test_approval_iie(self):
        assert common.classify_prompt("いいえ") == "conversation:approval"

    def test_approval_ok(self):
        assert common.classify_prompt("ok") == "conversation:approval"

    def test_approval_iiyo(self):
        assert common.classify_prompt("いいよ") == "conversation:approval"

    def test_approval_yoroshiku(self):
        assert common.classify_prompt("よろしく") == "conversation:approval"

    def test_approval_saiyo(self):
        assert common.classify_prompt("採用") == "conversation:approval"

    def test_approval_accept(self):
        assert common.classify_prompt("accept") == "conversation:approval"

    def test_confirmation_onegai(self):
        assert common.classify_prompt("お願い") == "conversation:confirmation"

    def test_confirmation_yatte(self):
        assert common.classify_prompt("やって") == "conversation:confirmation"

    def test_confirmation_susumete(self):
        assert common.classify_prompt("進めて") == "conversation:confirmation"

    def test_confirmation_taioshite(self):
        assert common.classify_prompt("対応して") == "conversation:confirmation"

    def test_confirmation_tsuzukete(self):
        assert common.classify_prompt("続けて") == "conversation:confirmation"

    def test_question_naze(self):
        assert common.classify_prompt("なぜ") == "conversation:question"

    def test_question_oshiete(self):
        assert common.classify_prompt("教えて") == "conversation:question"

    def test_question_mark(self):
        assert common.classify_prompt("これは何？") == "conversation:question"

    def test_direction_koushite(self):
        assert common.classify_prompt("こうして") == "conversation:direction"

    def test_direction_yamete(self):
        assert common.classify_prompt("やめて") == "conversation:direction"

    def test_direction_kaete(self):
        assert common.classify_prompt("変えて") == "conversation:direction"

    def test_direction_kawarini(self):
        assert common.classify_prompt("代わりに") == "conversation:direction"

    def test_direction_dewanaku(self):
        assert common.classify_prompt("ではなく") == "conversation:direction"

    def test_thanks_arigatou(self):
        assert common.classify_prompt("ありがとう") == "conversation:thanks"

    def test_thanks_kansha(self):
        assert common.classify_prompt("感謝します") == "conversation:thanks"

    def test_thanks_thx(self):
        assert common.classify_prompt("thx") == "conversation:thanks"

    def test_thanks_thanks(self):
        assert common.classify_prompt("thanks") == "conversation:thanks"

    def test_thanks_sankusu(self):
        assert common.classify_prompt("サンクス") == "conversation:thanks"


class TestConversationFallback:
    """conversation フォールバックテスト。"""

    def test_no_match_returns_other(self):
        """conversation キーワードにマッチしないプロンプトは other を返す。"""
        assert common.classify_prompt("ランダムなテキスト") == "other"

    def test_other_category_takes_priority(self):
        """他カテゴリのキーワードが先にマッチした場合はそちらが返る。"""
        result = common.classify_prompt("テストを実装して")
        assert result == "test"


class TestSubcategoryPriority:
    """サブカテゴリの挿入順優先度テスト。"""

    def test_approval_before_confirmation(self):
        """「はい、お願いします」→ approval（挿入順で先）。"""
        result = common.classify_prompt("はい、お願いします")
        assert result == "conversation:approval"

    def test_approval_before_thanks(self):
        """「ok、ありがとう」→ approval（挿入順で先）。"""
        result = common.classify_prompt("ok、ありがとう")
        assert result == "conversation:approval"

    def test_all_conversation_keywords_are_subcategorized(self):
        """旧 conversation の全キーワードがいずれかのサブカテゴリに含まれる。"""
        old_keywords = ["お願い", "続けて", "ありがと", "よろしく", "はい", "いいえ", "ok", "いいよ", "やって", "進めて", "対応して"]
        for kw in old_keywords:
            result = common.classify_prompt(kw)
            assert result.startswith("conversation:"), f"'{kw}' should be conversation subcategory, got '{result}'"
