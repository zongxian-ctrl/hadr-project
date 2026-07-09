"""Level 8 — the capstone: gather every source, see the aftermath, render a UI.

End to end, automatically:
  1. GATHER (deterministic): significant events from GDACS + USGS + EONET + NWS,
     each normalised to {severity level, coords, date}; record which feeds answered.
  2. SEE (deterministic): a NASA true-color image per event (+ a fire-overlay
     version), embedded as self-contained data: URIs; a page toggle swaps them.
  3. ASSESS (model): one call for a 'who is affected' line per event.
  4. RENDER (deterministic): a polished dashboard — KPI tiles, a world map with
     event dots, a severity legend, source filters, and the card grid.

Design follows the dataviz method: severity is a STATUS palette (red/orange +
always a label, never colour alone); sources are categorical; geography gets a
map. Deterministic gather+render outside, model only for judgement inside.

Run:  python harness/level8_capstone.py
Produces: harness-dashboard.html
"""

import html as html_mod
import json
from pathlib import Path

from llm import call_model
from tools import (
    DASHBOARD_PATH, FIRE_LAYER, TRUECOLOR,
    fetch_eonet, fetch_feed, fetch_nws, fetch_usgs, snapshot_data_uri,
)

MAX_EVENTS = 10
WORLD_PATH = (Path(__file__).parent / "assets" / "world_path.txt").read_text(encoding="utf-8")
SEV_RANK = {"red": 0, "orange": 1, "info": 2}
SEV_LABEL = {"red": "Severe impact", "orange": "Significant", "info": "Catalogued (no severity)"}


def gather():
    """Pull significant, located events from all sources. Returns (events, status)."""
    events, status = [], {}

    def add(source, raw, mapper, cap):
        d = json.loads(raw)
        if "error" in d:
            status[source] = "unreachable"
            return
        picked = []
        for e in d.get("events", []):
            m = mapper(e)
            if m and m["lat"] is not None and m["lon"] is not None:
                picked.append(m)
            if len(picked) >= cap:
                break
        events.extend(picked)
        status[source] = len(picked)

    def gd(e):
        c = e.get("coords") or [None, None]
        return {"source": "GDACS", "title": e["title"], "severity": e.get("alert"),
                "sev_level": "red" if e.get("alert") == "Red" else "orange",
                "where": e.get("country"), "lon": c[0], "lat": c[1], "date": e.get("date")}

    def us(e):
        c = e.get("coords") or [None, None]
        mag = e.get("mag") or 0
        return {"source": "USGS", "title": f"M{mag} — {e['place']}", "severity": f"M{mag}",
                "sev_level": "red" if mag >= 6 else "orange",
                "where": e.get("place"), "lon": c[0], "lat": c[1], "date": e.get("time")}

    def eo(e):
        c = e.get("coords") or [None, None]
        return {"source": "EONET", "title": e["title"], "severity": e.get("category"),
                "sev_level": "info", "where": e.get("category"),
                "lon": c[0], "lat": c[1], "date": e.get("date")}

    def nw(e):
        return {"source": "NWS", "title": e.get("event"), "severity": e.get("severity"),
                "sev_level": "red" if e.get("severity") == "Extreme" else "orange",
                "where": e.get("area"), "lon": e.get("lon"), "lat": e.get("lat"), "date": e.get("date")}

    add("GDACS", fetch_feed(), gd, 99)
    add("USGS", fetch_usgs(5.0, "day"), us, 4)
    add("EONET", fetch_eonet(None, 20), eo, 4)
    add("NWS", fetch_nws("Severe", 20), nw, 3)

    events.sort(key=lambda e: SEV_RANK.get(e["sev_level"], 3))
    return events[:MAX_EVENTS], status


def assess(events):
    """One model call: a 'who is affected' line per event. Falls back to '' on failure."""
    listing = "\n".join(f"{i}. {e['title']} ({e['source']}, {e.get('where') or ''})"
                        for i, e in enumerate(events))
    prompt = ("For each numbered event, write ONE short 'who/what is affected' sentence. "
              "No invented figures. Reply JSON only: {\"0\":\"...\"}\n\n" + listing)
    try:
        text = call_model([{"role": "user", "content": prompt}]).get("content", "")
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        for i, e in enumerate(events):
            e["assessment"] = obj.get(str(i), "")
    except Exception:
        for e in events:
            e.setdefault("assessment", "")
    return events


def _proj(lat, lon):
    return (lon + 180) / 360 * 1000, (90 - lat) / 180 * 500


