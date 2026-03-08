#!/usr/bin/env python3
"""レイヤー別診断モジュール。

Rules / Memory / Hooks / CLAUDE.md の4レイヤーを診断し、
統一フォーマット {"type", "file", "detail", "source"} で issue リストを出力する。
coherence.py の結果をアダプターパターンで再利用する。
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_plugin_root = Path(__file__).resolve().parent.parent.parent

# Jaccard 重複検出の閾値
MEMORY_DUPLICATE_JACCARD_THRESHOLD = 0.5

# Memory 内のモジュール名パターン（ファイルパスでない言及を検出）
_MODULE_PATTERN = re.compile(
    r"(?:^|\s)([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)(?:\s|$|[,、。])"
)

# ファイルパスパターン（coherence.py と同様）
_PATH_PATTERN = re.compile(
    r"(?:^|\s)([a-zA-Z_.][a-zA-Z0-9_./\-]*(?:\.(?:py|md|json|jsonl|yaml|yml|toml|sh|ts|js)|/))"
)


def _make_issue(issue_type: str, file_path: str, detail: Dict[str, Any], source: str) -> Dict[str, Any]:
    """統一フォーマットの issue を生成する。"""
    return {
        "type": issue_type,
        "file": file_path,
        "detail": detail,
        "source": source,
    }


# ---------- coherence アダプター ----------

def adapt_coherence_issues(coherence_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """coherence.py の compute_coherence_score() 結果を issue フォーマットに変換する。

    coherence.py 自体は変更しない。details dict から診断情報を抽出する。
    """
    issues: List[Dict[str, Any]] = []
    details = coherence_result.get("details", {})

    # Consistency: skill_existence.missing → claudemd_phantom_ref
    consistency = details.get("consistency", {})
    skill_existence = consistency.get("skill_existence", {})
    for name in skill_existence.get("missing", []):
        issues.append(_make_issue(
            "claudemd_phantom_ref",
            "CLAUDE.md",
            {"name": name, "ref_type": "skill", "line": 0},
            "coherence_adapter",
        ))

    # Consistency: memory_paths.stale → stale_memory
    memory_paths = consistency.get("memory_paths", {})
    for path in memory_paths.get("stale", []):
        issues.append(_make_issue(
            "stale_memory",
            "MEMORY.md",
            {"path": path, "line": 0, "context": ""},
            "coherence_adapter",
        ))

    # Efficiency: orphan_rules → orphan_rule
    efficiency = details.get("efficiency", {})
    orphan_rules = efficiency.get("orphan_rules", {})
    for rule_path in orphan_rules.get("rules", []):
        name = Path(rule_path).stem
        issues.append(_make_issue(
            "orphan_rule",
            rule_path,
            {"name": name},
            "coherence_adapter",
        ))

    return issues


# ---------- Rules 診断 ----------

def diagnose_rules(project_dir: Path, *, coherence_result: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Rules レイヤーの診断。

    - orphan_rule: どのスキル・CLAUDE.md からも参照されていない孤立ルール
    - stale_rule: ルール内の参照先が存在しない

    coherence.py の orphan_rules 結果を活用しつつ、スキル SKILL.md の参照チェックで補完する。
    """
    issues: List[Dict[str, Any]] = []
    rules_dir = project_dir / ".claude" / "rules"
    if not rules_dir.exists():
        return issues

    rule_files = list(rules_dir.glob("*.md"))
    if not rule_files:
        return issues

    # スキル SKILL.md の内容を収集
    skills_dir = project_dir / ".claude" / "skills"
    skill_contents: List[str] = []
    if skills_dir.exists():
        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                skill_contents.append(skill_md.read_text(encoding="utf-8").lower())
            except (OSError, UnicodeDecodeError):
                continue

    # CLAUDE.md の内容
    claude_md = project_dir / "CLAUDE.md"
    claude_content = ""
    if claude_md.exists():
        try:
            claude_content = claude_md.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            pass

    # coherence.py からの orphan_rules 候補
    coherence_orphans: Set[str] = set()
    if coherence_result:
        eff_details = coherence_result.get("details", {}).get("efficiency", {})
        orphan_info = eff_details.get("orphan_rules", {})
        for rule_path in orphan_info.get("rules", []):
            coherence_orphans.add(Path(rule_path).stem.lower())

    for rule_path in rule_files:
        rule_name = rule_path.stem.lower()

        # --- orphan_rule ---
        # CLAUDE.md で言及されているか
        referenced_in_claude = rule_name in claude_content

        # スキル SKILL.md で言及されているか
        referenced_in_skills = any(
            rule_name in content for content in skill_contents
        )

        if not referenced_in_claude and not referenced_in_skills:
            issues.append(_make_issue(
                "orphan_rule",
                str(rule_path),
                {"name": rule_path.stem},
                "diagnose_rules",
            ))

        # --- stale_rule ---
        try:
            content = rule_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for m in _PATH_PATTERN.finditer(line):
                ref_path = m.group(1).rstrip("/")
                if len(ref_path) < 5 or ref_path.startswith("http"):
                    continue
                if "/" not in ref_path:
                    continue
                check = project_dir / ref_path
                if not check.exists():
                    issues.append(_make_issue(
                        "stale_rule",
                        str(rule_path),
                        {"path": ref_path, "line": line_num},
                        "diagnose_rules",
                    ))

    return issues


