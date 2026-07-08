"""Tests for GDACS fetch resilience.

GDACS is a free public feed with no SLA: it intermittently hangs a connection
(observed ~30s) from datacenter IPs, while a retry succeeds in ~1s. `fetch_raw`
must retry transient failures rather than letting one hang sink the whole run.
These tests use a fake urlopen — never the network.
"""

import pytest

import hadr.gdacs as g


class FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] < 3:            # first two attempts hang/time out
            raise TimeoutError("timed out")
        return FakeResp(b'{"features": []}')

    monkeypatch.setattr(g.urllib.request, "urlopen", flaky_urlopen)
    monkeypatch.setattr(g.time, "sleep", lambda s: None)  # no real backoff wait

    raw = g.fetch_raw(retries=3, backoff=0)
    assert raw == {"features": []}
    assert calls["n"] == 3            # it kept trying until one worked


def test_raises_after_exhausting_retries(monkeypatch):
    def always_timeout(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(g.urllib.request, "urlopen", always_timeout)
    monkeypatch.setattr(g.time, "sleep", lambda s: None)

    with pytest.raises(TimeoutError):
        g.fetch_raw(retries=2, backoff=0)


def test_succeeds_first_try_no_retry(monkeypatch):
    calls = {"n": 0}

    def ok_urlopen(req, timeout):
        calls["n"] += 1
        return FakeResp(b'{"features": [1]}')

    monkeypatch.setattr(g.urllib.request, "urlopen", ok_urlopen)
    raw = g.fetch_raw()
    assert raw == {"features": [1]}
    assert calls["n"] == 1            # no wasted retries on the happy path
