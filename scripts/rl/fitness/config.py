"""Fitness 関数の共有設定。各モジュールはここから閾値を読み込む。"""

# Coherence
COHERENCE_THRESHOLDS = {
    "skill_min_lines": 50,
    "rule_max_lines": 3,
    "claude_md_max_lines": 200,
    "near_limit_pct": 0.80,
    "unused_skill_days": 30,
    "advice_threshold": 0.7,
}

# Telemetry
TELEMETRY_THRESHOLDS = {
    "min_sessions": 30,
    "min_days": 7,
    "implicit_reward_window_sec": 60,
}

# Constitutional
CONSTITUTIONAL_THRESHOLDS = {
    "min_coverage_for_eval": 0.5,
    "llm_timeout_sec": 60,
}

# Chaos
CHAOS_THRESHOLDS = {
    "critical_delta": 0.10,
    "spof_delta": 0.15,
    "low_delta": 0.02,
}

# Principles
PRINCIPLES_THRESHOLDS = {
    "min_coverage_for_eval": 0.5,
    "min_principle_quality": 0.3,
}

# Environment — 動的重み計算のベース重み
BASE_WEIGHTS = {
    "coherence": 0.23,
    "telemetry": 0.43,
    "constitutional": 0.29,
    "skill_quality": 0.05,
}