# ---------- Memory 診断 ----------

def _tokenize(text: str) -> Set[str]:
    """テキストをトークン化する（Jaccard 係数計算用）。"""
    return set(re.findall(r"[a-zA-Z0-9\u3040-\u9fff]+", text.lower()))


def diagnose_memory(
    project_dir: Path,
    *,
    existing_stale_refs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Memory レイヤーの診断。

    - stale_memory: 陳腐化エントリ（既存 stale_ref 未カバーパターンに限定）
    - memory_duplicate: 重複セクション（Jaccard 係数ベース）
    """
    issues: List[Dict[str, Any]] = []

    # MEMORY.md を読み込み
    memory_dir = project_dir / ".claude" / "memory"
    if not memory_dir.exists():
        return issues

    memory_md = memory_dir / "MEMORY.md"
    if not memory_md.exists():
        # 他の memory ファイルも対象
        memory_files = list(memory_dir.glob("*.md"))
        if not memory_files:
            return issues
    else:
        memory_files = [memory_md]

    # 既存 stale_ref のパスセット（重複排除用）
    stale_ref_paths: Set[str] = set()
    if existing_stale_refs:
        for ref in existing_stale_refs:
            path = ref.get("detail", {}).get("path", "")
            if path:
                stale_ref_paths.add(path)

    for mem_file in memory_files:
        try:
            content = mem_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = content.splitlines()

        # --- stale_memory: モジュール名のみの言及を検出 ---
        in_code_block = False
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # ファイルパス参照は stale_ref でカバー済みなのでスキップ
            # モジュール名パターン（パスなし、拡張子なし）のみ検出
            for m in _MODULE_PATTERN.finditer(line):
                module_name = m.group(1)
                # 短すぎる、一般的な単語は除外
                if len(module_name) < 8:
                    continue
                # ドットを含むモジュール名のみ（e.g., scripts.lib.foo）
                if "." not in module_name:
                    continue
                # Python モジュールパスに変換してチェック
                module_path = module_name.replace(".", "/") + ".py"
                if module_path in stale_ref_paths:
                    continue
                check = project_dir / module_path
                if not check.exists():
                    issues.append(_make_issue(
                        "stale_memory",
                        str(mem_file),
                        {"path": module_name, "line": line_num, "context": stripped[:80]},
                        "diagnose_memory",
                    ))

        # --- memory_duplicate: セクション名の Jaccard 重複 ---
        sections: List[str] = []
        for line in lines:
            m = re.match(r"^(#{1,3})\s+(.+)", line)
            if m:
                sections.append(m.group(2).strip())

        for i in range(len(sections)):
            for j in range(i + 1, len(sections)):
                tokens_i = _tokenize(sections[i])
                tokens_j = _tokenize(sections[j])
                if not tokens_i or not tokens_j:
                    continue
                intersection = tokens_i & tokens_j
                union = tokens_i | tokens_j
                jaccard = len(intersection) / len(union) if union else 0.0
                if jaccard >= MEMORY_DUPLICATE_JACCARD_THRESHOLD:
                    issues.append(_make_issue(
                        "memory_duplicate",
                        str(mem_file),
                        {
                            "sections": [sections[i], sections[j]],
                            "similarity": round(jaccard, 2),
                        },
                        "diagnose_memory",
                    ))

    return issues


# ---------- Hooks 診断 ----------

def diagnose_hooks(project_dir: Path) -> List[Dict[str, Any]]:
    """Hooks レイヤーの診断。

    - hooks_unconfigured: settings.json に hooks 設定がない
    """
    settings_path = project_dir / ".claude" / "settings.json"
    if not settings_path.exists():
        return []

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if settings.get("hooks"):
        return []

    return [_make_issue(
        "hooks_unconfigured",
        str(settings_path),
        {"reason": "no hooks configured"},
        "diagnose_hooks",
    )]


# ---------- CLAUDE.md 診断 ----------

def diagnose_claudemd(project_dir: Path) -> List[Dict[str, Any]]:
    """CLAUDE.md レイヤーの診断。

    - claudemd_phantom_ref: 言及された Skill/Rule が存在しない
    - claudemd_missing_section: Skills セクションがないがスキルが存在する
    """
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        return []

    try:
        content = claude_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    issues: List[Dict[str, Any]] = []
    skills_dir = project_dir / ".claude" / "skills"
    rules_dir = project_dir / ".claude" / "rules"

    # プラグインスキル名を収集（除外用）
    plugin_skills = _get_plugin_skill_names(project_dir)

    # --- claudemd_phantom_ref ---
    lines = content.splitlines()

    # Skills セクション内のスキル名を抽出
    in_skills = False
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+[Ss]kills?\b", stripped):
            in_skills = True
            continue
        if in_skills and re.match(r"^#{1,3}\s+", stripped) and not re.match(
            r"^#{1,3}\s+[Ss]kills?\b", stripped
        ):
            break
        if not in_skills:
            continue

        # スキル名抽出パターン
        m = re.match(r"^[-*]\s+/?([a-zA-Z0-9_:-]+)\s*[:：]", stripped)
        if m:
            name = m.group(1)
            # plugin:skill → skill
            if ":" in name:
                name = name.split(":", 1)[1]

            # プラグインスキルは除外
            if name in plugin_skills:
                continue

            # スキルの存在確認
            if skills_dir.exists():
                skill_path = skills_dir / name
                if not skill_path.exists() and not (skill_path / "SKILL.md").exists():
                    issues.append(_make_issue(
                        "claudemd_phantom_ref",
                        "CLAUDE.md",
                        {"name": name, "ref_type": "skill", "line": line_num},
                        "diagnose_claudemd",
                    ))

    # --- claudemd_missing_section ---
    has_skills_section = bool(
        re.search(r"^#{1,3}\s+[Ss]kills?\b|^#{1,3}\s+スキル", content, re.MULTILINE)
    )
    skill_count = 0
    if skills_dir.exists():
        skill_count = len(list(skills_dir.rglob("SKILL.md")))

    if skill_count > 0 and not has_skills_section:
        issues.append(_make_issue(
            "claudemd_missing_section",
            "CLAUDE.md",
            {"section": "skills", "skill_count": skill_count},
            "diagnose_claudemd",
        ))

    return issues


def _get_plugin_skill_names(project_dir: Path) -> Set[str]:
    """プラグイン由来のスキル名を収集する。"""
    plugin_skills: Set[str] = set()
    try:
        sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
        from audit import _load_plugin_skill_map
        plugin_map = _load_plugin_skill_map()
        for skills in plugin_map.values():
            plugin_skills.update(skills)
    except (ImportError, Exception):
        pass
    return plugin_skills


# ---------- 統合エントリポイント ----------

def diagnose_all_layers(
    project_dir: Path,
    *,
    coherence_result: Optional[Dict[str, Any]] = None,
    existing_stale_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """全レイヤーの診断を実行し、レイヤー別の issue リストを返す。

    個別レイヤーがエラーでも他レイヤーは実行される。

    Returns:
        {
            "rules": [...],
            "memory": [...],
            "hooks": [...],
            "claudemd": [...],
            "coherence_adapter": [...],
        }
    """
    result: Dict[str, List[Dict[str, Any]]] = {}

    # Rules
    try:
        result["rules"] = diagnose_rules(project_dir, coherence_result=coherence_result)
    except Exception as e:
        result["rules"] = [_make_issue("error", "", {"error": str(e)}, "diagnose_rules")]

    # Memory
    try:
        result["memory"] = diagnose_memory(project_dir, existing_stale_refs=existing_stale_refs)
    except Exception as e:
        result["memory"] = [_make_issue("error", "", {"error": str(e)}, "diagnose_memory")]

    # Hooks
    try:
        result["hooks"] = diagnose_hooks(project_dir)
    except Exception as e:
        result["hooks"] = [_make_issue("error", "", {"error": str(e)}, "diagnose_hooks")]

    # CLAUDE.md
    try:
        result["claudemd"] = diagnose_claudemd(project_dir)
    except Exception as e:
        result["claudemd"] = [_make_issue("error", "", {"error": str(e)}, "diagnose_claudemd")]

    # coherence アダプター
    if coherence_result:
        try:
            result["coherence_adapter"] = adapt_coherence_issues(coherence_result)
        except Exception as e:
            result["coherence_adapter"] = [_make_issue("error", "", {"error": str(e)}, "coherence_adapter")]
    else:
        result["coherence_adapter"] = []

    return result
