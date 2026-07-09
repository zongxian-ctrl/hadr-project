"""Level 8 — the capstone: gather every source, see the aftermath, render a UI.

Ties the whole harness together and runs end to end, automatically:

  1. GATHER (deterministic): pull significant events from GDACS + USGS + EONET
     into one list with coordinates and dates; record which sources answered.
  2. SEE (deterministic): fetch a NASA true-color satellite image per event
     (GIBS/WorldView, embedded as a self-contained data: URI), PLUS a second
     image with NASA's fire-detection overlay — a page toggle swaps between them.
  3. ASSESS (model): one call to write a 'who is affected' line per event.
  4. RENDER (deterministic): a polished, self-contained HTML dashboard, with a
     feed-status line so a silent feed failure is visible (not just "fewer events").

Deterministic gather+render on the outside, the model only for judgement in the
middle — the same architecture as the real project. Reliable *and* smart.

Run:  python harness/level8_capstone.py
Produces: harness-dashboard.html
"""

import html as html_mod
import json
from pathlib import Path

from llm import call_model
from tools import (
    DASHBOARD_PATH,
    FIRE_LAYER,
    TRUECOLOR,
    fetch_eonet,
    fetch_feed,
    fetch_usgs,
    snapshot_data_uri,
)

MAX_EVENTS = 8


def gather():
    """Deterministically pull significant events (with coords + date) from all
    sources. Returns (events, status) where status[source] is a count or 'unreachable'."""
    events, status = [], {}

    def add(source, raw, mapper, cap):
        d = json.loads(raw)
        if "error" in d:
            status[source] = "unreachable"
            return
        picked = [mapper(e) for e in d.get("events", [])[:cap]]
        picked = [e for e in picked if e["lat"] is not None and e["lon"] is not None]
        events.extend(picked)
        status[source] = len(picked)

    add("GDACS", fetch_feed(), lambda e: {
        "source": "GDACS", "title": e["title"], "severity": e.get("alert"),
        "where": e.get("country"),
        "lon": (e.get("coords") or [None, None])[0],
        "lat": (e.get("coords") or [None, None])[1], "date": e.get("date")}, 99)
    add("USGS", fetch_usgs(5.0, "day"), lambda e: {
        "source": "USGS", "title": f"M{e['mag']} — {e['place']}",
        "severity": f"M{e['mag']}", "where": e.get("place"),
        "lon": (e.get("coords") or [None, None])[0],
        "lat": (e.get("coords") or [None, None])[1], "date": e.get("time")}, 3)
    add("EONET", fetch_eonet("wildfires", 8), lambda e: {
        "source": "EONET", "title": e["title"], "severity": e.get("category"),
        "where": None,
        "lon": (e.get("coords") or [None, None])[0],
        "lat": (e.get("coords") or [None, None])[1], "date": e.get("date")}, 3)

    return events[:MAX_EVENTS], status


def assess(events):
    """One model call: a 'who is affected' line per event. Falls back to '' on failure."""
    listing = "\n".join(f"{i}. {e['title']} ({e['source']}, {e.get('where') or ''})"
                        for i, e in enumerate(events))
    prompt = ("For each numbered event, write ONE short 'who/what is affected' sentence. "
              "No invented figures. Reply JSON only: {\"0\": \"...\", \"1\": \"...\"}\n\n" + listing)
    try:
        text = call_model([{"role": "user", "content": prompt}]).get("content", "")
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        for i, e in enumerate(events):
            e["assessment"] = obj.get(str(i), "")
    except Exception:
        for e in events:
            e.setdefault("assessment", "")
    return events


def render(events, status):
    """Deterministic polished UI (fixed template, self-contained)."""
    esc = html_mod.escape
    sev_class = {"Red": "red", "Orange": "orange"}
    cards = []
    for e in events:
        plain = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "", layers=TRUECOLOR)
        fire = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "",
                                 layers=f"{TRUECOLOR},{FIRE_LAYER}") or plain
        if plain:
            img_html = (f'<img class="sat" src="{plain}" data-plain="{plain}" '
                        f'data-fire="{fire}" alt="satellite view" loading="lazy">')
        else:
            img_html = '<div class="noimg">imagery unavailable</div>'
        sev = e.get("severity") or ""
        cls = sev_class.get(sev, "usgs" if e["source"] == "USGS" else "eonet")
        when = (e.get("date") or "")[:10]
        cards.append(f"""    <article class="card {cls}">
      {img_html}
      <div class="body">
        <div class="row"><span class="badge {cls}">{esc(str(sev))}</span>
          <span class="src">{esc(e['source'])}</span></div>
        <h2>{esc(e['title'])}</h2>
        <p class="meta">{esc(e.get('where') or '')}{' · ' if e.get('where') else ''}{esc(when)}
          · {e['lat']:.2f}, {e['lon']:.2f}</p>
        <p class="assess">{esc(e.get('assessment') or '')}</p>
      </div>
    </article>""")

    status_bits = []
    for src in ("GDACS", "USGS", "EONET"):
        v = status.get(src, "—")
        status_bits.append(f'<span class="{"down" if v == "unreachable" else "ok"}">{src}: {v}</span>')
    status_line = " · ".join(status_bits)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Aftermath Dashboard</title>
