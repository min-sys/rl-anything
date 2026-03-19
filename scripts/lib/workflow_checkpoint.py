"""ワークフローチェックポイント検出エンジン + テンプレートカタログ。

workflow_checkpoint（検出）→ discover（走査）→ evolve（変換）→ remediation（修正）
の4層で共有する。
"""
import json
import logging
import re
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── DATA_DIR（テスト時 mock 対象）──────────────────────
import os as _os

_PLUGIN_DATA_ENV = _os.environ.get("CLAUDE_PLUGIN_DATA", "")
DATA_DIR = Path(_PLUGIN_DATA_ENV) if _PLUGIN_DATA_ENV else Path.home() / ".claude" / "rl-anything"

# ── 閾値定数 ──────────────────────────────────────────
MIN_CHECKPOINT_EVIDENCE = 2
CHECKPOINT_DETECTION_TIMEOUT_SECONDS = 5
BASE_CHECKPOINT_CONFIDENCE = 0.5
EVIDENCE_BONUS_PER_COUNT = 0.05
MAX_EVIDENCE_BONUS = 0.25
GATE_BONUS = 0.1

# ── ワークフロー判定パターン ──────────────────────────
_STEP_KEYWORDS_RE = re.compile(
    r"(?:Step|Phase|ステップ|フェーズ)", re.IGNORECASE
)
_NUMBERED_LIST_RE = re.compile(r"^\d+\.\s+", re.MULTILINE)
_IO_KEYWORDS_RE = re.compile(r"(?:Input|Output|入力|出力)", re.IGNORECASE)


# ── frontmatter 解析 ──────────────────────────────────

def _parse_frontmatter_type(skill_md_path: Path) -> Optional[str]:
    """SKILL.md から frontmatter の type フィールドを取得する。"""
    try:
        content = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except (PermissionError, OSError):
        return None

    if not content.startswith("---"):
        return None

    end = content.find("---", 3)
    if end == -1:
        return None

    fm_block = content[3:end]
    for line in fm_block.splitlines():
        line = line.strip()
        if line.startswith("type:"):
            return line[5:].strip()
    return None


# ── ワークフロースキル判定 ────────────────────────────

