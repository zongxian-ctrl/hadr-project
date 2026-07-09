"""Level 8 — the capstone: gather every source, resolve duplicates, see the
aftermath, render an interactive UI.

End to end, automatically:
  1. GATHER (deterministic): significant events from GDACS + USGS + EONET + NWS.
  2. RESOLVE (deterministic): merge the SAME real-world event seen by more than
     one feed (e.g. a quake in both USGS and GDACS) into one, by hazard type +
     space + time — the core HADR entity-resolution problem, in miniature.
  3. SEE (deterministic): a NASA image per event (+ a fire-overlay version).
  4. ASSESS (model): one call for a 'who is affected' line per event.
  5. RENDER (deterministic): KPI tiles, a world map with hoverable event dots,
     a legend, source filters, and the card grid.

Design follows the dataviz method: severity = status palette (label, never
colour alone); sources categorical; geography gets a map with a hover layer.

Run:  python harness/level8_capstone.py       →  harness-dashboard.html
"""

import html as html_mod
import json
import math
from datetime import datetime
from pathlib import Path

from llm import call_model
from tools import (
    DASHBOARD_PATH, FIRE_LAYER, TRUECOLOR,
    fetch_eonet, fetch_feed, fetch_nws, fetch_usgs, snapshot_data_uri,
)

# ---- how much to fetch (tune these) -----------------------------------------
MAX_EVENTS = 30           # total events shown after de-duplication; raise for more
USGS_MIN_MAG = 5.0        # earthquakes at/above this magnitude…
USGS_WINDOW = "day"       # …within: "hour" | "day" | "week"  (week = many more)
NWS_MIN_SEV = "Severe"    # "Extreme" | "Severe" | "Moderate" | "Minor" (lower = more)
FEED_CAPS = {"GDACS": 99, "USGS": 6, "EONET": 5, "NWS": 4}   # per-feed maximum
# NOTE: GDACS is fixed to Orange/Red inside fetch_feed (Green is mostly noise);
# broaden EONET by category count via FEED_CAPS["EONET"].
# -----------------------------------------------------------------------------
WORLD_PATH = (Path(__file__).parent / "assets" / "world_path.txt").read_text(encoding="utf-8")
SEV_RANK = {"red": 0, "orange": 1, "info": 2}
GDACS_HAZARD = {"EQ": "earthquake", "TC": "cyclone", "FL": "flood",
                "WF": "wildfire", "VO": "volcano", "DR": "drought"}
MERGE_KM = 200      # events closer than this (same hazard, same ~time) are one
MERGE_DAYS = 3


def _norm_eonet_hazard(cat):
    c = (cat or "").lower()
    for token in ("wildfire", "flood", "volcano", "earthquake", "landslide", "drought"):
        if c.startswith(token):
            return token
    return c or "event"


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
                "hazard": GDACS_HAZARD.get(e.get("type"), (e.get("type") or "").lower()),
                "where": e.get("country"), "lon": c[0], "lat": c[1], "date": e.get("date"),
                "url": e.get("url"), "detail": None}

    def us(e):
        c = e.get("coords") or [None, None]
        mag = e.get("mag") or 0
        depth = e.get("depth")
        return {"source": "USGS", "title": f"M{mag} — {e['place']}", "severity": f"M{mag}",
                "sev_level": "red" if mag >= 6 else "orange", "hazard": "earthquake",
                "where": e.get("place"), "lon": c[0], "lat": c[1], "date": e.get("time"),
                "url": e.get("url"),
                "detail": f"Depth {depth:.0f} km" if depth is not None else None}

    def eo(e):
        c = e.get("coords") or [None, None]
        return {"source": "EONET", "title": e["title"], "severity": e.get("category"),
                "sev_level": "info", "hazard": _norm_eonet_hazard(e.get("category")),
                "where": e.get("category"), "lon": c[0], "lat": c[1], "date": e.get("date"),
                "url": e.get("url"), "detail": None}

    def nw(e):
        return {"source": "NWS", "title": e.get("event"), "severity": e.get("severity"),
                "sev_level": "red" if e.get("severity") == "Extreme" else "orange",
                "hazard": "weather", "where": e.get("area"),
                "lon": e.get("lon"), "lat": e.get("lat"), "date": e.get("date"),
                "url": None, "detail": e.get("headline")}

    add("GDACS", fetch_feed(), gd, FEED_CAPS["GDACS"])
    add("USGS", fetch_usgs(USGS_MIN_MAG, USGS_WINDOW), us, FEED_CAPS["USGS"])
    add("EONET", fetch_eonet(None, 20), eo, FEED_CAPS["EONET"])
    add("NWS", fetch_nws(NWS_MIN_SEV, 20), nw, FEED_CAPS["NWS"])
    return events, status