def render(events, status):
    esc = html_mod.escape
    reds = sum(1 for e in events if e["sev_level"] == "red")
    oranges = sum(1 for e in events if e["sev_level"] == "orange")
    live = sum(1 for v in status.values() if v != "unreachable")

    dots = "".join(
        f'<circle cx="{_proj(e["lat"], e["lon"])[0]:.1f}" cy="{_proj(e["lat"], e["lon"])[1]:.1f}" '
        f'r="5" class="dot {e["sev_level"]}" data-source="{e["source"]}"><title>{esc(e["title"])}</title></circle>'
        for e in events)

    cards = []
    for e in events:
        plain = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "", layers=TRUECOLOR)
        fire = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "",
                                 layers=f"{TRUECOLOR},{FIRE_LAYER}") or plain
        img = (f'<img class="sat" src="{plain}" data-plain="{plain}" data-fire="{fire}" '
               f'alt="satellite view of {esc(e["title"])}" loading="lazy">' if plain
               else '<div class="noimg">imagery unavailable</div>')
        when = (e.get("date") or "")[:10]
        cards.append(f"""    <article class="card {e['sev_level']}" data-source="{esc(e['source'])}">
      {img}
      <div class="body">
        <div class="row"><span class="badge {e['sev_level']}">{esc(str(e.get('severity') or ''))}</span>
          <span class="src">{esc(e['source'])}</span></div>
        <h3>{esc(e['title'])}</h3>
        <p class="meta">{esc(e.get('where') or '')}{' · ' if e.get('where') else ''}{esc(when)}</p>
        <p class="assess">{esc(e.get('assessment') or '')}</p>
      </div>
    </article>""")

    status_line = " · ".join(
        f'<span class="{"down" if status.get(s) == "unreachable" else "ok"}">{s} {status.get(s, "—")}</span>'
        for s in ("GDACS", "USGS", "EONET", "NWS"))
    filters = "".join(f'<button class="chip" data-f="{s}" onclick="filt(this)">{s}</button>'
                      for s in ["All", "GDACS", "USGS", "EONET", "NWS"])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Situational Dashboard</title>
