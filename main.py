import datetime
import glob
import json
import os
import shutil

import requests

import paths
from adapters import ADAPTERS, PRIVATE, PUBLIC_ADAPTERS
from adapters.common import load_state, save_state

# How far ahead to fetch, in days (CLI and web). The web page shows 14 by default and filters client-side.
HORIZON_DAYS = 28


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


OVERRIDE_MAX_AGE_DAYS = 90


def deep_merge(base, over):
    """over wins; nested dicts merge, everything else (lists included) is replaced."""
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_chains():
    """config/chains.json, with config/chains.private.json (gitignored) merged over it if present."""
    return deep_merge(load_json(paths.CHAINS, {}), load_json(paths.CHAINS_PRIVATE, {}))


def load_overrides(collected):
    """overrides.json (manual values) merged over the collected centres; the override wins."""
    for name, o in load_json(paths.OVERRIDES, {}).items():
        fields = {k: v for k, v in o.items() if k not in ("source", "verified")}
        if not o.get("source") or not o.get("verified"):
            print(f"WARNING: override for {name!r} needs both 'source' and 'verified'")
        else:
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(o["verified"])).days
                if age > OVERRIDE_MAX_AGE_DAYS:
                    print(f"WARNING: override for {name!r} was verified {age} days ago ({o['verified']}); re-check it")
            except ValueError:
                print(f"WARNING: override for {name!r} has a bad 'verified' date {o['verified']!r}")
        if name not in collected:
            print(f"WARNING: override for {name!r} has no entry in centres.json")
        collected[name] = {**collected.get(name, {}), **fields,
                           "override": {"fields": sorted(fields), "source": o.get("source"),
                                        "verified": o.get("verified")}}
        if "hours" in fields:
            collected[name]["hours_source"] = o.get("source")
    return collected


def load_centres():
    """centres.json + overrides.json, keyed by every name a centre goes by (its key plus any aliases)."""
    centres = {}
    for name, c in load_overrides(load_json(paths.CENTRES, {})).items():
        for n in [name, *c.get("aliases", [])]:
            centres[n] = c
    return centres


def apply_centre_info(s, centres):
    """Fill a missing start/end from opening hours, warn on sessions outside them, attach the address."""
    c = centres.get(s["centre"])
    if not c:
        return
    if c.get("address"):
        s["address"] = ", ".join(p for p in [c["address"], c.get("postcode")] if p)
    s["area"], s["lat"], s["lng"] = c.get("area"), c.get("lat"), c.get("lng")
    hours = (c.get("hours") or {}).get(datetime.date.fromisoformat(s["date"]).strftime("%a"))
    if not hours:
        return
    opens, closes = hours  # either may be null when unknown
    s["start"] = s["start"] or opens
    s["end"] = s["end"] or closes
    if (opens and s["start"] and s["start"] < opens) or (closes and s["end"] and s["end"] > closes):
        print(f"WARNING: {s['chain']} {s['centre']} {s['date']} {s['start']}-{s['end']} is outside opening hours {opens}-{closes}")


def check_names(sessions, centres):
    """Session centre names vs centres.json (keys + aliases). Reports only; never raises."""
    try:
        seen = {s["centre"] for s in sessions}
        for name in sorted(seen - set(centres)):
            print(f"WARNING: centre {name!r} has no entry in centres.json")
        entries = {id(c): c for c in centres.values()}
        names = {id(c): [n for n, x in centres.items() if x is c] for c in entries.values()}
        for key, c in entries.items():
            if not seen & set(names[key]):
                print(f"NOTE: centres.json entry {names[key][0]!r} had no sessions this run")
    except Exception as e:
        print(f"WARNING: centre name check failed: {e}")


def collect(start_date, days=HORIZON_DAYS, public_only=False):
    """Run every chain's adapter; returns (sessions sorted by date/time, [error strings]).
    public_only: ignore private adapters and config/chains.private.json (for the committed snapshot)."""
    chains = load_json(paths.CHAINS, {}) if public_only else load_chains()
    adapters = PUBLIC_ADAPTERS if public_only else ADAPTERS
    state = load_state()
    for mod in [] if public_only else PRIVATE:  # private adapters keep their request budgets in state.json
        if hasattr(mod, "bind_state"):
            mod.bind_state(state)
    session = requests.Session()
    sessions, errors = [], []
    for chain_id, cfg in chains.items():
        try:
            sessions += adapters[cfg["source"]](cfg, session, state.setdefault(chain_id, {}), start_date, days)
        except Exception as e:
            errors.append(f"[{cfg.get('name', chain_id)}] failed: {e}")
            print(errors[-1])
    save_state(state)
    centres = load_centres()
    for s in sessions:
        apply_centre_info(s, centres)
    check_names(sessions, centres)
    # start is None when unknown (e.g. Mile End "before 9:30am"); sort those first in the day.
    sessions.sort(key=lambda s: (s["date"], s["start"] or "", s["chain"], s["centre"]))
    return sessions, errors