def is_workflow_skill(skill_dir: Path) -> bool:
    """SKILL.md からワークフロースキルを判定する。

    判定ロジック:
    1. frontmatter type: workflow → 即 True
    2. ヒューリスティクスフォールバック:
       - 基準A: Step/Phase/ステップ/フェーズ が numbered list 内に存在
       - 基準B: numbered list 3項目以上
       - 基準A+B → True, 基準A + 5項目以上 → True
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False

    # 1. frontmatter 優先
    fm_type = _parse_frontmatter_type(skill_md)
    if fm_type == "workflow":
        return True

    # 2. ヒューリスティクス
    try:
        content = skill_md.read_text(encoding="utf-8", errors="ignore")
    except (PermissionError, OSError):
        return False

    # 基準A: Step/Phase キーワードが numbered list 行に存在
    numbered_lines = _NUMBERED_LIST_RE.findall(content)
    numbered_count = len(numbered_lines)

    # numbered list の各行にステップキーワードがあるか
    has_step_in_numbered = False
    for match in _NUMBERED_LIST_RE.finditer(content):
        line_start = match.start()
        line_end = content.find("\n", line_start)
        if line_end == -1:
            line_end = len(content)
        line_text = content[line_start:line_end]
        if _STEP_KEYWORDS_RE.search(line_text):
            has_step_in_numbered = True
            break

    # 基準A が成立しない場合、content 全体に Step/Phase があるかチェック
    has_step_keyword = has_step_in_numbered or bool(_STEP_KEYWORDS_RE.search(content))

    criteria_a = has_step_in_numbered
    criteria_b = numbered_count >= 3

    # 基準A+B → True
    if criteria_a and criteria_b:
        return True

    # 基準A（content 全体）+ 5項目以上 → True
    if has_step_keyword and numbered_count >= 5:
        return True

    return False


# ── チェックポイント検出キーワード ────────────────────

_INFRA_DEPLOY_KEYWORDS = re.compile(
    r"(?:deploy|デプロイ|prod|本番|hotswap|cdk|cloudformation|stack)",
    re.IGNORECASE,
)
_DATA_MIGRATION_KEYWORDS = re.compile(
    r"(?:migration|マイグレーション|schema|スキーマ|prisma|alembic|migrate)",
    re.IGNORECASE,
)
_EXTERNAL_API_KEYWORDS = re.compile(
    r"(?:API|endpoint|webhook|外部|downstream|breaking\s*change|互換性)",
    re.IGNORECASE,
)
_SECRET_ROTATION_KEYWORDS = re.compile(
    r"(?:secret|シークレット|credential|認証|token|API\s*key|rotate)",
    re.IGNORECASE,
)

# ── 既存チェック検出キーワード ────────────────────────

_EXISTING_CHECK_PATTERNS = {
    "infra_deploy": re.compile(r"(?:deploy|デプロイ|本番|prod)", re.IGNORECASE),
    "data_migration": re.compile(r"(?:migration|マイグレーション|schema|スキーマ)", re.IGNORECASE),
    "external_api": re.compile(r"(?:API\s*(?:影響|確認|互換)|external|外部)", re.IGNORECASE),
    "secret_rotation": re.compile(r"(?:secret|シークレット|credential|認証)", re.IGNORECASE),
}


# ── 検出関数 ──────────────────────────────────────────

def _match_keywords(records: List[Dict], keyword_re: re.Pattern, skill_name: str) -> int:
    """records から last_skill でフィルタし、キーワードマッチ件数を返す。"""
    count = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if rec.get("last_skill", "") != skill_name:
            continue
        text = rec.get("correction", "") or rec.get("message", "") or rec.get("error", "")
        if keyword_re.search(text):
            count += 1
    return count


def _match_error_keywords(records: List[Dict], keyword_re: re.Pattern) -> int:
    """errors.jsonl のレコードからキーワードマッチ件数を返す（skill フィルタなし）。"""
    count = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        text = rec.get("error", "") or rec.get("message", "")
        if keyword_re.search(text):
            count += 1
    return count


def detect_infra_deploy_gap(
    corrections: List[Dict], errors: List[Dict], skill_name: str, project_dir: Path,
) -> Dict[str, Any]:
    """infra_deploy チェックポイントのギャップ検出。"""
    try:
        from verification_catalog import detect_iac_project
    except ImportError:
        from lib.verification_catalog import detect_iac_project

    iac_result = detect_iac_project(project_dir)
    if not iac_result.get("is_iac", False):
        return {"applicable": False, "evidence_count": 0, "gate_passed": False}

    count = _match_keywords(corrections, _INFRA_DEPLOY_KEYWORDS, skill_name)
    count += _match_error_keywords(errors, _INFRA_DEPLOY_KEYWORDS)
    return {"applicable": True, "evidence_count": count, "gate_passed": True}


def detect_data_migration_gap(
    corrections: List[Dict], errors: List[Dict], skill_name: str, project_dir: Path,
) -> Dict[str, Any]:
    """data_migration チェックポイントのギャップ検出。"""
    # applicability gate: DB 関連ファイルの存在チェック
    db_markers = [
        "prisma/schema.prisma",
        "alembic",
        "migrations",
    ]
    db_config_markers = ["knexfile", "ormconfig", "data-source", "drizzle.config"]

    gate_passed = False
    for marker in db_markers:
        if (project_dir / marker).exists():
            gate_passed = True
            break

    if not gate_passed:
        # knex/typeorm/drizzle はファイル名パターンチェック
        try:
            for f in project_dir.iterdir():
                if f.is_file():
                    name_lower = f.name.lower()
                    if any(m in name_lower for m in db_config_markers):
                        gate_passed = True
                        break
        except (PermissionError, OSError):
            pass

    if not gate_passed:
        return {"applicable": False, "evidence_count": 0, "gate_passed": False}

    count = _match_keywords(corrections, _DATA_MIGRATION_KEYWORDS, skill_name)
    count += _match_error_keywords(errors, _DATA_MIGRATION_KEYWORDS)
    return {"applicable": True, "evidence_count": count, "gate_passed": True}


def detect_external_api_gap(
    corrections: List[Dict], errors: List[Dict], skill_name: str, project_dir: Path,
) -> Dict[str, Any]:
    """external_api チェックポイントのギャップ検出。常時適用。"""
    count = _match_keywords(corrections, _EXTERNAL_API_KEYWORDS, skill_name)
    count += _match_error_keywords(errors, _EXTERNAL_API_KEYWORDS)
    return {"applicable": True, "evidence_count": count, "gate_passed": False}


def detect_secret_rotation_gap(
    corrections: List[Dict], errors: List[Dict], skill_name: str, project_dir: Path,
) -> Dict[str, Any]:
    """secret_rotation チェックポイントのギャップ検出。常時適用。"""
    count = _match_keywords(corrections, _SECRET_ROTATION_KEYWORDS, skill_name)
    count += _match_error_keywords(errors, _SECRET_ROTATION_KEYWORDS)
    return {"applicable": True, "evidence_count": count, "gate_passed": False}


# ── Detection Dispatch ─────────────────────────────────

_CHECKPOINT_DETECTION_DISPATCH: Dict[str, Any] = {
    "detect_infra_deploy_gap": detect_infra_deploy_gap,
    "detect_data_migration_gap": detect_data_migration_gap,
    "detect_external_api_gap": detect_external_api_gap,
    "detect_secret_rotation_gap": detect_secret_rotation_gap,
}

# ── テンプレートカタログ ──────────────────────────────

CHECKPOINT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "infra-deploy-checkpoint",
        "category": "infra_deploy",
        "description": "インフラ変更のデプロイ確認チェックポイント",
        "detection_fn": "detect_infra_deploy_gap",
        "applicability": "detect_iac_project",
        "template": (
            "**インフラデプロイ確認**: インフラ変更が含まれる場合、"
            "対象環境（dev/staging/prod）への反映状態を確認する。"
            "未反映の場合はデプロイを実行するか、明示的にスキップ理由を記録する。"
        ),
    },
    {
        "id": "data-migration-checkpoint",
        "category": "data_migration",
        "description": "DBスキーマ変更のマイグレーション確認チェックポイント",
        "detection_fn": "detect_data_migration_gap",
        "applicability": "detect_db_project",
        "template": (
            "**データマイグレーション確認**: スキーマ変更が含まれる場合、"
            "マイグレーションの実行状態を確認する。"
            "ロールバック手順が存在するか、データ損失リスクがないかを検証する。"
        ),
    },
    {
        "id": "external-api-checkpoint",
        "category": "external_api",
        "description": "外部API影響のロールバック確認チェックポイント",
        "detection_fn": "detect_external_api_gap",
        "applicability": None,
        "template": (
            "**外部API影響確認**: API インターフェースの変更が含まれる場合、"
            "下流サービスへの影響を確認する。"
            "破壊的変更がある場合はバージョニングまたは移行期間を設ける。"
        ),
    },
    {
        "id": "secret-rotation-checkpoint",
        "category": "secret_rotation",
        "description": "シークレット/認証情報変更の確認チェックポイント",
        "detection_fn": "detect_secret_rotation_gap",
        "applicability": None,
        "template": (
            "**シークレット確認**: 認証情報・シークレットの変更が含まれる場合、"
            "ローテーション手順に従い、旧情報の無効化と新情報の配布を確認する。"
            "環境ごと（dev/staging/prod）の更新状態を検証する。"
        ),
    },
]


def get_checkpoint_template(category: str) -> Optional[Dict[str, Any]]:
    """カテゴリ名でカタログエントリを取得する。見つからない場合は None。"""
    for entry in CHECKPOINT_CATALOG:
        if entry["category"] == category:
            return entry
    return None


# ── confidence 計算 ───────────────────────────────────

def _compute_confidence(evidence_count: int, gate_passed: bool) -> float:
    """チェックポイントギャップの confidence スコアを計算する。

    上限 0.85（proposable 分類を保証）。
    """
    score = BASE_CHECKPOINT_CONFIDENCE
    score += min(evidence_count * EVIDENCE_BONUS_PER_COUNT, MAX_EVIDENCE_BONUS)
    if gate_passed:
        score += GATE_BONUS
    return min(score, 0.85)


# ── SKILL.md 既存チェック判定 ─────────────────────────

def _has_existing_check(skill_dir: Path, category: str) -> bool:
    """SKILL.md にカテゴリ対応の既存チェックステップがあるか判定する。"""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return False

    pattern = _EXISTING_CHECK_PATTERNS.get(category)
    if not pattern:
        return False

    try:
        content = skill_md.read_text(encoding="utf-8", errors="ignore")
        return bool(pattern.search(content))
    except (PermissionError, OSError):
        return False


# ── テレメトリ読み込み ────────────────────────────────

def _load_jsonl(filepath: Path) -> List[Dict]:
    """JSONL ファイルを読み込む。存在しない/空なら空リスト。"""
    if not filepath.exists():
        return []
    records = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except (PermissionError, OSError):
        pass
    return records


# ── メイン検出関数 ────────────────────────────────────

class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError("checkpoint detection timeout")


def detect_checkpoint_gaps(
    skill_name: str,
    skill_dir: Path,
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """ワークフロースキルのチェックポイントギャップを検出する。

    Returns:
        ギャップのリスト。各エントリ:
        {"category": str, "evidence_count": int, "confidence": float,
         "template": str, "description": str}
    """
    # タイムアウト保護（SIGALRM が使える場合のみ）
    use_alarm = hasattr(signal, "SIGALRM")
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(CHECKPOINT_DETECTION_TIMEOUT_SECONDS)

    try:
        return _detect_gaps_impl(skill_name, skill_dir, project_dir)
    except _TimeoutError:
        logger.warning("checkpoint detection timed out for skill=%s", skill_name)
        return []
    except Exception as e:
        logger.warning("checkpoint detection error: %s", e)
        return []
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def _detect_gaps_impl(
    skill_name: str,
    skill_dir: Path,
    project_dir: Path,
) -> List[Dict[str, Any]]:
    """ギャップ検出の実装。"""
    corrections = _load_jsonl(DATA_DIR / "corrections.jsonl")
    errors = _load_jsonl(DATA_DIR / "errors.jsonl")

    gaps: List[Dict[str, Any]] = []

    for entry in CHECKPOINT_CATALOG:
        category = entry["category"]

        # 既存チェックがあればスキップ
        if _has_existing_check(skill_dir, category):
            continue

        # detection_fn 実行
        fn_name = entry["detection_fn"]
        fn = _CHECKPOINT_DETECTION_DISPATCH.get(fn_name)
        if fn is None:
            continue

        result = fn(corrections, errors, skill_name, project_dir)
        if not result.get("applicable", False):
            continue

        evidence_count = result.get("evidence_count", 0)
        if evidence_count < MIN_CHECKPOINT_EVIDENCE:
            continue

        gate_passed = result.get("gate_passed", False)
        confidence = _compute_confidence(evidence_count, gate_passed)

        gaps.append({
            "category": category,
            "evidence_count": evidence_count,
            "confidence": confidence,
            "template": entry["template"],
            "description": entry["description"],
        })

    return gaps
