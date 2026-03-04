#!/usr/bin/env python3
"""hooks 共通ユーティリティ — DATA_DIR, ensure_data_dir, append_jsonl, read_workflow_context, classify_prompt を提供する。"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"

# ワークフロー文脈ファイルの有効期限（秒）
_WORKFLOW_CONTEXT_EXPIRE_SECONDS = 24 * 60 * 60  # 24時間


def ensure_data_dir() -> None:
    """ディレクトリが存在しない場合 MUST 自動作成する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def workflow_context_path(session_id: str) -> Path:
    """ワークフロー文脈ファイルのパスを返す。"""
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    return Path(tmpdir) / f"rl-anything-workflow-{session_id}.json"


def read_workflow_context(session_id: str) -> dict:
    """ワークフロー文脈ファイルを読み取り parent_skill/workflow_id を返す。

    文脈ファイルが存在しない、24時間以上経過、破損の場合は
    {"parent_skill": null, "workflow_id": null} を返す。
    セッションをブロックしない（MUST NOT）。
    """
    null_result = {"parent_skill": None, "workflow_id": None}
    try:
        ctx_path = workflow_context_path(session_id)
        if not ctx_path.exists():
            return null_result

        # 24時間 expire チェック
        mtime = ctx_path.stat().st_mtime
        age = datetime.now(timezone.utc).timestamp() - mtime
        if age > _WORKFLOW_CONTEXT_EXPIRE_SECONDS:
            return null_result

        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        return {
            "parent_skill": ctx.get("skill_name"),
            "workflow_id": ctx.get("workflow_id"),
        }
    except Exception as e:
        print(f"[rl-anything] read_workflow_context error: {e}", file=sys.stderr)
        return null_result


# Agent prompt を簡易分類するキーワードマップ
# 辞書の順序がカテゴリ優先順位を決定する（先にマッチした方が採用される）
PROMPT_CATEGORIES = {
    "spec-review": ["spec", "requirement", "MUST", "quality check", r"review.*spec", "仕様", "要件"],
    "code-review": [r"review.*code", r"review.*change", r"review.*impl", "alignment", "verify", "コードレビュー", "変更確認", "差分"],
    "git-ops": ["merge", "commit", "push", "pull", "branch", "rebase", "cherry-pick", "revert", "stash", r"\btag\b", "マージ", "コミット", "プッシュ", "ブランチ", "取り込"],
    "deploy": ["deploy", "release", "staging", "production", "stg", "prod", "ci/cd", "pipeline", "デプロイ", "リリース", "本番", "環境"],
    "debug": ["debug", "log", "error", "fix", "issue", "bug", "修正", "バグ", "ログ", "エラー", "なおせ", "直せ", "直して", "原因", "調査"],
    "test": ["test", "assert", "pytest", "確認", "テスト", "検証", "動作", "ブラウザ"],
    "code-exploration": ["structure", "explore", "codebase", "directory", r"find.*file", "構造", "探索", "ファイル", "読んで", "見て"],
    "research": ["research", "best practice", "latest", "how to", "pattern", "調べて", "ベストプラクティス", "最新", "方法"],
    "implementation": ["implement", "create", "build", r"write.*code", r"add.*feature", "実装", "作成", "追加", "機能", "作って"],
    "config": ["config", "setting", "setup", "env", "設定", "構成", "セットアップ", "readme"],
    "conversation": ["お願い", "続けて", "ありがと", "よろしく", "はい", "いいえ", "ok", "いいよ", "やって", "進めて", "対応して"],
}


def classify_prompt(prompt: str) -> str:
    """prompt をキーワードベースで簡易分類する。"""
    prompt_lower = prompt.lower()
    for category, keywords in PROMPT_CATEGORIES.items():
        for kw in keywords:
            if re.search(kw, prompt_lower):
                return category
    return "other"


