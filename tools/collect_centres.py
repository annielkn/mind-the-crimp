"""One-off: collect address + weekly opening hours for every centre into centres.json.

Only writes config/centres.json. Manual values belong in config/overrides.json, which this never touches.

Run from the repo root: python3 -m tools.collect_centres
Not part of the normal run. Anything not parsed confidently is written as null and reported.
"""
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

import paths
from adapters.common import http_get, http_post
from adapters.lcc_wordpress import parse_table

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
POSTCODE = r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b"
HOURS_LINE = re.compile(r"^(?P<days>[A-Za-z&,\s-]+?)[:\s]+(?P<open>\d{1,2}:\d{2})\s*-\s*(?P<close>\d{1,2}:\d{2})$")

LCC_STORE_SEARCH = "https://londonclimbingcentres.co.uk/wp/wp-admin/admin-ajax.php"
CB_LOCATIONS = "https://www.citybouldering.co.uk/locations/city-bouldering-stratford"  # footer lists all locations
POSTCODES_BULK = "https://api.postcodes.io/postcodes"

# Human area names, read off each address. UNSURE ones are reported for checking.
AREAS = {
    "White City": "White City", "Aldgate": "Aldgate", "Stratford": "Stratford", "Fulham": "Fulham",
    "VauxWall East": "Vauxhall", "VauxWall West": "Vauxhall", "EustonWall": "Euston",
    "BethWall Green": "Bethnal Green", "CanaryWall": "Canary Wharf", "RavensWall": "Hammersmith",
    "CroyWall": "Croydon", "HarroWall": "Harrow", "Mile End": "Mile End",
}
UNSURE_AREAS = {
    "White City": "address says Shepherd's Bush",
    "Fulham": "address is Parsons Green (in Fulham)",
    "CanaryWall": "address says Poplar (E14), named after Canary Wharf",
    "RavensWall": "Ravenscourt Road W6; could be 'Ravenscourt Park'",
}


session = requests.Session()
report = []


def get(url, **params):
    r = http_get(session, url, params=params or None)
    r.raise_for_status()
    return r


def norm(name):
    return re.sub(r"[^a-z]", "", name.lower())


def day_index(word):
    for i, d in enumerate(DAYS):
        if word.strip().lower().startswith(d.lower()):
            return i
    raise ValueError(f"unknown day {word!r}")


def parse_days(spec):
    """'Monday - Friday', 'Sat & Sun', 'Monday and Friday', 'Tuesday- Thursday', 'Sat-Sun', 'Mon'."""
    out = []
    for part in re.split(r"\s*(?:&|,|\band\b)\s*", spec.strip()):
        if "-" in part:
            a, b = part.split("-", 1)
            out += range(day_index(a), day_index(b) + 1)
        else:
            out.append(day_index(part))
    return out


def parse_hours(lines):
    """Hour lines -> {"Mon": [open, close], ...}; raises unless all 7 days are covered."""
    hours = {}
    for line in lines:
        m = HOURS_LINE.match(line)
        for i in parse_days(m["days"]):
            hours[DAYS[i]] = [m["open"].zfill(5), m["close"].zfill(5)]
    missing = [d for d in DAYS if d not in hours]
    if missing:
        raise ValueError(f"no hours for {missing}")
    return {d: hours[d] for d in DAYS}


def split_postcode(text):
    m = re.search(POSTCODE, text)
    if not m:
        return text.strip(" ,"), None
    return (text[:m.start()] + text[m.end():]).strip(" ,"), m.group()


def match_centre(name, centres):
    """Site name -> adapter centre name; exact first, then normalised prefix ('BethWall' -> 'BethWall Green')."""
    for c in centres:
        if norm(c) == norm(name):
            return c
    hits = [c for c in centres if norm(c).startswith(norm(name)) or norm(name).endswith(norm(c))]
    return hits[0] if len(hits) == 1 else None


def entry(chain, address, postcode, hours, source_url, site_name, centre, hours_source=None):
    # verified: ISO date a human last checked this entry against the site; null until then.
    e = {"chain": chain, "area": AREAS.get(centre), "address": address, "postcode": postcode,
         "lat": None, "lng": None, "hours": hours,
         "hours_source": hours_source if hours else None, "source_url": source_url, "verified": None}
    if centre not in AREAS:
        report.append(f"{centre}: area null (not in AREAS)")
    if site_name != centre:
        e["aliases"] = [site_name]
    return e


def collect_lcc(names):
    out = {}
    # The centre post type has no structured fields; the store locator's search endpoint does.
    stores = get(LCC_STORE_SEARCH, action="store_search", lat=51.5074, lng=-0.1278,
                 max_results=25, search_radius=100, autoload=1).json()
    for store in stores:
        centre = match_centre(store["store"], names)
        if not centre:
            report.append(f"LCC store {store['store']!r} has no matching Magic Time centre; skipped")
            continue
        address = ", ".join(p for p in [store["address"], store["address2"], store["city"]] if p.strip())
        hours = None
        report.append(f"{centre}: hours null (LCC store data has empty hours and the centre page HTML has none)")
        out[centre] = entry("lcc", address, store["zip"] or None, hours, store["url"], store["store"], centre)
    return out


