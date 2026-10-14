"""Dates are Europe/London, not the machine's zone (GitHub Actions runs in UTC)."""
import datetime

from adapters import common

UTC = datetime.timezone.utc


class FrozenClock(datetime.datetime):
    instant = None

    @classmethod
    def now(cls, tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


def freeze(monkeypatch, instant):
    FrozenClock.instant = instant
    monkeypatch.setattr(common.datetime, "datetime", FrozenClock)


def test_london_date_after_utc_midnight_during_bst(monkeypatch):
    # 23:30 UTC on 14 Oct 2026 is 00:30 BST on 15 Oct: "today" in London is the 15th.
    freeze(monkeypatch, datetime.datetime(2026, 10, 14, 23, 30, tzinfo=UTC))
    assert common.london_today() == "2026-10-15"
    assert common.london_now().utcoffset() == datetime.timedelta(hours=1)


def test_london_date_in_winter_matches_utc(monkeypatch):
    # GMT in December: London and UTC agree.
    freeze(monkeypatch, datetime.datetime(2026, 12, 14, 23, 30, tzinfo=UTC))
    assert common.london_today() == "2026-12-14"


def test_parse_ts_treats_offsetless_timestamps_as_london():
    old = common.parse_ts("2026-10-14T22:42:09")  # written before refreshed_at carried an offset
    new = common.parse_ts("2026-10-14T22:42:09+01:00")
    assert old == new and old.tzinfo is not None