KEEP_SNAPSHOTS = 5
STALE_WARNING_DAYS = 3


def snapshot_files():
    return sorted(glob.glob(os.path.join(paths.SNAPSHOT_DIR, "*.json")))


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=1)


def seed_snapshots():
    """First run: import the newest data_snapshot/*.json (left untouched), else the current
    sessions.json, as the first snapshot."""
    paths.ensure_data_dir()
    if snapshot_files():
        return
    legacy = sorted(glob.glob(os.path.join(paths.LEGACY_SNAPSHOT_DIR, "*.json")), key=os.path.getmtime)
    source = legacy[-1] if legacy else paths.SESSIONS
    data = load_json(source, None)
    if not data or "sessions" not in data:
        return
    data.setdefault("refreshed_at", data.get("fetched_at") or datetime.datetime.fromtimestamp(
        os.path.getmtime(source)).isoformat(timespec="seconds"))
    name = data["refreshed_at"][:16].replace(":", "-")
    write_json(os.path.join(paths.SNAPSHOT_DIR, f"{name}.json"), data)
    print(f"Imported {os.path.relpath(source, paths.ROOT)} as the first snapshot")


# Only these session fields go into the committed public snapshot (no availability/capacity).
PUBLIC_FIELDS = {"chain", "centre", "date", "start", "end", "price", "price_max", "label", "conditions",
                 "type", "link", "address", "area", "lat", "lng"}


def public_view(data):
    return {"refreshed_at": data["refreshed_at"], "start": data["start"], "days": data["days"], "errors": [],
            "sessions": [{k: v for k, v in s.items() if k in PUBLIC_FIELDS} for s in data["sessions"]]}


def latest():
    """The last good refresh: local sessions.json, else the newest local snapshot, else the
    committed public snapshot (what a fresh clone uses). None if there's nothing at all."""
    seed_snapshots()
    data = load_json(paths.SESSIONS, None)
    if not data and snapshot_files():
        data = load_json(snapshot_files()[-1], None)
    if not data:
        data = load_json(paths.PUBLIC_SNAPSHOT, None)
    if data:
        data.setdefault("refreshed_at", data.get("fetched_at"))
    return data


def save_good(data):
    paths.ensure_data_dir()
    write_json(paths.SESSIONS, data)
    name = data["refreshed_at"][:16].replace(":", "-")
    write_json(os.path.join(paths.SNAPSHOT_DIR, f"{name}.json"), data)
    for old in snapshot_files()[:-KEEP_SNAPSHOTS]:
        os.remove(old)


def refresh(days=HORIZON_DAYS):
    """Live refresh. Only a fully successful run (every adapter worked) replaces sessions.json
    and adds a snapshot; otherwise returns None and the last good data stays."""
    today = datetime.date.today()
    sessions, errors = collect(today, days)
    if errors:
        print(f"Refresh incomplete, keeping last good data: {'; '.join(errors)}")
        return None
    data = {"refreshed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "start": today.isoformat(), "days": days, "sessions": sessions, "errors": []}
    save_good(data)
    return data


def age_days(data):
    return (datetime.datetime.now() - datetime.datetime.fromisoformat(data["refreshed_at"])).days


def offline_banner(data):
    days = age_days(data)
    print(f"OFFLINE — data from {data['refreshed_at']} ({days} days old)")
    if days > STALE_WARNING_DAYS:
        print(f"WARNING: offline data is more than {STALE_WARNING_DAYS} days old")


def status(s):
    if s["type"] == "walk-in":
        return "walk-in"
    if "avail" not in s:  # hand-entered sessions have no live availability
        return s.get("label") or "pre-book"
    if s["full"]:
        return "FULL"
    return f"{s['avail']} spaces" if s["avail"] is not None else "available"


def money(p):
    # 8 -> "8", 7.5 -> "7.50"
    return f"{p:g}" if p == int(p) else f"{p:.2f}"


def main():
    if paths.OFFLINE:
        data = latest()
        if not data:
            raise SystemExit("OFFLINE=1 and there's no snapshot yet. Run once with OFFLINE=0.")
        offline_banner(data)
    else:
        data = refresh() or latest()
        for mod in PRIVATE:
            if hasattr(mod, "report"):
                print(mod.report())
        if not data:
            raise SystemExit("Refresh failed and there's no earlier data to show.")
    for s in data["sessions"]:
        day = datetime.date.fromisoformat(s["date"]).strftime("%a")
        price = f"£{money(s['price'])}" if s["price"] is not None else "£?"
        if s.get("price_max") is not None:
            price += f"-{money(s['price_max'])}"
        times = f"{s['start']}-{s['end']}" if s["start"] else f"before {s['end']}"
        print(f"{s['date']} {day} | {s['chain']} | {s['centre']} | {times} | {price} | {status(s)}")


if __name__ == "__main__":
    main()