def collect_city_bouldering(names):
    out = {}
    lines = BeautifulSoup(get(CB_LOCATIONS).text, "html.parser").get_text("\n", strip=True).split("\n")
    # Footer blocks: "<City Bouldering|Climbing Co> X" followed by an address line with a postcode.
    titles = [i for i, l in enumerate(lines[:-1])
              if re.match(r"^(City Bouldering|Climbing Co) \w", l) and re.search(POSTCODE, lines[i + 1])]
    for n, start in enumerate(titles):
        end = titles[n + 1] if n + 1 < len(titles) else next(
            (i for i in range(start, len(lines)) if lines[i].startswith("©")), len(lines))
        block = lines[start:end]
        site_name = block[0]
        centre = next((c for c in names if site_name.endswith(c)), None)
        if not centre:
            report.append(f"City Bouldering location {site_name!r} has no configured offering; skipped")
            continue
        address, postcode = split_postcode(block[1])
        try:
            hours = parse_hours([l for l in block if HOURS_LINE.match(l)])
        except (ValueError, TypeError) as e:
            hours = None
            report.append(f"{centre}: hours null ({e})")
        if not postcode:
            report.append(f"{centre}: postcode null")
        out[centre] = entry("city-bouldering", address, postcode, hours, CB_LOCATIONS, centre, centre,
                            hours_source=f"{CB_LOCATIONS} (footer)")
    for c in names:
        if c not in out:
            report.append(f"{c}: not found in City Bouldering locations footer")
    return out


def collect_mile_end(centre):
    url = "https://www.mileendwall.org.uk/index.php/contact-us"
    lines = BeautifulSoup(get(url).text, "html.parser").get_text("\n", strip=True).split("\n")
    address = postcode = None
    if "Address:" in lines:
        i = lines.index("Address:") + 1
        j = next((k for k in range(i, len(lines)) if lines[k].endswith(":")), len(lines))
        address, postcode = split_postcode(", ".join(lines[i:j]))
    else:
        report.append(f"{centre}: address null ('Address:' block not found)")
    report.append(f"{centre}: hours null (no opening times on contact-us, first-visit, memberships or home page)")
    return {centre: entry("mile-end", address, postcode, None, url, centre, centre)}


def geocode(centres):
    """lat/lng for every postcode in one bulk postcodes.io request."""
    postcodes = sorted({c["postcode"] for c in centres.values() if c["postcode"]})
    r = http_post(session, POSTCODES_BULK, json={"postcodes": postcodes})
    r.raise_for_status()
    found = {x["query"]: x["result"] for x in r.json()["result"]}
    for name, c in centres.items():
        result = found.get(c["postcode"])
        if result:
            c["lat"], c["lng"] = result["latitude"], result["longitude"]
        else:
            report.append(f"{name}: lat/lng null (postcode {c['postcode']!r} not found on postcodes.io)")


def main():
    if paths.OFFLINE:
        raise SystemExit("OFFLINE=1 (the default): the collector needs live requests. Run with OFFLINE=0.")
    from main import load_chains
    chains = load_chains()
    lcc_page = get(chains["lcc"]["url"]).json()
    lcc_names = sorted({row[0] for row in parse_table(lcc_page["content"]["rendered"])})
    cb = chains["city-bouldering"]
    cb_names = sorted({o["centre"] for o in cb.get("offerings", []) + cb.get("rules", [])})

    centres = {}
    centres.update(collect_city_bouldering(cb_names))
    centres.update(collect_lcc(lcc_names))
    centres.update(collect_mile_end(chains["mile-end"]["centre"]))
    for name in lcc_names:
        if name not in centres:
            report.append(f"{name}: no LCC store data found")
    geocode(centres)
    for name, why in UNSURE_AREAS.items():
        report.append(f"{name}: area {AREAS[name]!r} is a judgement call ({why})")

    with open(paths.CENTRES, "w") as f:
        json.dump(centres, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"{'Centre':<16} {'Area':<14} {'Postcode':<9} {'Lat,Lng':<19} {'Address':<45} Hours")
    for name, c in centres.items():
        hours = "null" if c["hours"] is None else " ".join(
            f"{d} {o}-{cl or '?'}" for d, (o, cl) in c["hours"].items())
        latlng = f"{c['lat']:.4f},{c['lng']:.4f}" if c["lat"] is not None else "null"
        print(f"{name:<16} {c['area'] or 'null':<14} {c['postcode'] or 'null':<9} {latlng:<19} "
              f"{(c['address'] or 'null')[:45]:<45} {hours}")
    print("\nNulls / issues:")
    for line in report:
        print(" -", line)


if __name__ == "__main__":
    sys.exit(main())
