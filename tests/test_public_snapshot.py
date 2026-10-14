"""The committed public snapshot (data/public/sessions.json)."""
import json
import re

import paths

SNAPSHOT = json.load(open(paths.PUBLIC_SNAPSHOT))
# The spec's names map to this codebase: gym -> "centre", day/date -> "date".
REQUIRED = ["centre", "chain", "date", "start", "end", "price", "label"]
LEAK = re.compile(r"spaces|available|availability|capacity|^avail$|^full$|^bookable$")


def test_schema():
    assert SNAPSHOT["sessions"], "snapshot is empty"
    for s in SNAPSHOT["sessions"]:
        missing = [k for k in REQUIRED if s.get(k) in (None, "")]
        assert not missing, f"{s} is missing {missing}"
        assert isinstance(s["price"], (int, float)) and not isinstance(s["price"], bool), s
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"]), s
        assert re.fullmatch(r"\d{2}:\d{2}", s["start"]) and re.fullmatch(r"\d{2}:\d{2}", s["end"]), s
        assert s["end"] > s["start"], s


def test_no_availability_leak():
    def keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from keys(v)

    leaked = sorted({k for k in keys(SNAPSHOT) if LEAK.search(k)})
    assert not leaked, f"public snapshot has private-looking keys: {leaked}"