# ---- entity resolution: merge one real event seen by several feeds -----------

def _haversine_km(a, b):
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, [a["lat"], a["lon"], b["lat"], b["lon"]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "").strip()[:19])
    except Exception:
        return None


def _same_event(a, b):
    if not a["hazard"] or a["hazard"] != b["hazard"]:
        return False
    if _haversine_km(a, b) > MERGE_KM:
        return False
    da, db = _parse_dt(a.get("date")), _parse_dt(b.get("date"))
    if da and db and abs((da - db).days) > MERGE_DAYS:
        return False
    return True


def merge_events(events):
    """Fold duplicate observations of one event into a single record whose
    `sources` lists every feed that saw it. The most-severe observation wins as
    the primary (its title/coords/severity are kept)."""
    merged = []
    for e in sorted(events, key=lambda x: SEV_RANK.get(x["sev_level"], 3)):
        hit = next((m for m in merged if _same_event(e, m)), None)
        if hit:
            if e["source"] not in hit["sources"]:
                hit["sources"].append(e["source"])
        else:
            e = dict(e)
            e["sources"] = [e["source"]]
            merged.append(e)
    return merged


def assess(events):
    listing = "\n".join(f"{i}. {e['title']} ({'+'.join(e['sources'])}, {e.get('where') or ''})"
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
    merged_ct = sum(1 for e in events if len(e["sources"]) > 1)

    dots = []
    for i, e in enumerate(events):
        x, y = _proj(e["lat"], e["lon"])
        srcs = ",".join(e["sources"])
        sub = f"{'+'.join(e['sources'])} · {e.get('severity') or ''} · {(e.get('where') or '')} · {(e.get('date') or '')[:10]}"
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" class="dot {e["sev_level"]}" '
                    f'data-source="{esc(srcs)}" data-title="{esc(e["title"])}" data-sub="{esc(sub)}" '
                    f'onclick="jump({i})"/>')

    cards = []
    for i, e in enumerate(events):
        plain = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "", layers=TRUECOLOR)
        fire = snapshot_data_uri(e["lat"], e["lon"], e.get("date") or "",
                                 layers=f"{TRUECOLOR},{FIRE_LAYER}") or plain
        img = (f'<img class="sat" src="{plain}" data-plain="{plain}" data-fire="{fire}" '
               f'alt="satellite view of {esc(e["title"])}" loading="lazy">' if plain
               else '<div class="noimg">imagery unavailable</div>')
        when = (e.get("date") or "")[:10]
        src_badges = "".join(f'<span class="src">{esc(s)}</span>' for s in e["sources"])
        merged_tag = '<span class="merged">merged</span>' if len(e["sources"]) > 1 else ""
        detail_html = f'<p class="detail">{esc(e["detail"])}</p>' if e.get("detail") else ""
        link_html = (f'<a class="srclink" href="{esc(e["url"])}" target="_blank" rel="noopener">Full record ↗</a>'
                     if e.get("url") else "")
        cards.append(f"""    <article id="ev{i}" class="card {e['sev_level']}" data-source="{esc(','.join(e['sources']))}">
      {img}
      <div class="body">
        <div class="row"><span class="badge {e['sev_level']}">{esc(str(e.get('severity') or ''))}</span>
          {merged_tag}{src_badges}</div>
        <h3>{esc(e['title'])}</h3>
        <p class="meta">{esc(e.get('where') or '')}{' · ' if e.get('where') else ''}{esc(when)}</p>
        <p class="assess">{esc(e.get('assessment') or '')}</p>
        {detail_html}
        {link_html}
      </div>
    </article>""")

    status_line = " · ".join(
        f'<span class="{"down" if status.get(s) == "unreachable" else "ok"}">{s} {status.get(s, "—")}</span>'
        for s in ("GDACS", "USGS", "EONET", "NWS"))
    filters = "".join(f'<button class="chip" data-f="{s}" onclick="filt(this)">{s}</button>'
                      for s in ["All", "GDACS", "USGS", "EONET", "NWS"])
    merged_note = f' · {merged_ct} cross-feed match{"es" if merged_ct != 1 else ""}' if merged_ct else ""

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
  .topnav{{display:flex;align-items:center;gap:1rem;margin-bottom:.15rem;}}
  .about-link{{margin-left:auto;font-size:.85rem;color:var(--info);text-decoration:none;
  border:1px solid var(--line);border-radius:99px;padding:.28rem .8rem;white-space:nowrap;}}
  .about-link:hover{{border-color:var(--info);}}
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
  .map .land{{fill:var(--land);}} .dot{{stroke:var(--panel);stroke-width:1.5;cursor:pointer;transition:r .1s;}}
  .dot:hover{{r:8;}} .dot.red{{fill:var(--red);}} .dot.orange{{fill:var(--orange);}} .dot.info{{fill:var(--info);}}
  .dot.hide{{display:none;}}
  .tip{{position:fixed;display:none;z-index:9;background:var(--panel);color:var(--fg);border:1px solid var(--line);
  box-shadow:var(--sh);border-radius:8px;padding:.45rem .6rem;font-size:.8rem;max-width:240px;pointer-events:none;}}
  .tip b{{display:block;margin-bottom:.1rem;}}
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
  .body{{padding:.75rem .95rem 1rem;}} .row{{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap;margin-bottom:.25rem;}}
  .badge{{font-size:.68rem;font-weight:700;text-transform:uppercase;padding:.1rem .5rem;border-radius:99px;color:#fff;background:var(--muted);}}
  .badge.red{{background:var(--red);}} .badge.orange{{background:var(--orange);}} .badge.info{{background:var(--info);}}
  .merged{{font-size:.62rem;font-weight:700;text-transform:uppercase;padding:.1rem .45rem;border-radius:99px;
  border:1px dashed var(--muted);color:var(--muted);}}
  .src{{color:var(--muted);font-size:.72rem;border:1px solid var(--line);border-radius:99px;padding:.02rem .4rem;}}
  h3{{font-size:1rem;margin:.15rem 0 .3rem;}}
  .meta{{color:var(--muted);font-size:.78rem;margin:.15rem 0;}} .assess{{margin:.45rem 0 0;font-size:.9rem;}}
  .detail{{color:var(--muted);font-size:.8rem;margin:.35rem 0 0;}}
  .srclink{{display:inline-block;margin-top:.5rem;font-size:.8rem;color:var(--info);text-decoration:none;}}
  .srclink:hover{{text-decoration:underline;}}
  .card.flash{{animation:flash 1.2s ease;}}
  @keyframes flash{{0%,100%{{box-shadow:var(--sh);}}25%{{box-shadow:0 0 0 3px var(--info);}}}}
</style></head><body>
  <div class="wrap">
    <div class="topnav">
      <h1>🛰️ HADR Situational Dashboard</h1>
      <a class="about-link" href="index.html">About this tool ↗</a>
    </div>
    <p class="sub">{len(events)} events across {live} live feeds{merged_note} ·
      NASA satellite view per event (GIBS/VIIRS ~250m)</p>

    <div class="kpis">
      <div class="kpi"><div class="n">{len(events)}</div><div class="l">Events</div></div>
      <div class="kpi red"><div class="n">{reds}</div><div class="l">Severe impact</div></div>
      <div class="kpi orange"><div class="n">{oranges}</div><div class="l">Significant</div></div>
      <div class="kpi"><div class="n">{live}/4</div><div class="l">Feeds live</div></div>
    </div>

    <div class="panel">
      <div class="maphead"><h2>Where</h2>
        <div class="legend">
          <span class="k"><span class="swatch red"></span>Severe</span>
          <span class="k"><span class="swatch orange"></span>Significant</span>
          <span class="k"><span class="swatch info"></span>Catalogued</span>
          <span class="k">hover a dot for details</span>
        </div>
      </div>
      <svg class="map" viewBox="0 0 1000 500" role="img" aria-label="World map of current events">
        <path class="land" d="{WORLD_PATH}"/>
        {''.join(dots)}
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
  <div id="tip" class="tip"></div>
  <script>
    function fire(on){{document.querySelectorAll('img.sat').forEach(i=>i.src=on?i.dataset.fire:i.dataset.plain);}}
    function jump(i){{var c=document.getElementById('ev'+i);if(!c)return;
      c.classList.remove('hide');
      c.scrollIntoView({{behavior:'smooth',block:'center'}});
      c.classList.add('flash');setTimeout(function(){{c.classList.remove('flash');}},1200);}}
    function match(el,f){{return f==='All'||el.dataset.source.split(',').indexOf(f)>=0;}}
    function filt(btn){{
      var f=btn.dataset.f;
      document.querySelectorAll('.chip').forEach(c=>c.classList.toggle('on',c===btn));
      document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide',!match(c,f)));
      document.querySelectorAll('.dot').forEach(d=>d.classList.toggle('hide',!match(d,f)));
    }}
    document.querySelector('.chip').classList.add('on');
    var tip=document.getElementById('tip');
    document.querySelectorAll('.dot').forEach(function(d){{
      d.addEventListener('mousemove',function(ev){{
        tip.innerHTML='<b>'+d.dataset.title+'</b>'+d.dataset.sub;
        tip.style.display='block';
        tip.style.left=Math.min(ev.clientX+14,window.innerWidth-250)+'px';
        tip.style.top=(ev.clientY+14)+'px';
      }});
      d.addEventListener('mouseleave',function(){{tip.style.display='none';}});
    }});
  </script>
</body></html>
"""
    Path(DASHBOARD_PATH).write_text(page, encoding="utf-8")
    return len(page)


LANDING_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Monitor — what it is</title>
<style>
  :root{--bg:#eef0f3;--panel:#fff;--fg:#12151a;--muted:#5b6470;--line:#e2e5ea;
  --accent:#2563eb;--sh:0 1px 3px rgba(0,0,0,.08),0 8px 30px rgba(0,0,0,.06);color-scheme:light dark;}
  @media(prefers-color-scheme:dark){:root{--bg:#0c0e12;--panel:#161a20;--fg:#e8eaed;--muted:#9aa3ad;
  --line:#252a32;--accent:#6ea8fe;--sh:0 1px 3px rgba(0,0,0,.4);}}
  *{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.6 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  .wrap{max-width:880px;margin:0 auto;padding:4rem 1.25rem 4rem;}
  .hero{text-align:center;margin-bottom:2.5rem;}
  h1{font-size:2.2rem;letter-spacing:-.02em;margin:0 0 .4rem;}
  .tagline{color:var(--muted);font-size:1.12rem;max-width:52ch;margin:.4rem auto 1.6rem;}
  .cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;
  padding:.7rem 1.4rem;border-radius:99px;box-shadow:var(--sh);}
  .cta:hover{filter:brightness(1.08);}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem;}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:1.2rem 1.3rem;box-shadow:var(--sh);}
  .card h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 .5rem;}
  .card p{margin:0;font-size:.97rem;line-height:1.6;}
  .foot{text-align:center;color:var(--muted);font-size:.82rem;margin-top:2.5rem;}
</style></head><body>
  <div class="wrap">
    <div class="hero">
      <h1>🛰️ HADR Monitor</h1>
      <p class="tagline">Turns scattered public disaster feeds into one clear picture of what matters right now.</p>
      <a class="cta" href="harness-dashboard.html">View the live dashboard →</a>
    </div>
    <div class="grid">
      <div class="card"><h2>What is this?</h2><p>A situational-awareness board for humanitarian &amp; disaster
        response. It pulls live public feeds, removes duplicates, and shows each significant event on a world map
        with a NASA satellite view and a plain-language note on who's affected.</p></div>
      <div class="card"><h2>Why &amp; where it's headed</h2><p>Responders drown in scattered, duplicated alerts.
        This distils the noise into what's significant, where it is, and who it hits. Next: more feeds, sharper
        impact ranking, before/after imagery, and alerts for the most severe events.</p></div>
      <div class="card"><h2>Who it's for</h2><p>Duty officers, humanitarian analysts and responders doing a
        situation scan. It speeds up the first decision of the day — what needs attention now, and where to look
        first (triage &amp; prioritisation).</p></div>
      <div class="card"><h2>What it does <em>not</em> do</h2><p>No forecasting, no tasking or dispatch, no
        building-level damage (imagery is ~250&nbsp;m — smoke, floods, burn scars, not streets). Not real-time to
        the second; severity is a modelled alert level, not verified ground truth. Decision support — a human
        still decides.</p></div>
    </div>
    <p class="foot">Free feeds: GDACS · USGS · NASA EONET · US NWS · imagery NASA GIBS. Decision support, not a decision-maker.</p>
  </div>
</body></html>
"""


def write_landing():
    Path("index.html").write_text(LANDING_HTML, encoding="utf-8")


def main():
    print("1/5 gathering (GDACS + USGS + EONET + NWS) …")
    events, status = gather()
    print(f"    feeds: {status}")
    if not events:
        print("No located events right now.")
        return 0
    print("2/5 resolving duplicates across feeds …")
    events = merge_events(events)
    events.sort(key=lambda e: SEV_RANK.get(e["sev_level"], 3))
    events = events[:MAX_EVENTS]
    merged_ct = sum(1 for e in events if len(e["sources"]) > 1)
    print(f"    {len(events)} unique events ({merged_ct} matched across feeds)")
    print("3/5 assessing (model) …")
    events = assess(events)
    print("4/5 imagery + 5/5 rendering …")
    size = render(events, status)
    write_landing()
    print(f"Done → index.html (landing) + {DASHBOARD_PATH} ({size // 1024} KB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
