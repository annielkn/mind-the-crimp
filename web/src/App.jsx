import { useEffect, useRef, useState } from "react";

// Day headings: "Today", "Tomorrow", then "Friday 16 October". Relative to the viewer's real today,
// so an old offline snapshot never labels a past day "Today".
function formatDate(iso) {
  const today = localToday();
  if (iso === today) return "Today";
  if (iso === addDays(today, 1)) return "Tomorrow";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

// Vite's base ("./"): asset and data URLs stay relative, so the site works at / (server.py) and
// under a subpath like /mind-the-crimp/ (GitHub Pages).
const BASE = import.meta.env.BASE_URL;

// Pixel-art sprite from /public/sprites (made by tools/piskel_export.py): the animated GIF,
// or the first frame (<name>_f0.png) for reduced motion. <name>.png is the full sprite sheet.
// size must be a whole multiple of the 48px native size (32px for crimp) to stay crisp.
function Sprite({ name, size }) {
  return (
    <picture>
      <source srcSet={`${BASE}sprites/${name}_f0.png`} media="(prefers-reduced-motion: reduce)" />
      <img className="sprite" src={`${BASE}sprites/${name}.gif`} width={size} height={size} alt="" />
    </picture>
  );
}

// 24h departure-board time: "07:00–09:30". start is null only if a centre's opening time is unknown.
const timeRange = (s) => `${s.start ?? "?"}–${s.end}`;

// 8 -> "8", 7.5 -> "7.50"
const money = (p) => (Number.isInteger(p) ? String(p) : p.toFixed(2));

function formatPrice(s) {
  if (s.price == null) return "£?";
  return s.price_max != null ? `£${money(s.price)}–${money(s.price_max)}` : `£${money(s.price)}`;
}

// Live availability exists only for sessions scraped with spaces (private data); hand-entered
// sessions have no "avail" field and show their label instead.
function statusPill(s) {
  if (s.type === "walk-in") return <span className="pill lilac">Walk-in</span>;
  if ("avail" in s) return availability(s);
  return s.label ? <span className="pill lilac">{s.label}</span> : null;
}

// Spaces left, "Low: N" at 5 or fewer, or Full.
function availability(s) {
  if (s.full) return <span className="avail full">Full</span>;
  if (s.avail == null) return null;
  if (s.avail <= 5) return <span className="pill low">Low: {s.avail}</span>;
  return <span className="avail">{s.avail} spaces</span>;
}

const PILL_COLOURS = ["mint", "peach", "lilac"];

// One departure-board row per session; the whole row links to the booking/info page.
function SessionRow({ s, chainColour, distance }) {
  const body = (
    <>
      <span className="time">{timeRange(s)}</span>
      <span className="gym">
        {s.centre}
        {distance != null && <span className="dist"> · {distance.toFixed(1)} km</span>}
      </span>
      <span className="meta">
        <span className={`pill ${chainColour}`}>{s.chain}</span>
        {statusPill(s)}
      </span>
      <span className="price">{formatPrice(s)}</span>
    </>
  );
  const title = [s.address, ...(s.conditions ?? [])].filter(Boolean).join(" · ");
  return s.link ? (
    <a className="row" href={s.link} target="_blank" rel="noreferrer" title={title}>
      {body}
    </a>
  ) : (
    <div className="row" title={title}>{body}</div>
  );
}

// sessions -> [[date, [session, ...]]] in date order
function groupByDate(sessions) {
  const days = {};
  for (const s of sessions) (days[s.date] ??= []).push(s);
  return Object.keys(days)
    .sort()
    .map((date) => [date, days[date]]);
}

// Date maths on "YYYY-MM-DD" strings, in UTC so DST never shifts a day.
function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// "2026-10-15", "2026-10-21" -> "15–21 Oct"; across months -> "28 Oct – 3 Nov"; same day -> "18 Oct"
function dateSpan(from, to) {
  const fmt = (iso, opts) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", opts);
  if (from === to) return fmt(from, { day: "numeric", month: "short" });
  if (from.slice(0, 7) === to.slice(0, 7)) return `${fmt(from, { day: "numeric" })}–${fmt(to, { day: "numeric", month: "short" })}`;
  return `${fmt(from, { day: "numeric", month: "short" })} – ${fmt(to, { day: "numeric", month: "short" })}`;
}

// Great-circle distance in km.
function haversine(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

// "se1" -> "SE1"; "SE1 7PB" / "SE17PB" -> "SE1" (outward code)
function outcode(input) {
  const t = input.trim().toUpperCase();
  if (t.includes(" ")) return t.split(/\s+/)[0];
  return /^[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}$/.test(t) ? t.slice(0, -3) : t;
}

// Outcode lookups are cached per browser; storage can be unavailable, so never let it throw.
function cacheGet(code) {
  try {
    return JSON.parse(localStorage.getItem(`outcode:${code}`));
  } catch {
    return null;
  }
}
function cacheSet(code, point) {
  try {
    localStorage.setItem(`outcode:${code}`, JSON.stringify(point));
  } catch {
    /* ignore */
  }
}

const DEFAULT_DAYS = 3; // default view: today + the next 2 days
const WITHIN = [3, 5, 10];
const RANGES = [0, 1, 3, 7];
const DEFAULT_RANGE = 3; // used when a date is picked
const NEXT = "next"; // Range option "Next 3 days": no date, today onwards

// Filter state lives in the URL (?chain=&area=&near=&within=&date=&range=) so views are shareable.
function readParams() {
  const p = new URLSearchParams(window.location.search);
  const date = p.get("date") ?? "";
  const range = Number(p.get("range"));
  const within = Number(p.get("within"));
  return {
    chain: p.get("chain") ?? "",
    areas: p.get("area") ? p.get("area").split(",") : [],
    near: p.get("near") ?? "",
    within: WITHIN.includes(within) ? within : 0,
    date,
    range: !date ? NEXT : p.has("range") && RANGES.includes(range) ? range : DEFAULT_RANGE,
  };
}

function writeParams({ chain, areas, near, within, date, range }) {
  const p = new URLSearchParams();
  if (chain) p.set("chain", chain);
  if (areas.length) p.set("area", areas.join(","));
  if (near.trim()) p.set("near", near.trim());
  if (near.trim() && within) p.set("within", within);
  if (date) p.set("date", date);
  if (date && range !== DEFAULT_RANGE) p.set("range", range);
  const qs = p.toString();
  window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
}

const unique = (values) => [...new Set(values)].sort();

function AreaSelect({ options, value, onChange }) {
  const toggle = (a) => onChange(value.includes(a) ? value.filter((x) => x !== a) : [...value, a]);
  const ref = useRef(null);
  // Close the dropdown on a click/tap outside it, or on Escape.
  useEffect(() => {
    const close = (e) => {
      const el = ref.current;
      if (el?.open && (e.key === "Escape" || (e.type === "pointerdown" && !el.contains(e.target)))) el.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  return (
    <div className="chip multi-chip">
      <span>Area</span>
      <details className="multi" ref={ref}>
        <summary>{value.length === 0 ? "All" : value.length === 1 ? value[0] : `${value.length} areas`}</summary>
        <div className="multi-options">
          {options.map((a) => (
            <label key={a}>
              <input type="checkbox" checked={value.includes(a)} onChange={() => toggle(a)} /> {a}
            </label>
          ))}
          {value.length > 0 && (
            <button type="button" className="link-button" onClick={() => onChange([])}>Clear</button>
          )}
        </div>
      </details>
    </div>
  );
}

function Filter({ label, value, options, onChange }) {
  return (
    <label className="chip">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [initial] = useState(readParams);
  const [chain, setChain] = useState(initial.chain);
  const [areas, setAreas] = useState(initial.areas);
  const [near, setNear] = useState(initial.near);
  const [within, setWithin] = useState(initial.within); // 0 = any distance
  const [nearPoint, setNearPoint] = useState(null);
  const [nearError, setNearError] = useState("");
  const [date, setDate] = useState(initial.date);
  const [range, setRange] = useState(initial.range);
  // Current time as "HH:MM", ticking every minute so finished sessions drop off on their own.
  const [now, setNow] = useState(nowHHMM);
  useEffect(() => {
    const timer = setInterval(() => setNow(nowHHMM()), 60 * 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(
    () => writeParams({ chain, areas, near, within, date, range }),
    [chain, areas, near, within, date, range]
  );

  // Resolve the "Near" postcode district to a point (postcodes.io, cached in localStorage).
  useEffect(() => {
    const code = outcode(near);
    setNearError("");
    setNearPoint(null);
    if (!code) return;
    const cached = cacheGet(code);
    if (cached) {
      setNearPoint(cached);
      return;
    }
    let live = true;
    const timer = setTimeout(() => {
      fetch(`https://api.postcodes.io/outcodes/${encodeURIComponent(code)}`)
        .then((r) => (r.status === 404 ? null : r.json()))
        .then((body) => {
          if (!live) return;
          const res = body?.result;
          if (!res || res.latitude == null) return setNearError("Unknown postcode area");
          const point = { lat: res.latitude, lng: res.longitude };
          cacheSet(code, point);
          setNearPoint(point);
        })
        .catch(() => live && setNearError("Couldn't look up that postcode"));
    }, 400);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [near]);

  useEffect(() => {
    // server.py serves api/sessions; a static host only has the committed snapshot (deployed as sessions.json).
    // On GitHub Pages go straight to the snapshot, so there's no failed api/ request in the console.
    const getJSON = (url) => fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${url}: HTTP ${r.status}`))));
    const snapshot = () => getJSON(`${BASE}sessions.json`).then((body) => ({ ...body, mode: "snapshot" }));
    const onPages = window.location.hostname.endsWith("github.io");
    (onPages ? snapshot() : getJSON(`${BASE}api/sessions`).catch(snapshot))
      .then((body) => (body.error ? setError(body.error) : setData(body)))
      .catch((e) => setError(String(e)));
  }, []);

  const sessions = data ? data.sessions : [];
  const chains = unique(sessions.map((s) => s.chain));
  // Only offer areas that exist for the selected chain.
  const areaOptions = unique(sessions.filter((s) => !chain || s.chain === chain).map((s) => s.area).filter(Boolean));
  const distance = (s) => (nearPoint && s.lat != null ? haversine(nearPoint, s) : null);
  // Start from the real today, even when an older offline snapshot also has past days in it.
  const today = data?.start > localToday() ? data.start : localToday();
  const last = addDays(today, (data?.days ?? DEFAULT_DAYS) - 1);
  // No date picked: the next 3 days. Date picked: date ± range, clamped to what was fetched.
  const from = date ? (addDays(date, -range) > today ? addDays(date, -range) : today) : today;
  const to = date
    ? addDays(date, range) < last ? addDays(date, range) : last
    : addDays(today, DEFAULT_DAYS - 1);
  const shown = sessions.filter(
    (s) =>
      (!chain || s.chain === chain) &&
      (!areas.length || areas.includes(s.area)) &&
      (!nearPoint || !within || (distance(s) != null && distance(s) <= within)) &&
      s.date >= from &&
      s.date <= to &&
      // Hide today's sessions once their end time has passed (e.g. Mile End "until 09:30" at 09:31).
      !(s.date === localToday() && s.end && s.end < now)
  );
  // Within a day: nearest first when Near is set, otherwise by start time (the server's order).
  const days = groupByDate(shown).map(([day, rows]) => [
    day,
    nearPoint ? [...rows].sort((a, b) => (distance(a) ?? Infinity) - (distance(b) ?? Infinity)) : rows,
  ]);
  const chainColour = (c) => PILL_COLOURS[chains.indexOf(c) % PILL_COLOURS.length];

  function pickDate(value) {
    setDate(value);
    if (!value) setRange(NEXT);
    else if (range === NEXT) setRange(DEFAULT_RANGE);
  }

  function pickRange(value) {
    if (value === NEXT) {
      setRange(NEXT);
      setDate("");
      return;
    }
    setRange(Number(value));
    if (!date) setDate(today);
  }

  function pickChain(value) {
    setChain(value);
    if (value) setAreas(areas.filter((a) => sessions.some((s) => s.chain === value && s.area === a)));
  }

  return (
    <main>
      <header>
        <div className="brand">
          <Sprite name="chalkbag_happy" size={48} />
          <h1>Mind the Crimp</h1>
        </div>
        <p className="tagline">See it. Send it. Sorted.</p>
        {data && (
          <p className={`pill status ${{ live: "mint", snapshot: "lilac" }[data.mode] ?? "peach"}`}>
            {data.mode === "live"
              ? `Live · updated ${new Date(data.refreshed_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`
              : data.mode === "snapshot"
                ? `Snapshot · updated ${new Date(data.refreshed_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`
                : `Offline · data from ${new Date(data.refreshed_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`}
          </p>
        )}
      </header>
      {error && <p className="error">Couldn't load sessions: {error}</p>}
      {data?.errors.map((e) => <p key={e} className="error">{e}</p>)}
      {!data && !error && (
        <div className="state" role="status" aria-label="Loading sessions">
          <Sprite name="chalkbag_happy" size={96} />
        </div>
      )}
      {data && (
        <div className="filters">
          <label className="chip">
            <span>Date</span>
            <input type="date" value={date} min={today} max={last} onChange={(e) => pickDate(e.target.value)} />
          </label>
          <label className="chip">
            <span>Range</span>
            <select value={range} onChange={(e) => pickRange(e.target.value)}>
              <option value={NEXT}>Next {DEFAULT_DAYS} days</option>
              {RANGES.map((r) => (
                <option key={r} value={r}>{r === 0 ? "That day only" : `± ${r} day${r > 1 ? "s" : ""}`}</option>
              ))}
            </select>
          </label>
          <label className="chip near">
            <span>Near</span>
            <input
              type="text"
              value={near}
              placeholder="e.g. SE1"
              autoComplete="postal-code"
              onChange={(e) => setNear(e.target.value)}
            />
            <select
              value={within}
              disabled={!nearPoint}
              aria-label="Within"
              onChange={(e) => setWithin(Number(e.target.value))}
            >
              <option value={0}>any km</option>
              {WITHIN.map((km) => (
                <option key={km} value={km}>≤ {km} km</option>
              ))}
            </select>
          </label>
          <Filter label="Chain" value={chain} options={chains} onChange={pickChain} />
          <AreaSelect options={areaOptions} value={areas} onChange={setAreas} />
          {nearError && <p className="error">{nearError}</p>}
        </div>
      )}
      {data && (
        <h2 className="window">
          Showing options for {dateSpan(from, to)}
          {nearPoint && (within ? ` within ${within} km of ${outcode(near)}` : ` near ${outcode(near)}`)}
        </h2>
      )}
      {data && days.length === 0 && (
        <div className="state">
          <Sprite name="chalkbag_sleepy" size={96} />
          <p>Wallet says rest day.</p>
        </div>
      )}
      {days.map(([day, rows]) => (
        <section className="card" key={day}>
          <h2>{formatDate(day)}</h2>
          {rows.map((s, i) => (
            <SessionRow key={i} s={s} chainColour={chainColour(s.chain)} distance={distance(s)} />
          ))}
        </section>
      ))}
      <footer className="site-footer">
        <nav aria-label="Site">
          <a href="./" aria-current="page">Home</a>
          <a href="./about.html">About</a>
        </nav>
      </footer>
    </main>
  );
}