<style>
  :root{{--bg:#eef0f3;--panel:#fff;--fg:#12151a;--muted:#5b6470;--line:#e2e5ea;
  --red:#c62828;--orange:#d97706;--info:#2563eb;--land:#cdd3db;--ocean:#dde3ea;
  --ok:#2e7d32;--down:#c62828;--sh:0 1px 3px rgba(0,0,0,.08),0 4px 16px rgba(0,0,0,.05);}}
  @media(prefers-color-scheme:dark){{:root{{--bg:#0c0e12;--panel:#161a20;--fg:#e8eaed;
  --muted:#9aa3ad;--line:#252a32;--red:#ef7070;--orange:#f0a24b;--info:#6ea8fe;
  --land:#2b3038;--ocean:#171b21;--ok:#7cc47f;--down:#ef7070;--sh:0 1px 3px rgba(0,0,0,.4);}}}}
  *{{box-sizing:border-box;}} body{{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
  .wrap{{max-width:1180px;margin:0 auto;padding:1.75rem 1.25rem 3rem;}}
  h1{{margin:0;font-size:1.5rem;letter-spacing:-.01em;}}
  .sub{{color:var(--muted);font-size:.88rem;margin:.15rem 0 1.25rem;}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.9rem;margin-bottom:1.1rem;}}
  .kpi{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.9rem 1.1rem;box-shadow:var(--sh);}}
  .kpi .n{{font-size:1.9rem;font-weight:700;line-height:1;}} .kpi .l{{color:var(--muted);font-size:.8rem;margin-top:.35rem;}}
  .kpi.red .n{{color:var(--red);}} .kpi.orange .n{{color:var(--orange);}}
  .panel{{background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--sh);
  padding:1rem 1.1rem;margin-bottom:1.1rem;}}
  .maphead{{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:.6rem;}}
  .maphead h2{{font-size:1rem;margin:0;}} .legend{{display:flex;gap:1rem;font-size:.8rem;color:var(--muted);margin-left:auto;flex-wrap:wrap;}}
  .legend .k{{display:inline-flex;align-items:center;gap:.35rem;}}
  .swatch{{width:11px;height:11px;border-radius:99px;display:inline-block;box-shadow:0 0 0 2px var(--panel);}}
  .swatch.red{{background:var(--red);}} .swatch.orange{{background:var(--orange);}} .swatch.info{{background:var(--info);}}
  svg.map{{width:100%;height:auto;display:block;border-radius:10px;background:var(--ocean);}}
  .map .land{{fill:var(--land);}} .dot{{stroke:var(--panel);stroke-width:1.5;}}
  .dot.red{{fill:var(--red);}} .dot.orange{{fill:var(--orange);}} .dot.info{{fill:var(--info);}}
  .dot.hide{{display:none;}}
  .bar{{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:0 0 1rem;font-size:.82rem;color:var(--muted);}}
  .bar .ok{{color:var(--ok);}} .bar .down{{color:var(--down);font-weight:700;}}
  .chips{{display:flex;gap:.4rem;flex-wrap:wrap;}} .chip{{border:1px solid var(--line);background:var(--panel);
  color:var(--fg);border-radius:99px;padding:.25rem .8rem;font-size:.8rem;cursor:pointer;}}
  .chip.on{{background:var(--fg);color:var(--bg);border-color:var(--fg);}}
  .toggle{{margin-left:auto;color:var(--fg);cursor:pointer;user-select:none;font-size:.82rem;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.1rem;}}
  .card{{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--muted);
  border-radius:14px;overflow:hidden;display:flex;flex-direction:column;box-shadow:var(--sh);}}
  .card.red{{border-top-color:var(--red);}} .card.orange{{border-top-color:var(--orange);}} .card.info{{border-top-color:var(--info);}}
  .card.hide{{display:none;}}
  .card img,.noimg{{width:100%;height:170px;object-fit:cover;background:#000;display:block;}}
  .noimg{{display:flex;align-items:center;justify-content:center;color:var(--muted);background:var(--line);font-size:.85rem;}}
  .body{{padding:.75rem .95rem 1rem;}} .row{{display:flex;gap:.5rem;align-items:center;margin-bottom:.25rem;}}
  .badge{{font-size:.68rem;font-weight:700;text-transform:uppercase;padding:.1rem .5rem;border-radius:99px;color:#fff;background:var(--muted);}}
  .badge.red{{background:var(--red);}} .badge.orange{{background:var(--orange);}} .badge.info{{background:var(--info);}}
  .src{{color:var(--muted);font-size:.76rem;margin-left:auto;}} h3{{font-size:1rem;margin:.15rem 0 .3rem;}}
  .meta{{color:var(--muted);font-size:.78rem;margin:.15rem 0;}} .assess{{margin:.45rem 0 0;font-size:.9rem;}}
</style></head><body>
  <div class="wrap">
    <h1>🛰️ HADR Situational Dashboard</h1>
    <p class="sub">{len(events)} significant events across {live} live feeds · NASA
      satellite view per event (GIBS/VIIRS ~250m)</p>

    <div class="kpis">
      <div class="kpi"><div class="n">{len(events)}</div><div class="l">Significant events</div></div>
      <div class="kpi red"><div class="n">{reds}</div><div class="l">Severe impact</div></div>
      <div class="kpi orange"><div class="n">{oranges}</div><div class="l">Significant</div></div>
      <div class="kpi"><div class="n">{live}/4</div><div class="l">Feeds live</div></div>
    </div>

    <div class="panel">
      <div class="maphead">
        <h2>Where</h2>
        <div class="legend">
          <span class="k"><span class="swatch red"></span>Severe</span>
          <span class="k"><span class="swatch orange"></span>Significant</span>
          <span class="k"><span class="swatch info"></span>Catalogued</span>
        </div>
      </div>
      <svg class="map" viewBox="0 0 1000 500" role="img" aria-label="World map of current events">
        <path class="land" d="{WORLD_PATH}"/>
        {dots}
      </svg>
    </div>

    <div class="bar"><span>feeds:</span> {status_line}
      <label class="toggle"><input type="checkbox" onchange="fire(this.checked)"> Show NASA fire detections</label>
    </div>
    <div class="bar"><div class="chips">{filters}</div></div>

    <div class="grid">
{chr(10).join(cards)}
    </div>
  </div>
  <script>
    function fire(on){{document.querySelectorAll('img.sat').forEach(i=>i.src=on?i.dataset.fire:i.dataset.plain);}}
    function filt(btn){{
      var f=btn.dataset.f;
      document.querySelectorAll('.chip').forEach(c=>c.classList.toggle('on',c===btn));
      document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide', f!=='All'&&c.dataset.source!==f));
      document.querySelectorAll('.dot').forEach(d=>d.classList.toggle('hide', f!=='All'&&d.dataset.source!==f));
    }}
    document.querySelector('.chip').classList.add('on');
  </script>
</body></html>
"""
    Path(DASHBOARD_PATH).write_text(page, encoding="utf-8")
    return len(page)


def main():
    print("1/4 gathering (GDACS + USGS + EONET + NWS) …")
    events, status = gather()
    print(f"    feeds: {status}")
    if not events:
        print("No located events right now.")
        return 0
    print("2/4 assessing (model) …")
    events = assess(events)
    print("3/4 imagery + 4/4 rendering …")
    size = render(events, status)
    print(f"Done → {DASHBOARD_PATH} ({size // 1024} KB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
