"""Write the committed public snapshot, data/public/sessions.json.

    OFFLINE=0 python3 -m tools.public_snapshot

Runs only the public adapters against config/chains.json (private adapters and
config/chains.private.json are ignored), keeps only PUBLIC_FIELDS per session, and refuses to
write if any adapter failed.
"""
import datetime
import json
import os

import paths
from main import HORIZON_DAYS, collect, public_view


def main():
    if paths.OFFLINE:
        raise SystemExit("OFFLINE=1 (the default): building the public snapshot needs live requests. Run with OFFLINE=0.")
    today = datetime.date.today()
    sessions, errors = collect(today, HORIZON_DAYS, public_only=True)
    if errors:
        raise SystemExit(f"Not writing the public snapshot, a chain failed: {'; '.join(errors)}")
    data = public_view({"refreshed_at": datetime.datetime.now().isoformat(timespec="seconds"),
                        "start": today.isoformat(), "days": HORIZON_DAYS, "sessions": sessions})
    os.makedirs(os.path.dirname(paths.PUBLIC_SNAPSHOT), exist_ok=True)
    with open(paths.PUBLIC_SNAPSHOT, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {os.path.relpath(paths.PUBLIC_SNAPSHOT, paths.ROOT)}: {len(data['sessions'])} sessions")


if __name__ == "__main__":
    main()
