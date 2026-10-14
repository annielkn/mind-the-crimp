"""The pipeline must work without adapters/private/ (as in the public repo).

Runs in a subprocess so hiding the private package can't leak into other tests. Nothing is deleted:
sys.modules["adapters.private"] = None makes that import fail, and all data paths point at a temp dir.
"""
import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent("""
    import datetime, json, os, sys, tempfile
    sys.modules["adapters.private"] = None          # simulate: private package absent
    import paths
    tmp = tempfile.mkdtemp()
    paths.CHAINS_PRIVATE = os.path.join(tmp, "none.json")   # ...and no private config
    paths.DATA_DIR = tmp
    paths.STATE = os.path.join(tmp, "state.json")
    paths.SESSIONS = os.path.join(tmp, "sessions.json")
    paths.SNAPSHOT_DIR = os.path.join(tmp, "snapshots")
    paths.LEGACY_SNAPSHOT_DIR = os.path.join(tmp, "legacy")
    import adapters, main, server
    assert adapters.PRIVATE == [], adapters.PRIVATE
    assert set(adapters.ADAPTERS) == set(adapters.PUBLIC_ADAPTERS), adapters.ADAPTERS
    # Offline: the CLI and the API serve the committed public snapshot.
    main.main()
    api = server.sessions()
    assert api["mode"] == "offline" and api["sessions"], api.keys()
    # Live pipeline with network refused: hand-entered chains still produce sessions.
    sessions, errors = main.collect(datetime.date(2026, 10, 19), 7)
    assert any(s["chain"] == "City Bouldering" for s in sessions), "manual rules produced nothing"
    assert all("OFFLINE=1" in e for e in errors), errors
    print("PRIVATE_OPTIONAL_OK", len(api["sessions"]), len(sessions))
""")


def test_pipeline_runs_without_private_adapters():
    env = {**os.environ, "OFFLINE": "1"}
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "PRIVATE_OPTIONAL_OK" in r.stdout
