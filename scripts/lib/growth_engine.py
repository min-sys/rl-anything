#!/usr/bin/env python3
"""NFD Growth Engine — Phase 判定 + 進捗率 + キャッシュ層。

NFD 論文 (arXiv:2603.10808) の Spiral Development Model を実装。
環境の成熟度を 4 フェーズで判定し、PJ 別キャッシュに保存する。
InstructionsLoaded hook はキャッシュを読むだけ（LLM コストゼロ）。
"""
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "hooks"))

try:
    import common as _common

    _DATA_DIR = _common.DATA_DIR
except ImportError:
    _DATA_DIR = Path.home() / ".claude" / "rl-anything"

# ── 定数 ────────────────────────────────────────────────────────

STALENESS_WARN_DAYS = 7
STALENESS_HIDE_DAYS = 30


# ── Phase Enum ──────────────────────────────────────────────────


class Phase(str, Enum):
    BOOTSTRAP = "bootstrap"
    INITIAL_NURTURING = "initial_nurturing"
    STRUCTURED_NURTURING = "structured_nurturing"
    MATURE_OPERATION = "mature_operation"


PHASE_DISPLAY_NAMES: Dict[Phase, Dict[str, str]] = {
    Phase.BOOTSTRAP: {"en": "Bootstrap", "ja": "初期構築"},
    Phase.INITIAL_NURTURING: {"en": "Initial Nurturing", "ja": "初期育成"},
    Phase.STRUCTURED_NURTURING: {"en": "Structured Nurturing", "ja": "構造化育成"},
    Phase.MATURE_OPERATION: {"en": "Mature Operation", "ja": "成熟運用"},
}


# ── データクラス ────────────────────────────────────────────────


@dataclass
class PhaseInfo:
    phase: Phase
    display_name: str
    display_name_ja: str
    progress: float  # 0.0-1.0


# ── 内部ヘルパー ────────────────────────────────────────────────


def _data_dir() -> Path:
    return _DATA_DIR


def _cache_path(project: str) -> Path:
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", project) if project else "unknown"
    return _data_dir() / f"growth-state-{safe_name}.json"


# ── Phase 判定 ──────────────────────────────────────────────────


def detect_phase(
    sessions_count: int,
    corrections_count: int,
    crystallized_rules: int,
    coherence_score: float,
) -> Phase:
    """降順で評価 (Mature → Structured → Initial → Bootstrap)。
    最初にマッチしたフェーズを返す。どれにもマッチしなければ Bootstrap。
    """
    # Mature Operation
    if (
        sessions_count > 200
        and crystallized_rules >= 10
        and coherence_score >= 0.7
    ):
        return Phase.MATURE_OPERATION

    # Structured Nurturing
    if (
        sessions_count >= 50
        and corrections_count >= 10
        and crystallized_rules >= 3
    ):
        return Phase.STRUCTURED_NURTURING

    # Initial Nurturing
    if sessions_count >= 10:
        return Phase.INITIAL_NURTURING

    # Bootstrap (fallback)
    return Phase.BOOTSTRAP


# ── 進捗率 ──────────────────────────────────────────────────────


def compute_phase_progress(
    phase: Phase,
    sessions_count: int,
    corrections_count: int,
    crystallized_rules: int,
    coherence_score: float,
) -> float:
    """フェーズ内での進捗率 (0.0-1.0)。次フェーズの条件に対する達成度。"""
    if phase == Phase.MATURE_OPERATION:
        return 1.0

    if phase == Phase.BOOTSTRAP:
        # 次フェーズ (Initial) の条件: sessions >= 10
        return min(1.0, sessions_count / 10.0)

    if phase == Phase.INITIAL_NURTURING:
        # 次フェーズ (Structured) の条件:
        #   sessions >= 50, corrections >= 10, crystallized_rules >= 3
        s = min(1.0, sessions_count / 50.0)
        c = min(1.0, corrections_count / 10.0)
        r = min(1.0, crystallized_rules / 3.0)
        return (s + c + r) / 3.0

    if phase == Phase.STRUCTURED_NURTURING:
        # 次フェーズ (Mature) の条件:
        #   sessions > 200, crystallized_rules >= 10, coherence >= 0.7
        s = min(1.0, sessions_count / 200.0)
        r = min(1.0, crystallized_rules / 10.0)
        co = min(1.0, coherence_score / 0.7)
        return (s + r + co) / 3.0

    return 0.0


# ── PhaseInfo 生成 ──────────────────────────────────────────────


def compute_phase_info(
    sessions_count: int,
    corrections_count: int,
    crystallized_rules: int,
    coherence_score: float,
) -> PhaseInfo:
    """テレメトリデータから PhaseInfo を生成する。"""
    phase = detect_phase(
        sessions_count, corrections_count, crystallized_rules, coherence_score
    )
    progress = compute_phase_progress(
        phase, sessions_count, corrections_count, crystallized_rules, coherence_score
    )
    names = PHASE_DISPLAY_NAMES[phase]
    return PhaseInfo(
        phase=phase,
        display_name=names["en"],
        display_name_ja=names["ja"],
        progress=round(progress, 2),
    )


# ── キャッシュ ──────────────────────────────────────────────────


def update_cache(
    project: str,
    phase: Phase,
    progress: float,
    extra: Dict[str, Any],
) -> None:
    """PJ 別キャッシュファイルに書き込み。"""
    path = _cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "phase": phase.value,
        "progress": round(progress, 4),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_cache(project: str) -> Optional[Dict[str, Any]]:
    """PJ 別キャッシュファイルを読み取り。

    Returns:
        None: ファイル未存在 / parse エラー / 30日超 staleness
        dict: キャッシュデータ。7日超の場合 stale=True 付き
    """
    path = _cache_path(project)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # staleness チェック
    updated_at_str = data.get("updated_at", "")
    if updated_at_str:
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
            now = datetime.now(timezone.utc)
            age_days = (now - updated_at).days

            if age_days > STALENESS_HIDE_DAYS:
                return None
            if age_days > STALENESS_WARN_DAYS:
                data["stale"] = True
                data["stale_days"] = age_days
        except (ValueError, TypeError):
            pass

    return data
