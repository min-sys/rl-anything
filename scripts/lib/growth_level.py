#!/usr/bin/env python3
"""NFD Growth Level — env_score → レベル + 称号 + XP 進捗。

environment fitness score (0.0-1.0) を 10 段階のレベルにマッピングし、
セッション greeting と audit --growth で表示する。
"""
from dataclasses import dataclass
from typing import Tuple

# ── 定数 ────────────────────────────────────────────────────────

# (threshold, level, title_en, title_ja)
LEVEL_THRESHOLDS: list[Tuple[float, int, str, str]] = [
    (0.0, 1, "Seedling", "芽生え"),
    (0.15, 2, "Sprout", "若芽"),
    (0.25, 3, "Sapling", "苗木"),
    (0.35, 4, "Growing", "成長中"),
    (0.45, 5, "Established", "定着"),
    (0.55, 6, "Flourishing", "開花"),
    (0.65, 7, "Experienced", "熟達"),
    (0.75, 8, "Veteran", "歴戦"),
    (0.82, 9, "Master", "達人"),
    (0.90, 10, "Evolutionist", "進化の体現者"),
]


# ── データクラス ────────────────────────────────────────────────


@dataclass
class LevelInfo:
    level: int  # 1-10
    title_en: str
    title_ja: str
    threshold: float  # このレベルの下限スコア
    env_score: float  # 現在のスコア


@dataclass
class XPProgress:
    current_level: LevelInfo
    next_threshold: float  # 次レベルの下限（Lv.10 なら 1.0）
    progress: float  # 0.0-1.0
    score_needed: float  # 次レベルまでの差分


# ── レベル計算 ──────────────────────────────────────────────────


def compute_level(env_score: float) -> LevelInfo:
    """environment fitness score → レベル + 称号。

    降順で評価し、最初にマッチしたレベルを返す。
    env_score < 0 は Lv.1 にクランプ。
    """
    score = max(0.0, env_score)

    # 降順で走査して最初にマッチする閾値を見つける
    matched = LEVEL_THRESHOLDS[0]  # フォールバック: Lv.1
    for entry in LEVEL_THRESHOLDS:
        if score >= entry[0]:
            matched = entry
        else:
            break

    threshold, level, title_en, title_ja = matched
    return LevelInfo(
        level=level,
        title_en=title_en,
        title_ja=title_ja,
        threshold=threshold,
        env_score=score,
    )


def compute_xp_progress(env_score: float) -> XPProgress:
    """次のレベルまでの進捗率。

    Lv.10 の場合は progress=1.0, score_needed=0.0。
    """
    level_info = compute_level(env_score)

    if level_info.level >= 10:
        return XPProgress(
            current_level=level_info,
            next_threshold=1.0,
            progress=1.0,
            score_needed=0.0,
        )

    # 次レベルの閾値を取得
    next_entry = LEVEL_THRESHOLDS[level_info.level]  # level は 1-indexed
    next_threshold = next_entry[0]

    span = next_threshold - level_info.threshold
    if span <= 0:
        progress = 1.0
    else:
        progress = (level_info.env_score - level_info.threshold) / span
        progress = max(0.0, min(1.0, progress))

    score_needed = max(0.0, next_threshold - level_info.env_score)

    return XPProgress(
        current_level=level_info,
        next_threshold=next_threshold,
        progress=round(progress, 4),
        score_needed=round(score_needed, 4),
    )
