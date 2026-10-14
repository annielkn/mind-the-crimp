# mindthecrimp
Cheap climbing sessions for the next 28 days across chains in `config/chains.json` (adapters in `adapters/`).
Setup: `python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt && (cd web && npm install && npm run build)`
CLI: `python3 main.py` · Web: `python3 server.py` → http://localhost:8000 · `OFFLINE=1` (default) uses your newest local snapshot, else the committed one; `OFFLINE=0` fetches live
Frontend dev: run `python3 server.py`, then `cd web && npm run dev` (proxies /api to :8000)
Note: `web/dist` (the built site) isn't committed. On a fresh clone run `cd web && npm install && npm run build` once (needs network) before `python3 server.py` can serve the page.

## Offline by default
Runs offline by default from the committed snapshot (`data/public/sessions.json`). `OFFLINE=0` refreshes from public gym websites; please keep request volume low.
