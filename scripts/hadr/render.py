"""Render normalised events into a self-contained HTML events page.

Slice 1 is deliberately rough: one column, alert-colour coded, no history yet.
It shows *all* events (Orange/Red is rare enough that a floor-only page is
usually empty), sorted worst-first, and marks which clear the reporting floor.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from .model import Event, is_reportable

_LEVEL_CLASS = {"Red": "red", "Orange": "orange", "Green": "green"}


def _fmt_time(dt: datetime | None) -> str:
    if dt is None:
        return "time unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _event_row(event: Event) -> str:
    cls = _LEVEL_CLASS.get(event.alert_level, "unknown")
    flag = '<span class="floor">reportable</span>' if is_reportable(event) else ""
    where = html.escape(event.country or "location unknown")
    title = html.escape(event.title)
    link = (
        f'<a href="{html.escape(event.report_url)}">details</a>'
        if event.report_url
        else ""
    )
    return f"""      <li class="event {cls}">
        <span class="pill {cls}">{html.escape(event.alert_level)}</span>
        <span class="type">{html.escape(event.hazard_type)}</span>
        <span class="title">{title}</span>
        {flag}
        <div class="meta">{where} &middot; {_fmt_time(event.event_time)}
          &middot; score {event.alert_score:g} &middot; {link}</div>
      </li>"""


def render_page(events: list[Event], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    ordered = sorted(
        events, key=lambda e: (e.severity_rank, e.alert_score), reverse=True
    )
    reportable = sum(1 for e in events if is_reportable(e))
    rows = "\n".join(_event_row(e) for e in ordered) or (
        '      <li class="empty">No events in the feed.</li>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Monitor — Events (slice 1)</title>
<style>
  :root {{
    --bg:#fff; --fg:#1a1d21; --muted:#5b6470; --line:#e3e6ea; --card:#f6f7f9;
    --red:#c62828; --orange:#d97706; --green:#2e7d32; color-scheme: light dark;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#16181d; --fg:#e8eaed; --muted:#9aa3ad; --line:#2c3038; --card:#1e2127;
      --red:#ef7070; --orange:#f0a24b; --green:#7cc47f;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.6 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  main {{ max-width:44rem; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
  h1 {{ font-size:1.6rem; margin:0 0 .2rem; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:1.8rem; }}
  ul {{ list-style:none; margin:0; padding:0; }}
  .event {{ background:var(--card); border:1px solid var(--line);
    border-left-width:4px; border-radius:8px; padding:.7rem .9rem; margin:.6rem 0; }}
  .event.red    {{ border-left-color:var(--red); }}
  .event.orange {{ border-left-color:var(--orange); }}
  .event.green  {{ border-left-color:var(--green); }}
  .pill {{ font-size:.72rem; font-weight:700; padding:.05rem .5rem; border-radius:99px;
    border:1px solid; text-transform:uppercase; }}
  .pill.red    {{ color:var(--red); border-color:var(--red); }}
  .pill.orange {{ color:var(--orange); border-color:var(--orange); }}
  .pill.green  {{ color:var(--green); border-color:var(--green); }}
  .type {{ color:var(--muted); font-size:.85rem; margin:0 .35rem; }}
  .title {{ font-weight:600; }}
  .floor {{ font-size:.7rem; font-weight:700; color:var(--bg); background:var(--fg);
    padding:.05rem .45rem; border-radius:99px; margin-left:.3rem; }}
  .meta {{ color:var(--muted); font-size:.82rem; margin-top:.3rem; }}
  .meta a {{ color:inherit; }}
  .empty {{ color:var(--muted); padding:1rem 0; }}
</style>
</head>
<body>
<main>
  <h1>HADR Monitor — Events</h1>
  <p class="sub">Slice 1 · GDACS only · {len(events)} events,
    {reportable} clear the Orange/Red reporting floor ·
    generated {_fmt_time(generated_at)}</p>
  <ul>
{rows}
  </ul>
</main>
</body>
</html>
"""
