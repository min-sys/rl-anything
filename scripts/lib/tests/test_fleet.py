"""fleet モジュールのユニットテスト。

Phase 1 で必須の 5 関数をカバー:
- resolve_auto_memory_dir
- enumerate_projects
- classify_project
- run_audit_subprocess
- format_status_table

特殊文字を含むパスは Phase 3 で扱う（本テストは扱わない）。
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from fleet import (  # noqa: E402
    AUDIT_ERROR,
    AUDIT_OK,
    AUDIT_TIMEOUT,
    STATUS_ENABLED,
    STATUS_NOT_ENABLED,
    STATUS_STALE,
    AuditResult,
    FleetRow,
    classify_project,
    enumerate_projects,
    format_status_table,
    resolve_auto_memory_dir,
    run_audit_subprocess,
)


class TestResolveAutoMemoryDir:
    """resolve_auto_memory_dir() の命名規則逆引きテスト。"""

    def test_通常のPJパス(self):
        pj = Path("/Users/foo/matsukaze-utils/bots")
        result = resolve_auto_memory_dir(pj)
        assert result == Path.home() / ".claude" / "projects" / "-Users-foo-matsukaze-utils-bots"

    def test_実測_rl_anything_PJ(self):
        """~/.claude/projects/ 内に実在するはずの slug と一致する。"""
        pj = Path("/Users/matsukaze-takashi/matsukaze-utils/rl-anything")
        result = resolve_auto_memory_dir(pj)
        expected = Path.home() / ".claude" / "projects" / "-Users-matsukaze-takashi-matsukaze-utils-rl-anything"
        assert result == expected

    def test_trailing_slash_正規化(self):
        """末尾スラッシュは除去されて同じ結果になる。"""
        with_slash = Path("/Users/foo/bar/")
        without_slash = Path("/Users/foo/bar")
        assert resolve_auto_memory_dir(with_slash) == resolve_auto_memory_dir(without_slash)

    def test_相対パスは絶対化される(self):
        """相対パスを渡されたら resolve して絶対パスに揃える。"""
        rel = Path("./somewhere")
        result = resolve_auto_memory_dir(rel)
        # resolve した absolute path が `-` 区切りで slug 化されている
        abs_str = str(rel.resolve())
        expected = Path.home() / ".claude" / "projects" / abs_str.replace("/", "-")
        assert result == expected


class TestEnumerateProjects:
    """enumerate_projects() の PJ 列挙フィルタテスト。"""

    def test_両方持ちとCLAUDE_md単体と_claude_単体を含み両方無しを除外(self, tmp_path):
        (tmp_path / "both" / ".claude").mkdir(parents=True)
        (tmp_path / "both" / "CLAUDE.md").write_text("")
        (tmp_path / "claude_md_only" / "CLAUDE.md").parent.mkdir()
        (tmp_path / "claude_md_only" / "CLAUDE.md").write_text("")
        (tmp_path / "dot_claude_only" / ".claude").mkdir(parents=True)
        (tmp_path / "neither").mkdir()
        result = enumerate_projects(tmp_path)
        names = [p.name for p in result]
        assert names == ["both", "claude_md_only", "dot_claude_only"]

    def test_rootが存在しなければ空リスト(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        assert enumerate_projects(missing) == []

    def test_ファイルは除外_子ディレクトリのみ対象(self, tmp_path):
        (tmp_path / "pj" / ".claude").mkdir(parents=True)
        (tmp_path / "CLAUDE.md").write_text("")  # root 直下のファイルは対象外
        result = enumerate_projects(tmp_path)
        assert [p.name for p in result] == ["pj"]

    def test_ドットディレクトリは除外(self, tmp_path):
        """`.worktrees` のようなドットディレクトリは PJ 候補にしない。"""
        (tmp_path / ".worktrees" / ".claude").mkdir(parents=True)
        (tmp_path / "pj" / "CLAUDE.md").parent.mkdir()
        (tmp_path / "pj" / "CLAUDE.md").write_text("")
        result = enumerate_projects(tmp_path)
        assert [p.name for p in result] == ["pj"]


class TestClassifyProject:
    """classify_project() の 3 値判定 + settings parse retry テスト。"""

    @staticmethod
    def _make_pj(tmp_path: Path, name: str) -> Path:
        pj = tmp_path / "repos" / name
        (pj / ".claude").mkdir(parents=True)
        return pj

    @staticmethod
    def _make_auto_memory(auto_memory_root: Path, pj: Path, age_days: float) -> Path:
        slug = str(pj.resolve()).replace("/", "-")
        d = auto_memory_root / slug
        d.mkdir(parents=True)
        f = d / "session.jsonl"
        f.write_text("{}\n")
        t = time.time() - age_days * 86400
        os.utime(f, (t, t))
        return d

    @staticmethod
    def _write_settings(path: Path, enabled: bool | None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if enabled is None:
            data: dict = {"enabledPlugins": {}}
        else:
            data = {"enabledPlugins": {"rl-anything@rl-anything": enabled}}
        path.write_text(json.dumps(data))

    def test_ENABLED_最近の活動あり(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._write_settings(settings, True)
        self._make_auto_memory(auto_memory, pj, age_days=1)
        assert classify_project(pj, settings, auto_memory) == STATUS_ENABLED

    def test_STALE_auto_memory_古い(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._write_settings(settings, True)
        self._make_auto_memory(auto_memory, pj, age_days=40)
        assert classify_project(pj, settings, auto_memory) == STATUS_STALE

    def test_STALE_auto_memory_欠損(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._write_settings(settings, True)
        # auto_memory/<slug> を作らない
        assert classify_project(pj, settings, auto_memory) == STATUS_STALE

    def test_NOT_ENABLED_plugin_disabled(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._write_settings(settings, False)
        self._make_auto_memory(auto_memory, pj, age_days=1)  # 活動あっても無視
        assert classify_project(pj, settings, auto_memory) == STATUS_NOT_ENABLED

    def test_NOT_ENABLED_settings_欠損(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "does_not_exist.json"
        auto_memory = tmp_path / "projects"
        assert classify_project(pj, settings, auto_memory) == STATUS_NOT_ENABLED

    def test_settings_parse_失敗_retry_成功(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._make_auto_memory(auto_memory, pj, age_days=1)

        # 1 回目: 破損。2 回目: 正常。
        settings.write_text("{ broken")
        call_count = {"n": 0}
        original_read_text = Path.read_text

        def flaky_read_text(self, *args, **kwargs):
            if self == settings:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return "{ broken"
                return json.dumps({"enabledPlugins": {"rl-anything@rl-anything": True}})
            return original_read_text(self, *args, **kwargs)

        with mock.patch.object(Path, "read_text", flaky_read_text):
            result = classify_project(pj, settings, auto_memory)
        assert result == STATUS_ENABLED
        assert call_count["n"] == 2

    def test_settings_parse_失敗_retry_も失敗(self, tmp_path):
        pj = self._make_pj(tmp_path, "pj1")
        settings = tmp_path / "settings.json"
        auto_memory = tmp_path / "projects"
        self._make_auto_memory(auto_memory, pj, age_days=1)
        settings.write_text("{ broken")
        assert classify_project(pj, settings, auto_memory) == STATUS_NOT_ENABLED


class TestRunAuditSubprocess:
    """run_audit_subprocess() の正常系 + TIMEOUT + ERROR テスト。"""

    @staticmethod
    def _make_pj(tmp_path: Path) -> Path:
        pj = tmp_path / "pj1"
        pj.mkdir()
        return pj

    @staticmethod
    def _write_growth_state(data_dir: Path, pj: Path, *, progress: float, phase: str) -> Path:
        data_dir.mkdir(parents=True, exist_ok=True)
        state_path = data_dir / f"growth-state-{pj.name}.json"
        state_path.write_text(json.dumps({
            "progress": progress,
            "phase": phase,
            "updated_at": "2026-04-22T00:00:00+00:00",
            "sessions_count": 10,
            "crystallizations_count": 0,
        }))
        return state_path

    def test_正常系_growth_state_から読み取り(self, tmp_path):
        pj = self._make_pj(tmp_path)
        data_dir = tmp_path / "data"
        self._write_growth_state(data_dir, pj, progress=0.65, phase="continuous_growth")

        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=fake_proc) as m:
            result = run_audit_subprocess(pj, data_dir=data_dir)

        assert result.status == AUDIT_OK
        assert result.env_score == 0.65
        assert result.phase == "continuous_growth"
        assert result.growth_level == 7  # 0.65 → Lv.7 (LEVEL_THRESHOLDS)
        assert result.latest_audit == datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc)
        # subprocess に CLAUDE_PLUGIN_DATA env が渡されたことを確認
        _, kwargs = m.call_args
        assert kwargs["env"]["CLAUDE_PLUGIN_DATA"] == str(data_dir)

    def test_growth_state_欠損時は_OK_だがスコア_None(self, tmp_path):
        pj = self._make_pj(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()  # ディレクトリはあるがファイルなし
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=fake_proc):
            result = run_audit_subprocess(pj, data_dir=data_dir)
        assert result.status == AUDIT_OK
        assert result.env_score is None
        assert result.phase is None
        assert result.growth_level is None
        assert "no growth-state" in result.message

    def test_TIMEOUT(self, tmp_path):
        pj = self._make_pj(tmp_path)
        data_dir = tmp_path / "data"
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="rl-audit", timeout=10),
        ):
            result = run_audit_subprocess(pj, timeout=10, data_dir=data_dir)
        assert result.status == AUDIT_TIMEOUT
        assert "timeout" in result.message.lower()

    def test_ERROR_returncode非ゼロ(self, tmp_path):
        pj = self._make_pj(tmp_path)
        data_dir = tmp_path / "data"
        fake_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Traceback (most recent call last)\nKeyError: 'foo'"
        )
        with mock.patch("subprocess.run", return_value=fake_proc):
            result = run_audit_subprocess(pj, data_dir=data_dir)
        assert result.status == AUDIT_ERROR
        assert "KeyError" in result.message

    def test_ERROR_growth_state_破損(self, tmp_path):
        pj = self._make_pj(tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / f"growth-state-{pj.name}.json").write_text("{ corrupted")
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", return_value=fake_proc):
            result = run_audit_subprocess(pj, data_dir=data_dir)
        assert result.status == AUDIT_ERROR
        assert "state parse" in result.message


class TestFormatStatusTable:
    """format_status_table() の表示整形テスト。"""

    def _now(self) -> datetime:
        return datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)

    def test_ENABLEDと_STALEと_NOT_ENABLEDが正しく区別される(self):
        rows = [
            FleetRow(
                pj_name="rl-anything",
                status=STATUS_ENABLED,
                env_score=0.65,
                growth_level=7,
                phase="continuous_growth",
                latest_audit=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
                audit_status=AUDIT_OK,
            ),
            FleetRow(pj_name="bots", status=STATUS_STALE, audit_status=AUDIT_OK),
            FleetRow(pj_name="ope-browser", status=STATUS_NOT_ENABLED),
        ]
        out = format_status_table(rows, now=self._now())
        lines = out.strip().split("\n")
        assert lines[0].startswith("PJ")
        # ENABLED 行: score/level/phase が表示される
        assert "0.65" in lines[1]
        assert "Lv.7" in lines[1]
        assert "continuous_growth" in lines[1]
        assert "2h ago" in lines[1]
        # STALE 行: score=N/A, 他は —
        assert "N/A" in lines[2]
        assert "—" in lines[2]
        # NOT_ENABLED 行: audit も —
        parts = lines[3].split()
        assert parts[0] == "ope-browser"
        assert parts[1] == "NOT_ENABLED"

    def test_TIMEOUT_と_ERROR行(self):
        rows = [
            FleetRow(pj_name="a", status=STATUS_ENABLED, audit_status=AUDIT_TIMEOUT),
            FleetRow(pj_name="b", status=STATUS_ENABLED, audit_status=AUDIT_ERROR, message="boom"),
        ]
        out = format_status_table(rows, now=self._now())
        assert "TIMEOUT" in out
        assert "ERROR" in out

    def test_列幅は最長セルに揃う(self):
        rows = [
            FleetRow(pj_name="short", status=STATUS_STALE),
            FleetRow(pj_name="very-long-project-name", status=STATUS_STALE),
        ]
        out = format_status_table(rows, now=self._now())
        lines = out.strip().split("\n")
        # ヘッダ行の "STATUS" と同じ offset に各行の STALE 列が来る
        status_offset = lines[0].index("STATUS")
        for data_line in lines[1:]:
            assert data_line[status_offset:status_offset + len("STALE")] == "STALE"

    def test_相対時刻_分_時間_日(self):
        now = self._now()
        rows = [
            FleetRow(pj_name="min", status=STATUS_ENABLED, env_score=0.5,
                     latest_audit=now - timedelta(minutes=5), audit_status=AUDIT_OK),
            FleetRow(pj_name="hour", status=STATUS_ENABLED, env_score=0.5,
                     latest_audit=now - timedelta(hours=3), audit_status=AUDIT_OK),
            FleetRow(pj_name="day", status=STATUS_ENABLED, env_score=0.5,
                     latest_audit=now - timedelta(days=2), audit_status=AUDIT_OK),
        ]
        out = format_status_table(rows, now=now)
        assert "5m ago" in out
        assert "3h ago" in out
        assert "2d ago" in out

    def test_空リストでもヘッダだけ出る(self):
        out = format_status_table([], now=self._now())
        lines = out.strip().split("\n")
        assert len(lines) == 1
        assert "PJ" in lines[0] and "STATUS" in lines[0]
