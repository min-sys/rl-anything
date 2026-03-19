"""テキストからコードブロック外のファイルパス参照を抽出する共通モジュール。

audit.py の _extract_paths_outside_codeblocks() を共有化。
suggest_paths_frontmatter() からも利用する。
"""
import re
from typing import List, Tuple

# 既知のプロジェクトディレクトリプレフィックス（2セグメントパスフィルタ用）
KNOWN_DIR_PREFIXES = {"skills", "scripts", "hooks", ".claude", "openspec", "docs"}


def extract_paths_outside_codeblocks(text: str) -> List[Tuple[int, str]]:
    """テキストからコードブロック外のファイルパス参照を抽出する。

    Returns:
        [(line_number, path_string), ...] のリスト。行番号は1始まり。
    """
    # コードブロックの行範囲を特定
    lines = text.splitlines()
    in_codeblock = False
    codeblock_lines: set = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_codeblock = not in_codeblock
            codeblock_lines.add(i)
            continue
        if in_codeblock:
            codeblock_lines.add(i)

    # コードブロック外の行からパスを抽出
    # 相対パス (skills/update/, scripts/lib/) または絶対パス (/path/to/file)
    path_pattern = re.compile(r'(?:^|[\s`"\'])(/[a-zA-Z0-9_./-]{2,}|[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./-]+)')
    results = []
    for i, line in enumerate(lines):
        if i in codeblock_lines:
            continue
        for match in path_pattern.finditer(line):
            path_str = match.group(1).rstrip("/.,;:)")
            # 短すぎるパスやURL風のものを除外
            if len(path_str) < 3 or path_str.startswith("http"):
                continue
            # スラッシュコマンド記法 (/plugin, /rl-anything:xxx) を除外
            if path_str.startswith("/") and "/" not in path_str[1:]:
                continue
            # Python シンボル参照 (CONST/func) を除外 — 全大文字セグメントを含む場合
            segments = path_str.split("/")
            if not path_str.startswith("/") and any(s.isupper() for s in segments if s):
                continue
            # 全セグメントが数値パターンのパスを除外（HTTP ステータスコード 429/500/503、バージョン 1.0/2.1 等）
            if all(s.replace(".", "").isdigit() for s in segments if s):
                continue
            # 拡張子なしの2セグメント相対パスは既知プレフィックスで検証
            if (
                not path_str.startswith("/")
                and len(segments) == 2
                and not any("." in s for s in segments)
                and segments[0] not in KNOWN_DIR_PREFIXES
            ):
                continue
            results.append((i + 1, path_str))
    return results
