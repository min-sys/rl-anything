"""audit.py の project フィルタリングテスト。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

import audit


@pytest.fixture(autouse=True)
def reset_cache():
    audit._plugin_skill_map_cache = None
    yield
    audit._plugin_skill_map_cache = None


@pytest.fixture
def usage_data_dir(tmp_path):
    """プロジェクトフィールド付き usage.jsonl を含むデータディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"skill_name": "my-skill", "project": "atlas", "timestamp": now},
        {"skill_name": "my-skill", "project": "atlas", "timestamp": now},
        {"skill_name": "other-skill", "project": "beta", "timestamp": now},
        {"skill_name": "my-skill", "project": None, "timestamp": now},
    ]
    (data_dir / "usage.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )
    return data_dir


class TestLoadUsageDataProject:
    """load_usage_data の project フィルタテスト。"""

    def test_project_scoped(self, usage_data_dir):
        with mock.patch.object(audit, "DATA_DIR", usage_data_dir):
            records = audit.load_usage_data(project_root=Path("/Users/foo/atlas"))
        assert len(records) == 2
        assert all(r["project"] == "atlas" for r in records)

    def test_global_includes_all(self, usage_data_dir):
        """project_root 未指定時は全レコードを対象。"""
        with mock.patch.object(audit, "DATA_DIR", usage_data_dir):
            records = audit.load_usage_data()
        assert len(records) == 4

    def test_project_excludes_null(self, usage_data_dir):
        """project フィルタ指定時、null レコードは除外される。"""
        with mock.patch.object(audit, "DATA_DIR", usage_data_dir):
            records = audit.load_usage_data(project_root=Path("/Users/foo/atlas"))
        projects = [r.get("project") for r in records]
        assert None not in projects
