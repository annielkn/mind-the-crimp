import datetime

from bs4 import BeautifulSoup

from .common import bank_holidays, http_get, to_hhmm


def parse_table(html):
    """Magic Time table -> [[centre, weekday, "HH:MM", "HH:MM"], ...]."""
    heading = BeautifulSoup(html, "html.parser").find(id="price-super")
    table = heading.find_next("table") if heading else None
    if table is None:
        raise ValueError("Magic Time table not found (no #price-super followed by a <table>)")
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) != 4:
            raise ValueError(f"expected 4 columns in Magic Time table, got {len(cells)}: {cells}")
        centre, weekday, start, end = cells
        rows.append([centre, weekday, to_hhmm(start), to_hhmm(end)])
    if not rows:
        raise ValueError("Magic Time table is empty")
    return rows


def fetch(chain_cfg, session, state, start_date, days):
    r = http_get(session, chain_cfg["url"])
    r.raise_for_status()
    page = r.json()
    modified = page["modified_gmt"]
    if state.get("modified_gmt") == modified and state.get("table"):
        table = state["table"]
    else:
        if state.get("modified_gmt"):
            print(f"LCC schedule changed (was {state['modified_gmt']}, now {modified})")
        table = parse_table(page["content"]["rendered"])
        state.update(modified_gmt=modified, table=table)

    # Magic Time doesn't run on bank holidays.
    holidays = bank_holidays(session, state)
    sessions = []
    for i in range(days):
        day = start_date + datetime.timedelta(days=i)
        if day.isoformat() in holidays:
            continue
        for centre, weekday, start, end in table:
            if weekday.lower() == day.strftime("%A").lower():
                sessions.append({
                    "chain": chain_cfg["name"], "centre": centre, "date": day.isoformat(),
                    "start": start, "end": end, "price": chain_cfg.get("price"), "label": "Magic Time",
                    "bookable": False, "avail": None, "full": False,
                    "type": chain_cfg["type"], "link": page.get("link"),
                })
    return sessions
