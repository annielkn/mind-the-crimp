# Mind the Crimp!
Checks for sub-£10 climbing sessions for adults in London and shows data for the next 28 days

**Live:** https://annielkn.github.io/mind-the-crimp/

## Quick start
Setup:
`python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt && (cd web && npm install && npm run build)`

- CLI: `python3 main.py`
- Web: `python3 server.py` → http://localhost:8000
- Frontend dev: run `python3 server.py`, then `cd web && npm run dev` (proxies `/api` to :8000)

Note:
`web/dist` isn't committed. The build step in Setup (needs network) must run once before `server.py` can serve the page

## Data modes
- `OFFLINE=1` (default): no network. Shows the last live fetch if there is one, otherwise the bundled snapshot in `data/public/sessions.json`
- `OFFLINE=0`: fetches live from gym websites and saves the result locally. Please keep request volume low
