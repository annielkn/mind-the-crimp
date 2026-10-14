import datetime
import json
import re
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import paths

# Honest User-Agent: says who we are and where to find the project (and its politeness rules).
HEADERS = {"User-Agent": "MindTheCrimp/1.0 (+https://github.com/annielkn/mind-the-crimp)"}
BANK_HOLIDAYS_URL = "https://www.gov.uk/bank-holidays.json"
BANK_HOLIDAYS_MAX_AGE = 7 * 24 * 3600

DEFAULT_HOST_GAP = 1.0  # seconds between requests to the same host when robots.txt sets nothing
ROBOTS_MAX_AGE = 7 * 24 * 3600

_last_by_host = {}  # host -> monotonic time of the last request to it
_crawl_delay = {}  # host -> Crawl-delay seconds from robots.txt (None if unset), cached per process
# hostname -> (before(), after(response)): optional per-host hooks, e.g. a request budget
# registered by a private adapter. Keeps this module free of any site-specific rules.
_host_guards = {}


class OfflineError(RuntimeError):
    pass


def register_host_guard(host, before=None, after=None):
    _host_guards[host] = (before, after)


def load_state():
    try:
        with open(paths.STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    paths.ensure_data_dir()
    with open(paths.STATE, "w") as f:
        json.dump(state, f, indent=1)


def _wait_for(host):
    """Sleep until this host's gap (max of DEFAULT_HOST_GAP and its Crawl-delay) has passed."""
    gap = max(DEFAULT_HOST_GAP, _crawl_delay.get(host) or 0)
    last = _last_by_host.get(host)
    if last is not None:
        wait = last + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
    _last_by_host[host] = time.monotonic()


def _load_crawl_delay(session, host):
    """Crawl-delay for host from robots.txt: disk cache (7 days), else one fetch. Never raises."""
    if host in _crawl_delay:
        return
    try:
        with open(paths.ROBOTS_CACHE) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    entry = cache.get(host)
    if entry and time.time() - entry["fetched_ts"] < ROBOTS_MAX_AGE:
        _crawl_delay[host] = entry["crawl_delay"]
        return
    text = ""
    try:
        _wait_for(host)
        r = session.request("GET", f"https://{host}/robots.txt", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            text = r.text
    except Exception:
        pass  # no robots.txt (or unreachable): fall back to DEFAULT_HOST_GAP
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    delay = rp.crawl_delay(HEADERS["User-Agent"])
    _crawl_delay[host] = float(delay) if delay else None
    cache[host] = {"crawl_delay": _crawl_delay[host], "fetched_ts": time.time()}
    try:
        paths.ensure_data_dir()
        with open(paths.ROBOTS_CACHE, "w") as f:
            json.dump(cache, f, indent=1)
    except OSError:
        pass


def throttle(session, host):
    """Per-host politeness: respect robots.txt Crawl-delay, else DEFAULT_HOST_GAP."""
    _load_crawl_delay(session, host)
    _wait_for(host)


# All "today"/"now" logic is Europe/London, never the machine's clock zone (GitHub Actions runs in UTC).
LONDON = ZoneInfo("Europe/London")


def london_now():
    return datetime.datetime.now(LONDON)


def london_date():
    return london_now().date()


def london_today():
    return london_date().isoformat()


def parse_ts(text):
    """ISO timestamp -> aware datetime; a timestamp without an offset is taken as London time."""
    ts = datetime.datetime.fromisoformat(text)
    return ts if ts.tzinfo else ts.replace(tzinfo=LONDON)


def _request(method, session, url, **kwargs):
    """The only place the project touches the network."""
    if paths.OFFLINE:
        raise OfflineError(f"OFFLINE=1: refusing {method} {url}")
    host = urlparse(url).hostname
    before, after = _host_guards.get(host, (None, None))
    if before:
        before()
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 20)
    throttle(session, host)
    r = session.request(method, url, **kwargs)
    if after:
        after(r)
    return r


def http_get(session, url, **kwargs):
    return _request("GET", session, url, **kwargs)


def http_post(session, url, **kwargs):
    return _request("POST", session, url, **kwargs)


def to_hhmm(text):
    """'4 PM', '4:30 PM', '9am', '11pm' -> 'HH:MM'."""
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*", text, re.I)
    if not m:
        raise ValueError(f"unrecognised time: {text!r}")
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{hour:02d}:{m.group(2) or '00'}"


def bank_holidays(session, state):
    cached = state.get("bank_holidays")
    if cached and time.time() - cached["fetched_ts"] < BANK_HOLIDAYS_MAX_AGE:
        return set(cached["dates"])
    r = http_get(session, BANK_HOLIDAYS_URL)
    r.raise_for_status()
    dates = [e["date"] for e in r.json()["england-and-wales"]["events"]]
    state["bank_holidays"] = {"fetched_ts": time.time(), "dates": dates}
    return set(dates)
