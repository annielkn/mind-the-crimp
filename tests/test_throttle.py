"""Per-host throttling in adapters/common.py, on a fake clock with a fake session (no network)."""
import pytest

import paths
from adapters import common


class Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class FakeSession:
    def __init__(self, clock, robots):
        self.clock, self.robots, self.calls = clock, robots, []

    def request(self, method, url, **kwargs):
        self.calls.append((self.clock["now"], url))
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            return Resp(200, self.robots[host]) if host in self.robots else Resp(404)
        return Resp(200, "ok")


@pytest.fixture
def env(monkeypatch, tmp_path):
    clock = {"now": 1000.0}
    monkeypatch.setattr(common.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(common.time, "sleep", lambda s: clock.__setitem__("now", clock["now"] + s))
    monkeypatch.setattr(paths, "OFFLINE", False)
    monkeypatch.setattr(paths, "ROBOTS_CACHE", str(tmp_path / "robots.json"))
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setattr(common, "_last_by_host", {})
    monkeypatch.setattr(common, "_crawl_delay", {})
    robots = {"slow.example": "User-agent: *\nCrawl-delay: 10\n", "plain.example": "User-agent: *\nDisallow: /private/\n"}
    return clock, FakeSession(clock, robots)


def page_times(session, host):
    return [t for t, url in session.calls if host in url and not url.endswith("/robots.txt")]


def test_same_host_respects_crawl_delay(env):
    clock, s = env
    common.http_get(s, "https://slow.example/a")
    common.http_get(s, "https://slow.example/b")
    t1, t2 = page_times(s, "slow.example")
    assert t2 - t1 >= 10
    assert sum(url.endswith("/robots.txt") for _, url in s.calls) == 1  # robots.txt fetched once


def test_same_host_default_gap_without_crawl_delay(env):
    clock, s = env
    for host in ("plain.example", "missing.example"):  # robots.txt without Crawl-delay, and a 404
        common.http_get(s, f"https://{host}/a")
        common.http_get(s, f"https://{host}/b")
        t1, t2 = page_times(s, host)
        assert t2 - t1 >= common.DEFAULT_HOST_GAP
        assert t2 - t1 < 10


def test_different_hosts_do_not_wait_for_each_other(env):
    clock, s = env
    common.http_get(s, "https://slow.example/a")
    before = clock["now"]
    common.http_get(s, "https://plain.example/a")  # only its own robots.txt + gap, not slow.example's 10s
    assert clock["now"] - before < 10
