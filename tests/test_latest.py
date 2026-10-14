"""Offline data source order in main.latest(): local sessions.json > newest local snapshot >
committed public snapshot. Order wins over age: the committed file is only a fresh-clone fallback."""
import json

import pytest

import main
import paths


def write(path, refreshed_at):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"refreshed_at": refreshed_at, "start": "2026-10-14", "days": 28,
                                "sessions": [], "errors": []}))


@pytest.fixture
def data(monkeypatch, tmp_path):
    p = {
        "sessions": tmp_path / "sessions.json",
        "snapshots": tmp_path / "snapshots",
        "public": tmp_path / "public" / "sessions.json",
    }
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "SESSIONS", str(p["sessions"]))
    monkeypatch.setattr(paths, "SNAPSHOT_DIR", str(p["snapshots"]))
    monkeypatch.setattr(paths, "PUBLIC_SNAPSHOT", str(p["public"]))
    # The committed snapshot is always the newest, to prove order beats age.
    write(p["public"], "2026-10-14T23:59:00")
    return p


def test_local_sessions_beat_newer_committed_snapshot(data):
    write(data["sessions"], "2026-10-14T08:00:00")
    assert main.latest()["refreshed_at"] == "2026-10-14T08:00:00"


def test_local_snapshot_beats_newer_committed_snapshot(data):
    write(data["snapshots"] / "2026-10-14T09-00.json", "2026-10-14T09:00:00")
    assert main.latest()["refreshed_at"] == "2026-10-14T09:00:00"


def test_committed_snapshot_only_when_nothing_local(data):
    assert main.latest()["refreshed_at"] == "2026-10-14T23:59:00"
