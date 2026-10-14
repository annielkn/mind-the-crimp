"""Every file path the project uses, defined once."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(ROOT, "config")  # committed, hand-edited or collected
DATA_DIR = os.path.join(ROOT, "data")  # runtime caches, gitignored

CHAINS = os.path.join(CONFIG_DIR, "chains.json")
CHAINS_PRIVATE = os.path.join(CONFIG_DIR, "chains.private.json")  # gitignored; deep-merged over CHAINS
CENTRES = os.path.join(CONFIG_DIR, "centres.json")
OVERRIDES = os.path.join(CONFIG_DIR, "overrides.json")
STATE = os.path.join(DATA_DIR, "state.json")
ROBOTS_CACHE = os.path.join(DATA_DIR, "robots.json")  # per-host Crawl-delay from robots.txt
SESSIONS = os.path.join(DATA_DIR, "sessions.json")  # last good refresh
SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")  # newest few good refreshes
# Committed (not gitignored): public sessions only, so a fresh clone runs offline with no network.
PUBLIC_SNAPSHOT = os.path.join(DATA_DIR, "public", "sessions.json")
LEGACY_SNAPSHOT_DIR = os.path.join(ROOT, "data_snapshot")  # imported once if snapshots/ is empty
WEB_DIST = os.path.join(ROOT, "web", "dist")


# OFFLINE=1 (the default for now): no network at all; everything reads the newest snapshot.
OFFLINE = os.environ.get("OFFLINE", "1") == "1"


def ensure_data_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