<style>
  :root{{--bg:#f4f5f7;--fg:#1a1d21;--card:#fff;--muted:#5b6470;--line:#e3e6ea;
  --red:#c62828;--orange:#d97706;--usgs:#2563eb;--eonet:#b45309;--ok:#2e7d32;--down:#c62828;
  color-scheme:light dark;}}
  @media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e8eaed;--card:#1a1d23;
  --muted:#9aa3ad;--line:#2c3038;--red:#ef7070;--orange:#f0a24b;--usgs:#6ea8fe;--eonet:#f0b357;
  --ok:#7cc47f;--down:#ef7070;}}}}
  *{{box-sizing:border-box;}} body{{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
  header{{max-width:1100px;margin:0 auto;padding:2rem 1.25rem .5rem;}}
  h1{{margin:0 0 .2rem;font-size:1.6rem;}} .sub{{color:var(--muted);font-size:.9rem;}}
  .bar{{max-width:1100px;margin:.4rem auto 0;padding:0 1.25rem;display:flex;gap:1.2rem;
  align-items:center;flex-wrap:wrap;font-size:.82rem;color:var(--muted);}}
  .bar .ok{{color:var(--ok);}} .bar .down{{color:var(--down);font-weight:700;}}
  .toggle{{margin-left:auto;color:var(--fg);cursor:pointer;user-select:none;}}
  .grid{{max-width:1100px;margin:1rem auto;padding:0 1.25rem 3rem;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.1rem;}}
  .card{{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--muted);
  border-radius:12px;overflow:hidden;display:flex;flex-direction:column;}}
  .card.red{{border-top-color:var(--red);}} .card.orange{{border-top-color:var(--orange);}}
  .card.usgs{{border-top-color:var(--usgs);}} .card.eonet{{border-top-color:var(--eonet);}}
  .card img{{width:100%;height:190px;object-fit:cover;background:#000;display:block;}}
  .noimg{{height:190px;display:flex;align-items:center;justify-content:center;
  color:var(--muted);background:var(--line);font-size:.85rem;}}
  .body{{padding:.8rem 1rem 1rem;}} .row{{display:flex;gap:.5rem;align-items:center;margin-bottom:.3rem;}}
  .badge{{font-size:.7rem;font-weight:700;text-transform:uppercase;padding:.1rem .5rem;
  border-radius:99px;color:#fff;background:var(--muted);}}
  .badge.red{{background:var(--red);}} .badge.orange{{background:var(--orange);}}
  .badge.usgs{{background:var(--usgs);}} .badge.eonet{{background:var(--eonet);}}
  .src{{color:var(--muted);font-size:.78rem;}} h2{{font-size:1.02rem;margin:.1rem 0 .3rem;}}
  .meta{{color:var(--muted);font-size:.8rem;margin:.2rem 0;}} .assess{{margin:.5rem 0 0;font-size:.92rem;}}
</style></head><body>
  <header>
    <h1>🛰️ HADR Aftermath Dashboard</h1>
    <p class="sub">{len(events)} significant events · each with a NASA true-color
      satellite view (GIBS/VIIRS ~250m: smoke, flood extent, burn scars)</p>
  </header>
  <div class="bar">
    <span>feeds:</span> {status_line}
    <label class="toggle"><input type="checkbox" id="fire" onchange="toggleFire(this.checked)">
      Show NASA fire detections</label>
  </div>
  <main class="grid">
{chr(10).join(cards)}
  </main>
  <script>
    function toggleFire(on) {{
      document.querySelectorAll('img.sat').forEach(function(i) {{
        i.src = on ? i.dataset.fire : i.dataset.plain;
      }});
    }}
  </script>
</body></html>
"""
    Path(DASHBOARD_PATH).write_text(page, encoding="utf-8")
    return len(page)


def main():
    print("1/4 gathering events from GDACS + USGS + EONET …")
    events, status = gather()
    print(f"    feeds: {status}")
    if not events:
        print("No located events right now; nothing to render.")
        return 0
    print("2/4 assessing (model: who is affected) …")
    events = assess(events)
    print("3/4 fetching aftermath imagery (true-color + fire overlay) + 4/4 rendering …")
    size = render(events, status)
    print(f"Done → {DASHBOARD_PATH} ({size // 1024} KB). Toggle fire detections in the page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
