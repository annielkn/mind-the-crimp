"""Chains entered by hand: weekly rules in config, expanded to dated sessions. No network."""
import datetime


def fetch(chain_cfg, session, state, start_date, days):
    sessions = []
    for i in range(days):
        day = start_date + datetime.timedelta(days=i)
        for rule in chain_cfg.get("rules", []):
            if rule["day"] != day.strftime("%a"):
                continue
            sessions.append({
                "chain": chain_cfg["name"], "centre": rule["centre"], "date": day.isoformat(),
                "start": rule["start"], "end": rule["end"], "price": rule.get("price"),
                "label": rule.get("label"), "conditions": rule.get("conditions", []),
                "type": chain_cfg["type"], "link": rule.get("link"),
            })
    return sessions
