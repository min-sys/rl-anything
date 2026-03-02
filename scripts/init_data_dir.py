#!/usr/bin/env python3
"""~/.claude/rl-anything/ ディレクトリの初期化スクリプト。

観測データ・アーカイブ・フィードバックドラフト用のディレクトリを作成し、
.gitignore を配置する。
"""
import os
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"

SUBDIRS = [
    "archive",
    "feedback-drafts",
]

GITIGNORE_CONTENT = """\
# rl-anything data directory — machine-generated, not version-controlled
*
!.gitignore
"""


def init_data_dir() -> Path:
    """データディレクトリを初期化して返す。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (DATA_DIR / sub).mkdir(exist_ok=True)

    gitignore = DATA_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE_CONTENT)

    return DATA_DIR


if __name__ == "__main__":
    path = init_data_dir()
    print(f"Initialized: {path}")
