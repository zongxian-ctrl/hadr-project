"""Level 8 — the capstone: gather every source, see the aftermath, render a UI.

Ties the whole harness together and runs end to end, automatically:

  1. GATHER (deterministic): pull significant events from GDACS + USGS + EONET
     into one list with coordinates and dates.
  2. SEE (deterministic): fetch a NASA aftermath satellite image per event
     (GIBS/WorldView, embedded as a self-contained data: URI).
  3. ASSESS (model): one call to write a 'who is affected' line per event.
  4. RENDER (deterministic): a polished, self-contained HTML dashboard.

This is the same split the real project uses: deterministic gather + render on
the outside, the model only for judgement in the middle. Reliable *and* smart.

Run:  python harness/level8_capstone.py
Produces: harness-dashboard.html
"""

import html as html_mod
import json
import sys

from llm import call_model
from tools import (
    DASHBOARD_PATH,
    fetch_eonet,
    fetch_feed,
    fetch_usgs,
    snapshot_data_uri,
)

MAX_EVENTS = 8


def gather():
    """Deterministically pull significant events (with coords + date) from all sources."""
    events = []
    for e in json.loads(fetch_feed()).get("events", []):
        c = e.get("coords") or [None, None]
        events.append({"source": "GDACS", "title": e["title"], "severity": e.get("alert"),
                       "where": e.get("country"), "lon": c[0], "lat": c[1], "date": e.get("date")})
    for e in json.loads(fetch_usgs(5.0, "day")).get("events", [])[:3]:
        c = e.get("coords") or [None, None]
        events.append({"source": "USGS", "title": f"M{e['mag']} — {e['place']}",
                       "severity": f"M{e['mag']}", "where": e.get("place"),
                       "lon": c[0], "lat": c[1], "date": e.get("time")})
    for e in json.loads(fetch_eonet("wildfires", 8)).get("events", [])[:3]:
        c = e.get("coords") or [None, None]
        events.append({"source": "EONET", "title": e["title"], "severity": e.get("category"),
                       "where": None, "lon": c[0], "lat": c[1], "date": e.get("date")})
    events = [e for e in events if e["lat"] is not None and e["lon"] is not None]
    return events[:MAX_EVENTS]


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


def render(events):
    """Deterministic polished UI (fixed template, self-contained). Guarantees 'nice'."""
    esc = html_mod.escape
    sev_class = {"Red": "red", "Orange": "orange"}
    cards = []
    for e in events:
        img = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "")
        img_html = (f'<img src="{img}" alt="satellite view" loading="lazy">' if img
                    else '<div class="noimg">imagery unavailable</div>')
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

    counts = {}
    for e in events:
        counts[e["source"]] = counts.get(e["source"], 0) + 1
    summary = " · ".join(f"{v} {k}" for k, v in counts.items()) or "no events"

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Aftermath Dashboard</title>
<style>
  :root{{--bg:#f4f5f7;--fg:#1a1d21;--card:#fff;--muted:#5b6470;--line:#e3e6ea;
  --red:#c62828;--orange:#d97706;--usgs:#2563eb;--eonet:#b45309;color-scheme:light dark;}}
  @media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e8eaed;--card:#1a1d23;
  --muted:#9aa3ad;--line:#2c3038;--red:#ef7070;--orange:#f0a24b;--usgs:#6ea8fe;--eonet:#f0b357;}}}}
  *{{box-sizing:border-box;}} body{{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
  header{{max-width:1100px;margin:0 auto;padding:2rem 1.25rem .5rem;}}
  h1{{margin:0 0 .2rem;font-size:1.6rem;}} .sub{{color:var(--muted);font-size:.9rem;}}
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
    <p class="sub">{len(events)} significant events ({summary}) · each with a NASA
      satellite view (GIBS/VIIRS ~250m: smoke, fire hotspots, flood extent, burn scars)</p>
  </header>
  <main class="grid">
{chr(10).join(cards)}
  </main>
</body></html>
"""
    from pathlib import Path
    Path(DASHBOARD_PATH).write_text(page, encoding="utf-8")
    return len(page)


def main():
    print("1/4 gathering events from GDACS + USGS + EONET …")
    events = gather()
    print(f"    {len(events)} events with coordinates.")
    if not events:
        print("No located events right now; nothing to render.")
        return 0
    print("2/4 assessing (model: who is affected) …")
    events = assess(events)
    print("3/4 fetching aftermath satellite imagery + 4/4 rendering …")
    size = render(events)
    print(f"Done → {DASHBOARD_PATH} ({size // 1024} KB, images embedded).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