# 修正パターン: ユーザーのフィードバックを検出するための統一辞書
# claude-reflect v3.0.1 の全パターンを統合
CORRECTION_PATTERNS = {
    # --- claude-reflect 由来: explicit（最高優先度） ---
    "remember": {"pattern": r"(?i)^remember:", "confidence": 0.90, "type": "explicit", "decay_days": 120},
    # --- claude-reflect 由来: guardrail（explicit の次に優先。correction より先に走査） ---
    "dont-unless-asked": {"pattern": r"(?i)don't (?:add|include|create) .{1,40} unless", "confidence": 0.90, "type": "guardrail", "decay_days": 120},
    "only-what-asked": {"pattern": r"(?i)only (?:change|modify|edit|touch) what I (?:asked|requested|said)", "confidence": 0.90, "type": "guardrail", "decay_days": 120},
    "stop-unrelated": {"pattern": r"(?i)stop (?:refactoring|changing|modifying|editing) (?:unrelated|other|surrounding)", "confidence": 0.90, "type": "guardrail", "decay_days": 120},
    "dont-over-engineer": {"pattern": r"(?i)don't (?:over-engineer|add extra|be too|make unnecessary)", "confidence": 0.85, "type": "guardrail", "decay_days": 90},
    "dont-refactor-unless": {"pattern": r"(?i)don't (?:refactor|reorganize|restructure) (?:unless|without)", "confidence": 0.85, "type": "guardrail", "decay_days": 90},
    "leave-alone": {"pattern": r"(?i)leave .{1,30} (?:alone|unchanged|as is)", "confidence": 0.85, "type": "guardrail", "decay_days": 90},
    "dont-add-annotations": {"pattern": r"(?i)don't (?:add|include) (?:comments|docstrings|type hints|annotations) (?:unless|to code)", "confidence": 0.85, "type": "guardrail", "decay_days": 90},
    "minimal-changes": {"pattern": r"(?i)(?:minimal|minimum|only necessary) changes", "confidence": 0.80, "type": "guardrail", "decay_days": 90},
    # --- 既存 CJK ---
    "iya": {"pattern": r"^いや[、,.\s]|^いや違", "confidence": 0.85, "type": "correction", "decay_days": 90},
    "chigau": {"pattern": r"^違う[、，,.\s]", "confidence": 0.85, "type": "correction", "decay_days": 90},
    "souja-nakute": {"pattern": r"そうじゃなく[てけ]", "confidence": 0.80, "type": "correction", "decay_days": 90},
    # --- claude-reflect 由来: positive ---
    "perfect": {"pattern": r"(?i)perfect!|exactly right|that's exactly", "confidence": 0.70, "type": "positive", "decay_days": 90},
    "great-approach": {"pattern": r"(?i)that's what I wanted|great approach", "confidence": 0.70, "type": "positive", "decay_days": 90},
    "keep-doing": {"pattern": r"(?i)keep doing this|love it|excellent|nailed it", "confidence": 0.70, "type": "positive", "decay_days": 90},
    # --- claude-reflect 由来: correction (strong) ---
    "no": {"pattern": r"^no[,. ]+", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    "dont": {"pattern": r"(?i)^don't\b|^do not\b", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    "stop": {"pattern": r"(?i)^stop\b|^never\b", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    "thats-wrong": {"pattern": r"(?i)that's (wrong|incorrect)|that is (wrong|incorrect)", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    "I-meant": {"pattern": r"(?i)^I meant\b|^I said\b", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    "I-told-you": {"pattern": r"(?i)^I told you\b|^I already told\b", "confidence": 0.85, "type": "correction", "decay_days": 120, "strong": True},
    "use-X-not-Y": {"pattern": r"(?i)use .{1,30} not\b", "confidence": 0.70, "type": "correction", "decay_days": 60, "strong": True},
    # --- claude-reflect 由来: correction (weak) ---
    "actually": {"pattern": r"(?i)^actually[,. ]", "confidence": 0.55, "type": "correction", "decay_days": 45},
}

# 偽陽性フィルター: マッチしたら correction 検出を無効化
FALSE_POSITIVE_FILTERS = [
    r"[？\?]$",  # 末尾が疑問符
    r"(?i)^(please|can you|could you|would you|help me)\b",  # タスクリクエスト
    r"(?i)(help|fix|check|review|figure out|set up)\s+(this|that|it|the)\b",  # タスク動詞
    r"(?i)(error|failed|could not|cannot|can't|unable to)\s+\w+",  # エラー記述
    r"(?i)(is|was|are|were)\s+(not|broken|failing)",  # バグ報告
    r"(?i)^I (need|want|would like)\b",  # タスクリクエスト
    r"(?i)^(ok|okay|alright)[,.]?\s+(so|now|let)",  # タスク続行
]

# メッセージ長の閾値
_MAX_CAPTURE_PROMPT_LENGTH = 500
_MIN_SHORT_CORRECTION_LENGTH = 80


def should_include_message(text: str) -> bool:
    """メッセージが correction 検出対象かどうかを判定する。

    XMLタグ、JSON、ツール結果、セッション継続メッセージ等のシステムコンテンツを除外する。
    "remember:" で始まるメッセージは長さに関わらずバイパスする。
    """
    if not text.strip():
        return False

    # "remember:" はバイパス（長さ制限を適用しない）
    if re.search(r"(?i)^remember:", text.strip()):
        return True

    # 長すぎるメッセージはスキップ
    if len(text.strip()) > _MAX_CAPTURE_PROMPT_LENGTH:
        return False

    skip_patterns = [
        r"^<",  # XMLタグ
        r"^\[",  # ブラケット
        r"^\{",  # JSON
        r"tool_result",
        r"tool_use_id",
        r"<command-",
        r"<task-notification>",
        r"<system-reminder>",
        r"This session is being continued",
        r"^Analysis:",
        r"^\*\*",  # ボールドマークダウン
        r"^   -",  # インデント済みリスト
    ]

    for pattern in skip_patterns:
        if re.search(pattern, text.strip()):
            return False

    return True


def calculate_confidence(base_confidence: float, text: str, matched_count: int = 1, has_strong: bool = False, has_i_told_you: bool = False) -> tuple[float, int]:
    """信頼度を計算する（長さ調整、パターン数・強度による調整）。

    Returns:
        (adjusted_confidence, decay_days) のタプル。
    """
    # パターン数・強度に基づく信頼度
    if has_i_told_you:
        confidence = 0.85
        decay_days = 120
    elif matched_count >= 3:
        confidence = 0.85
        decay_days = 120
    elif matched_count >= 2:
        confidence = 0.75
        decay_days = 90
    elif has_strong:
        confidence = max(base_confidence, 0.70)
        decay_days = 60
    else:
        confidence = base_confidence
        decay_days = 45

    # メッセージ長による調整
    text_length = len(text.strip())
    if text_length < _MIN_SHORT_CORRECTION_LENGTH:
        confidence = min(0.90, confidence + 0.10)
    elif text_length > 300:
        confidence = max(0.50, confidence - 0.15)
    elif text_length > 150:
        confidence = max(0.55, confidence - 0.10)

    return (confidence, decay_days)


def detect_correction(text: str):
    """テキストから修正パターンを検出する（最初のマッチのみ）。

    Returns:
        (correction_type, confidence) のタプル、または None（検出なし）。
        後方互換性のためタプルインターフェースを維持する。
    """
    text_stripped = text.strip()
    if not text_stripped:
        return None

    # 偽陽性チェック
    for fp in FALSE_POSITIVE_FILTERS:
        if re.search(fp, text_stripped) or re.search(fp, text_stripped.lower()):
            return None

    for key, info in CORRECTION_PATTERNS.items():
        pattern = info["pattern"]
        if re.search(pattern, text_stripped) or re.search(pattern, text_stripped.lower()):
            return (key, info["confidence"])

    return None


def detect_all_patterns(text: str) -> list[str]:
    """テキストから全マッチするパターンキーのリストを返す。

    信頼度計算の入力（matched_patterns フィールド）に使用する。
    """
    text_stripped = text.strip()
    if not text_stripped:
        return []

    # 偽陽性チェック
    for fp in FALSE_POSITIVE_FILTERS:
        if re.search(fp, text_stripped) or re.search(fp, text_stripped.lower()):
            return []

    matched = []
    for key, info in CORRECTION_PATTERNS.items():
        pattern = info["pattern"]
        if re.search(pattern, text_stripped) or re.search(pattern, text_stripped.lower()):
            matched.append(key)

    return matched


def last_skill_path(session_id: str) -> Path:
    """直前スキル記録ファイルのパスを返す。"""
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    return Path(tmpdir) / f"rl-anything-last-skill-{session_id}.json"


def write_last_skill(session_id: str, skill_name: str) -> None:
    """直前スキル名を一時ファイルに書き出す。"""
    try:
        path = last_skill_path(session_id)
        data = {"skill_name": skill_name, "timestamp": datetime.now(timezone.utc).isoformat()}
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception as e:
        print(f"[rl-anything] write_last_skill error: {e}", file=sys.stderr)


def read_last_skill(session_id: str) -> str | None:
    """直前スキル名を一時ファイルから読み取る。TTL 24時間。"""
    try:
        path = last_skill_path(session_id)
        if not path.exists():
            return None
        mtime = path.stat().st_mtime
        age = datetime.now(timezone.utc).timestamp() - mtime
        if age > _WORKFLOW_CONTEXT_EXPIRE_SECONDS:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("skill_name")
    except Exception as e:
        print(f"[rl-anything] read_last_skill error: {e}", file=sys.stderr)
        return None


def project_name_from_dir(project_dir: str) -> str:
    """プロジェクトディレクトリパスから末尾のディレクトリ名を返す。"""
    return Path(project_dir).name


def append_jsonl(filepath: Path, record: dict) -> None:
    """JSONL ファイルに1行追記する。失敗時はサイレント。"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything] write failed: {e}", file=sys.stderr)
