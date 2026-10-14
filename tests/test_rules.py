"""Weekly rules (adapters/manual.py) -> dated sessions."""
import datetime
from zoneinfo import ZoneInfo

from adapters import manual

LONDON = ZoneInfo("Europe/London")

CHAIN = {
    "name": "Test Chain",
    "type": "bookable",
    "rules": [
        {"centre": "A", "day": "Mon", "start": "08:00", "end": "10:00", "price": 7.5, "label": "Off-peak"},
        {"centre": "B", "day": "Sun", "start": "16:30", "end": "17:30", "price": 7.5, "label": "Off-peak"},
    ],
}


def test_rule_expansion_for_a_fixed_week():
    # Mon 19 Oct 2026 .. Sun 25 Oct 2026
    sessions = manual.fetch(CHAIN, None, {}, datetime.date(2026, 10, 19), 7)
    assert [(s["centre"], s["date"], s["start"], s["end"]) for s in sessions] == [
        ("A", "2026-10-19", "08:00", "10:00"),
        ("B", "2026-10-25", "16:30", "17:30"),
    ]
    assert all(s["chain"] == "Test Chain" and s["price"] == 7.5 and s["label"] == "Off-peak" for s in sessions)


def test_rule_on_dst_change_day_keeps_local_wall_clock_times():
    # UK clocks go back at 02:00 BST on Sun 25 Oct 2026 (BST -> GMT).
    sessions = manual.fetch(CHAIN, None, {}, datetime.date(2026, 10, 24), 3)
    sun = [s for s in sessions if s["date"] == "2026-10-25"]
    assert len(sun) == 1
    start = datetime.datetime.fromisoformat(f"{sun[0]['date']}T{sun[0]['start']}").replace(tzinfo=LONDON)
    end = datetime.datetime.fromisoformat(f"{sun[0]['date']}T{sun[0]['end']}").replace(tzinfo=LONDON)
    # 16:30 local is after the change, so it's GMT (UTC+0), and the session is still one hour long.
    assert (start.hour, start.minute) == (16, 30)
    assert start.utcoffset() == datetime.timedelta(0)
    assert end - start == datetime.timedelta(hours=1)
    # Exactly one session per rule day across the change (no duplicated or skipped day).
    assert [s["date"] for s in sessions] == ["2026-10-25", "2026-10-26"]
