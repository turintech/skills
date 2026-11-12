"""Shared helpers for the studio tests: the synthetic snapshots, and drawing a built page in headless Chrome."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_report  # noqa: E402
import collect_discovery  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "synthetic"
CHROME = check_report.find_chrome()


def run_snapshot() -> dict:
    return collect_discovery.build_snapshot(collect_discovery.load_from_dir(str(FIXTURE)), collected_at="2026-01-01T00:00:00Z")


def project_snapshot(n: int = 2) -> dict:
    runs = []
    for i in range(n):
        snap = run_snapshot()
        snap["run"]["id"] = f"run-{i}"
        runs.append(snap)
    return {"schemaVersion": collect_discovery.SCHEMA_VERSION, "kind": "project", "projectId": "proj-1", "runs": runs, "skipped": []}


def with_intervals(snap: dict) -> dict:
    """The run snapshot with falcon intervals on latency, so the forest draws: the first version clear of 0, the rest crossing it."""
    for i, v in enumerate(snap["versions"]):
        st = v["metrics"].get("latency_ms")
        if st and st.get("vsBaseline"):
            pct = st["vsBaseline"]["improvementPct"]
            st["vsBaseline"].update(verdict="better" if i == 0 else "noise", ciLowPct=pct - (5 if i == 0 else pct + 5), ciHighPct=pct + 5, readings=5)
    return snap


def failed_run() -> dict:
    snap = run_snapshot()
    snap["run"].update(id="dead-run", status="failed")
    snap.update(versions=[], metrics=[], bestLines=None)
    return snap


def dump(html: str, dataset: str, session: int = 0, after: str = "", width: int = 1280, more: bool = False) -> str:
    """The rendered DOM of one view, at a window width, with More charts open when asked."""
    start = json.dumps({"dataset": dataset, "session": session, **({"more": True} if more else {})})
    page = html.replace("<!doctype html>\n", f"<!doctype html>\n<script>window.__STUDIO_START={start}</script>", 1) + after
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "view.html"
        path.write_text(page, encoding="utf-8")
        return subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={Path(tmp) / 'profile'}",
                               f"--window-size={width},900", "--virtual-time-budget=8000", "--dump-dom", path.as_uri()],
                              env=check_report.chrome_env(tmp), capture_output=True, text=True, timeout=120, check=False).stdout


def with_data(html: str, change) -> str:
    """The built page with its embedded data changed, escaped as build_studio.py escapes it."""
    match = re.search(r'(<script type="application/json" id="studio-data">)(.*?)(</script>)', html, re.S)
    data = json.loads(match.group(2))
    change(data)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return html[:match.start(2)] + raw + html[match.end(2):]


def late(js: str) -> str:
    """A script that runs after the page has drawn and before the checker's probe reads it."""
    return "<script>setTimeout(function () { " + js + " }, 2000);</script>"


def probed(html: str, dataset: str, js: str, act: str = "", phone: bool = False, **kw) -> dict:
    """Run act after the page draws, then js a second later; js returns a JSON-able value, read back from the DOM.
    phone=True draws the page in a 390px frame, as the checker does, since headless Chrome won't open a window under 500px."""
    target = "(window.parent !== window ? window.parent.document : document).body"
    script = ("<script>setTimeout(function () { " + act + " }, 2500); setTimeout(function () { var out = (function () { " + js
              + " })(); var p = document.createElement('pre'); p.id = 'probe'; p.textContent = JSON.stringify(out); " + target + ".appendChild(p); }, 3500);</script>")
    if phone:
        start = json.dumps({"dataset": dataset, "session": kw.pop("session", 0), **({"more": True} if kw.pop("more", False) else {})})
        inner = html.replace("<!doctype html>\n", f"<!doctype html>\n<script>window.__STUDIO_START={start}</script>", 1) + script
        outer = '<!doctype html><body style="margin:0"><iframe id="f" style="width:390px;height:900px;border:0"></iframe><script>document.getElementById("f").srcdoc = ' + json.dumps(inner).replace("</", "<\\/") + ';</script>'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "phone.html"
            path.write_text(outer, encoding="utf-8")
            out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={Path(tmp) / 'profile'}",
                                  "--window-size=600,900", "--virtual-time-budget=10000", "--dump-dom", path.as_uri()],
                                 env=check_report.chrome_env(tmp), capture_output=True, text=True, timeout=120, check=False).stdout
        found = re.search(r'<pre id="probe">(.*?)</pre>', out, re.S)
        assert found, "the probe did not run"
        return json.loads(found.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
    found = re.search(r'<pre id="probe">(.*?)</pre>', dump(html, dataset, after=script, **kw), re.S)
    assert found, "the probe did not run"
    return json.loads(found.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))


VISIBLE = "var vis = function (t) { return getComputedStyle(t).visibility !== 'hidden' && t.getBoundingClientRect().width > 0; }; var card = function (id) { return document.querySelector('[data-card=\"' + id + '\"]'); }; var texts = function (id) { return [].filter.call(card(id).querySelectorAll('svg text'), vis).map(function (t) { return t.textContent; }); };"


def embedded(html: str) -> dict:
    # Parsed raw, as the browser's JSON.parse sees it.
    match = re.search(r'<script type="application/json" id="studio-data">(.*?)</script>', html, re.S)
    return json.loads(match.group(1))


def low_then_high() -> dict:
    """A real run's shape: an unchanged low-importance target listed before the high-importance one that moved."""
    snap = run_snapshot()
    lat = next(m for m in snap["metrics"] if m["key"] == "latency_ms")
    lat["importance"] = "high"
    snap["metrics"].insert(0, dict(copy.deepcopy(lat), key="db_size_mb", label="db size mb", importance="low", metricId="db-size"))
    snap["baseline"]["metrics"]["db_size_mb"] = copy.deepcopy(snap["baseline"]["metrics"]["latency_ms"])
    for v in snap["versions"]:
        st = v["metrics"].get("latency_ms")
        if st:
            flat = copy.deepcopy(st)
            flat.update(mean=snap["baseline"]["metrics"]["latency_ms"]["mean"], pctBetter=0.0, timesBetter=1.0)
            if flat.get("vsBaseline"):
                flat["vsBaseline"].update(verdict="noise", improvementPct=0.0)
            v["metrics"]["db_size_mb"] = flat
    snap["rankings"]["db_size_mb"] = [dict(r, pctBetter=0.0, timesBetter=1.0) for r in snap["rankings"]["latency_ms"]]
    snap["perMetricWinners"]["db_size_mb"] = copy.deepcopy(snap["perMetricWinners"]["latency_ms"])
    for w in snap["perMetricWinners"]["db_size_mb"].values():
        if isinstance(w, dict):
            w.update(pctBetter=0.0, timesBetter=1.0)
    return snap
