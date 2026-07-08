"""Tests for the local harness driver.

The harness reuses the (already tested) gate + briefing, then shells out to
OpenCode only when something changed. These tests fake the network and the
opencode subprocess, so nothing external is touched: they pin the gate
decision — run the model on change, skip it when nothing changed unless forced.
"""

import json

import run_local


def _feed(*levels):
    """A minimal GDACS feed with one event per given alert level."""
    feats = []
    for i, lvl in enumerate(levels):
        feats.append({
            "geometry": {"coordinates": [1.0, 2.0]},
            "properties": {
                "eventtype": "EQ", "eventid": 1000 + i, "glide": "",
                "name": f"Quake {i}", "alertlevel": lvl, "alertscore": 1.0,
                "country": "Testland", "fromdate": "2026-07-08T00:00:00",
                "url": {"report": "http://x"},
            },
        })
    return {"type": "FeatureCollection", "features": feats}


def test_runs_model_on_change(tmp_path, monkeypatch):
    monkeypatch.setattr(run_local, "fetch_raw", lambda: _feed("Red", "Orange"))
    monkeypatch.setattr(run_local.shutil, "which", lambda name: "opencode")
    calls = []
    monkeypatch.setattr(run_local.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or _rc0())
    monkeypatch.chdir(tmp_path)

    rc = run_local.main(["--state", str(tmp_path / "s.json")])
    assert rc == 0
    assert len(calls) == 1                       # opencode was invoked
    assert "opencode" in calls[0][0]
    assert json.loads((tmp_path / "briefing.json").read_text())["events"]  # briefing written


def test_skips_model_when_unchanged(tmp_path, monkeypatch):
    feed = _feed("Red", "Orange")
    monkeypatch.setattr(run_local, "fetch_raw", lambda: feed)
    monkeypatch.setattr(run_local.shutil, "which", lambda name: "opencode")
    calls = []
    monkeypatch.setattr(run_local.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or _rc0())
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "s.json"

    run_local.main(["--state", str(state)])      # first run: change -> model runs
    calls.clear()
    rc = run_local.main(["--state", str(state)])  # second run: unchanged
    assert rc == 0
    assert calls == []                           # model was NOT invoked


def test_force_runs_model_even_when_unchanged(tmp_path, monkeypatch):
    feed = _feed("Red")
    monkeypatch.setattr(run_local, "fetch_raw", lambda: feed)
    monkeypatch.setattr(run_local.shutil, "which", lambda name: "opencode")
    calls = []
    monkeypatch.setattr(run_local.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or _rc0())
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "s.json"

    run_local.main(["--state", str(state)])
    calls.clear()
    run_local.main(["--state", str(state), "--force"])
    assert len(calls) == 1                        # --force runs the model anyway


class _rc0:
    returncode = 0
