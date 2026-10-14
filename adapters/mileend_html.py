import datetime
import hashlib
import re

from bs4 import BeautifulSoup

from .common import bank_holidays, http_get, to_hhmm

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_offer(text):
    """'Super off-peak (weekdays before 9:30am) £5 - £6 (including donation)'
    -> ({0..4}, "09:30", 5.0, None)  # £6 only adds the donation"""
    lower = text.lower()
    if "weekdays" in lower:
        days = {0, 1, 2, 3, 4}
    else:
        days = {i for i, name in enumerate(WEEKDAYS) if name in lower}
    if not days:
        raise ValueError(f"no days found in Mile End offer: {text!r}")
    end = re.search(r"before (\d{1,2}(?::\d{2})?\s*[ap]m)", text, re.I)
    if not end:
        raise ValueError(f"no 'before <time>' found in Mile End offer: {text!r}")
    price_range = re.search(r"£(\d+(?:\.\d+)?)\s*-\s*£(\d+(?:\.\d+)?)", text)
    single = re.search(r"£(\d+(?:\.\d+)?)", text)
    if price_range:
        low, high = sorted(float(p) for p in price_range.groups())
        # "£5 - £6 (including donation)": the top of the range is just the optional donation.
        if "donation" in lower:
            high = None
    elif single:
        low, high = float(single.group(1)), None
    else:
        low = high = None
    return days, to_hhmm(end.group(1)), low, high


def fetch(chain_cfg, session, state, start_date, days):
    r = http_get(session, chain_cfg["url"])
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    strong = soup.find("strong", string=lambda t: t and t.strip().startswith("Super off-peak"))
    if strong is None:
        raise ValueError("'Super off-peak' <strong> not found on Mile End first-visit page")
    text = strong.parent.get_text(" ", strip=True)

    # No modified date on this page, so detect changes by hashing the offer text.
    digest = hashlib.sha256(text.encode()).hexdigest()
    if state.get("sha256") and state["sha256"] != digest:
        print(f"Mile End offer changed: {text}")
    state.update(sha256=digest, text=text)

    weekdays, end, price, price_max = parse_offer(text)
    holidays = bank_holidays(session, state)
    sessions = []
    for i in range(days):
        day = start_date + datetime.timedelta(days=i)
        if day.weekday() not in weekdays or day.isoformat() in holidays:
            continue
        sessions.append({
            "chain": chain_cfg["name"], "centre": chain_cfg["centre"], "date": day.isoformat(),
            "start": to_hhmm(chain_cfg["open_time"]) if chain_cfg.get("open_time") else None, "end": end,
            "price": price, "price_max": price_max, "label": "Super off-peak",
            "bookable": False, "avail": None, "full": False,
            "type": chain_cfg["type"], "link": chain_cfg["url"],
        })
    return sessions
