#!/usr/bin/env python3
"""Build the interactive chart studio: one page from one or more collector snapshots, the data inlined. It loads its
pinned chart libraries (React, Recharts, htm) from cdnjs and unpkg, so it needs the network to draw.

Stdlib only. Each --snapshot is a run snapshot (`collect_discovery.py --run-id`) or a project snapshot
(`--project`), whose runs become that dataset's Discovery sessions, oldest first. The page draws only
what the snapshots hold: falcon's verdicts and intervals, never a statistic of its own.

    python3 build_studio.py --snapshot snap.json --output studio.html
    python3 build_studio.py --snapshot project.json --label "Build time" --failed 1:2:3,4 --output studio.html

--failed N:SESSION:VERSIONS marks versions that failed a check of the user's own, outside the snapshot
(for example an output-correctness check), in snapshot N (1-based), session SESSION. They stay drawn,
marked with a cross. Inside a project snapshot, runs with no measured version (a failed run, say) are
left out and named on stderr and on the page, as are the runs the collector skipped, so SESSION counts
the runs that remain, oldest first: the session number the page shows. A run snapshot with no measured version, or a project with none left, is refused.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from collect_discovery import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "chart-studio.html"
# SCHEMA_VERSION is the collector's, so a schema bump moves both.


def short(value: object) -> str:
    return str(value or "")[:8]


def note(line: str) -> None:
    print(f"build_studio.py: {line}", file=sys.stderr)


def measured(snapshot: dict) -> bool:
    """At least one version has a reading on one of the run's target metrics, the ones the page draws. An AI score or a
    harness timing (compile_runtime) does not count: the judge scores code that never ran, and a build can time a run
    whose benchmark failed."""
    keys = {m.get("key") for m in snapshot.get("metrics") or [] if isinstance(m, dict) and m.get("kind") == "target"}
    return any(
        isinstance(stat, dict) and stat.get("mean") is not None
        for v in snapshot.get("versions") or [] if isinstance(v, dict) and isinstance(v.get("metrics"), dict)
        for key, stat in v["metrics"].items()
        if key in keys
    )


def run_name(snapshot: dict) -> str:
    run = snapshot.get("run") or {}
    return f"run {short(run.get('id'))} ({run.get('status') or 'no status'})"


def dataset(snapshot: dict, index: int, label: str | None) -> dict:
    """One picker entry: a run snapshot, or a project snapshot as sessions."""
    if not isinstance(snapshot, dict):
        raise ValueError(f"snapshot {index}: expected a collector snapshot (a JSON object), got {type(snapshot).__name__}")
    if snapshot.get("kind") == "project":
        skipped = snapshot.get("skipped") or []
        if not isinstance(skipped, list) or not all(isinstance(s, dict) for s in skipped):
            raise ValueError(f"snapshot {index}: `skipped` is not a list of JSON objects; collect it with collect_discovery.py --project")
        left_out = []
        for skip in skipped:
            note(f"snapshot {index}: the collector skipped run {short(skip.get('id'))} ({skip.get('status') or 'no status'}): {skip.get('reason') or 'no reason given'}")
            left_out.append({"id": str(skip.get("id") or ""), "reason": f"{skip.get('status') or 'no status'}, {skip.get('reason') or 'no reason given'}"})
        runs = snapshot.get("runs") or []
        if not isinstance(runs, list):
            raise ValueError(f"snapshot {index}: `runs` is not a list; collect it with collect_discovery.py --project")
        for n, r in enumerate(runs, 1):
            run_id = ((r.get("run") or {}).get("id") if isinstance(r, dict) and isinstance(r.get("run"), dict) else None)
            check_run(r, f"{index}, run {n}" + (f" ({short(run_id)})" if run_id else ""))
        kept = [r for r in runs if measured(r)]
        for r in runs:
            if r not in kept:
                note(f"snapshot {index}: left out {run_name(r)}, which has no measured version")
                left_out.append({"id": str((r.get("run") or {}).get("id") or ""), "reason": f"{(r.get('run') or {}).get('status') or 'no status'}, no measured version"})
        runs = kept
        if not runs:
            raise ValueError(f"snapshot {index}: the project snapshot has no run with a measured version to draw")
        extra = {"leftOut": left_out} if left_out else {}  # the page names them too
        if len(runs) == 1:
            return {**dataset(runs[0], index, label), **extra}
        name = label or runs[0].get("run", {}).get("projectName") or "Project " + short(snapshot.get("projectId"))
        return {"id": "p-" + str(snapshot.get("projectId") or index), "label": name, "sessions": runs, **extra}
    check_run(snapshot, index)
    if not measured(snapshot):
        raise ValueError(f"snapshot {index}: {run_name(snapshot)} has no measured version to draw")
    run = snapshot["run"]
    name = label or run.get("projectName") or "Discovery run " + short(run.get("id"))
    return {"id": "r-" + str(run.get("id") or index), "label": name, "snapshot": snapshot}


def check_run(snapshot: object, index: int | str) -> None:
    """The fields the page reads without a guard; anything else it treats as optional."""
    if not isinstance(snapshot, dict):
        raise ValueError(f"snapshot {index}: a run is not a JSON object")
    if snapshot.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"snapshot {index}: schemaVersion is {snapshot.get('schemaVersion')!r}, expected {SCHEMA_VERSION}; re-collect it")
    for key, kind, word in (("run", dict, "a JSON object"), ("metrics", list, "a list"), ("baseline", dict, "a JSON object"),
                            ("versions", list, "a list"), ("perMetricWinners", dict, "a JSON object")):
        if not isinstance(snapshot.get(key), kind):
            raise ValueError(f"snapshot {index}: `{key}` is missing or is not {word}; collect it with collect_discovery.py")
    for key in ("metrics", "versions"):
        if not all(isinstance(item, dict) for item in snapshot[key]):
            raise ValueError(f"snapshot {index}: an item of `{key}` is not a JSON object; collect it with collect_discovery.py")
    for key in ("metrics", "readings"):
        if not isinstance(snapshot["baseline"].get(key), dict):
            raise ValueError(f"snapshot {index}: `baseline.{key}` is missing or is not a JSON object; collect it with collect_discovery.py")
    best = snapshot.get("bestLines")
    if not isinstance(best, (dict, type(None))) or (isinstance(best, dict) and not (
            isinstance(best.get("lede"), str) and isinstance(best.get("label"), str) and isinstance(best.get("notes", {}), dict))):
        raise ValueError(f"snapshot {index}: `bestLines` is not {{label, lede, notes}}; collect it with collect_discovery.py")
    if isinstance(best, dict) and "metric" not in best:
        note(f"snapshot {index}: collected by an older collect_discovery.py (no bestLines.metric); the page picks the lead itself. Collect it again to match today's rules")
    pareto = snapshot.get("pareto")
    if pareto is not None and not (isinstance(pareto, dict) and (pareto.get("axes") is None or (
            isinstance(pareto["axes"], list) and len(pareto["axes"]) >= 2 and all(isinstance(a, dict) and a.get("key") for a in pareto["axes"][:2])))
            and isinstance(pareto.get("points") or [], list)):
        raise ValueError(f"snapshot {index}: `pareto` is not {{axes: [two metrics with a key], points: [...]}}; collect it with collect_discovery.py")
    if not all(isinstance(v.get("metrics", {}), dict) for v in snapshot["versions"]):
        raise ValueError(f"snapshot {index}: a version's `metrics` is not a JSON object; collect it with collect_discovery.py")
    if not all(isinstance(st, (dict, type(None))) for v in snapshot["versions"] for st in (v.get("metrics") or {}).values()):
        raise ValueError(f"snapshot {index}: a version's metric reading is not a JSON object; collect it with collect_discovery.py")


IDENTIFIERS = re.compile(r"^(key|id|sha|metric|reference)$|(Id|Sha|Ids)$")  # fields that name things the page matches on, left as they are


def no_dashes(value: object, field: str = "") -> object:
    """The page uses no en or em dashes: "3\u20135" reads "3 to 5", any other becomes a comma. Text values only: keys,
    ids and metric names stay as they are, so they still match each other."""
    if isinstance(value, str):
        if IDENTIFIERS.search(field):
            return value
        value = re.sub(r"(\w*\d)\s*\u2013\s*(?=[\u2013\u2212-]?\w*\d)", r"\1 to ", value)  # a range, "3\u20135" or "v2\u2013v5", reads "to"
        value = re.sub(r"(^|[\s(])\u2013(?=\d)", "\\1\u2212", value)  # a dash used as a minus keeps its sign
        value = re.sub(r"^\s*[\u2013\u2014]\s*|\s*[\u2013\u2014]\s*$", "", value)  # a dash that opens or closes the text goes
        return re.sub(r"\s*[\u2013\u2014]\s*", ", ", value)
    if isinstance(value, list):
        return [no_dashes(v, field) for v in value]
    if isinstance(value, dict):
        return {k: no_dashes(v, k) for k, v in value.items()}
    return value


def non_finite(value: object, path: str = "") -> str | None:
    """Where the first NaN or Infinity is, as a path like datasets[0].snapshot.versions[1].metrics.latency_ms.std."""
    if isinstance(value, float) and not math.isfinite(value):
        return path
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
    for k, v in items:
        hit = non_finite(v, (f"{path}.{k}" if path else k) if isinstance(k, str) else f"{path}[{k}]")
        if hit:
            return hit
    return None


def parse_failed(specs: list[str], datasets: list[dict]) -> None:
    for spec in specs:
        match = re.fullmatch(r"(\d+):(\d+):(\d+(?:,\d+)*)", spec.strip())
        if not match:
            raise ValueError(f"--failed {spec!r}: expected N:SESSION:VERSIONS, e.g. 1:2:3,4")
        n, session, versions = int(match[1]), int(match[2]), [int(v) for v in match[3].split(",")]
        if not 1 <= n <= len(datasets):
            raise ValueError(f"--failed {spec!r}: there is no snapshot {n}")
        ds = datasets[n - 1]
        # SESSION is the number the page shows ("Discovery session 2"): runs left out of the page are not counted.
        sessions = ds.get("sessions") or [ds["snapshot"]]
        if "snapshot" in ds and session != 1:
            raise ValueError(f"--failed {spec!r}: snapshot {n} is drawn as one run, so its only session is 1")
        if not 1 <= session <= len(sessions):
            raise ValueError(f"--failed {spec!r}: snapshot {n} has {len(sessions)} session(s) on the page")
        known = {v.get("version") for v in sessions[session - 1].get("versions") or []}
        unknown = [v for v in versions if v not in known]
        if unknown:
            raise ValueError(f"--failed {spec!r}: no version {', '.join(map(str, unknown))} in that session")
        run_id = (sessions[session - 1].get("run") or {}).get("id")
        note(f"--failed {spec}: marks v{', v'.join(map(str, sorted(set(versions))))} in Discovery session {session}" + (f" (run {short(run_id)})" if run_id else ""))  # which run, in words
        marks = ds.setdefault("correctness", {})
        marks[str(session)] = sorted(set(marks.get(str(session), [])) | set(versions))  # a repeat adds, never replaces


#: The studio's cards, for --only: one chart drawn exactly as the studio draws it.
CARDS = ("best", "ranked", "forest", "time", "box", "table", "pareto", "ai", "sessions")


def drawable(card: str, ds: dict) -> str | None:
    """Why the first view of `ds` has no `card` to draw, or None. Only sessions, ai and pareto can be missing: this mirrors
    the page's pareto() and hasAIScores(), so --only refuses at build time. The other cards always draw, and say in a
    sentence when they have nothing to show (no intervals yet, no individual iterations)."""
    if card == "sessions":
        if "sessions" not in ds:
            return "one run has no sessions chart; give a project snapshot with two or more measured runs"
        # As the page's SessionsCard: the first session's leading targets (directed, never a control), present in every other.
        first = ds["sessions"][0]
        leads = {m.get("key") for m in first.get("metrics") or [] if isinstance(m, dict) and m.get("kind") == "target"
                 and m.get("role") != "reference" and m.get("higherIsBetter") is not None}
        shared = [k for k in leads if all(any(isinstance(m, dict) and m.get("key") == k for m in s.get("metrics") or []) for s in ds["sessions"][1:])]
        return None if shared else "the sessions share no target metric with a direction, so there is nothing to rank them on"
    snap = ds["sessions"][0] if "sessions" in ds else ds["snapshot"]
    metrics = [m for m in snap.get("metrics") or [] if isinstance(m, dict)]
    means = lambda key: [((v.get("metrics") or {}).get(key) or {}).get("mean") for v in snap.get("versions") or []]
    if card == "ai":
        judged = [m["key"] for m in metrics if m.get("kind") == "quality"]
        return None if any(x is not None for k in judged for x in means(k)) else "no version has an AI Metric score"
    if card == "pareto":
        axes = (snap.get("pareto") or {}).get("axes")
        if axes and not (isinstance((snap.get("pareto") or {}).get("points"), list) and snap["pareto"]["points"]):
            return "the --pareto front has no points"
        with_dir = [m for m in metrics if m.get("higherIsBetter") is not None]
        rank = {"high": 0, "medium": 1, "low": 2}
        targets = sorted((m for m in with_dir if m.get("kind") == "target" and m.get("role") != "reference"), key=lambda m: rank.get(m.get("importance"), 3))
        told = ((snap.get("bestLines") or {}).get("metric"))
        target = next((m["key"] for m in targets if m["key"] == told), targets[0]["key"] if targets else None)  # the page's leadOrder()
        judged = next((m["key"] for m in with_dir if m.get("kind") == "quality"), None)
        keys = [a.get("key") for a in axes[:2]] if axes else [target, judged] if target and judged else []
        flat = lambda vals: len(vals) < 2 or all(x == vals[0] for x in vals)
        if len(keys) < 2 or keys[0] == keys[1] or any(flat([x for x in means(k) if x is not None]) for k in keys):
            return "no two metrics that differ across versions; collect with --pareto X,Y"
    return None


def build(snapshots: list[dict], labels: list[str] | None = None, failed: list[str] | None = None, title: str = "Discovery chart studio",
          only: str | None = None) -> str:
    labels = labels or []
    if only is not None and only not in CARDS:
        raise ValueError(f"--only must be one of {', '.join(CARDS)}, not {only!r}")
    if not snapshots:
        raise ValueError("give at least one --snapshot")
    if len(labels) > len(snapshots):
        raise ValueError("more --label values than --snapshot files")
    datasets = [dataset(s, i + 1, labels[i] if i < len(labels) else None) for i, s in enumerate(snapshots)]
    seen: dict[str, int] = {}
    for ds in datasets:  # the same run twice still gets two picker entries
        seen[ds["id"]] = seen.get(ds["id"], 0) + 1
        if seen[ds["id"]] > 1:
            ds["id"] += f"-{seen[ds['id']]}"
    parse_failed(failed or [], datasets)
    # A one-card page draws snapshot 1, and of a project its first session (the sessions card draws them all).
    marked = [tuple(int(x) for x in m.groups()) for m in (re.fullmatch(r"\s*(\d+):(\d+):.*", s) for s in failed or []) if m]
    if only is not None and any(n != 1 for n, _ in marked):
        raise ValueError(f"--only {only} draws snapshot 1 only, so --failed can mark only snapshot 1")
    if only not in (None, "sessions") and "sessions" in datasets[0]:
        if any(s != 1 for _, s in marked):
            raise ValueError(f"--only {only} draws Discovery session 1 of the project only, so --failed can mark only session 1")
        note(f"--only {only}: draws Discovery session 1 of {len(datasets[0]['sessions'])}; the sessions card shows them all")
    if only is not None and len(datasets) > 1:  # a one-card page draws the first snapshot only, so it carries no other
        note(f"--only {only}: draws snapshot 1 only; the other {len(datasets) - 1} are left out of the page")
        datasets = datasets[:1]
    if only is not None and (why := drawable(only, datasets[0])):
        raise ValueError(f"--only {only}: {why}")
    payload = no_dashes({"datasets": datasets, **({"only": only} if only else {})})
    # "<" as \u003c, still valid JSON, so data can never close or comment out the script element it sits in.
    try:  # the browser's JSON.parse has no NaN or Infinity, so a page holding one would not load
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    except ValueError:
        raise ValueError(f"the snapshot's {non_finite(payload)} is NaN or Infinity, which the page cannot read; collect it again with this "
                         "collect_discovery.py, which writes them as null") from None
    html = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (("__TITLE__", str(no_dashes(title)).replace("&", "&amp;").replace("<", "&lt;")), ("__STUDIO_DATA__", data)):
        if html.count(key) != 1:
            raise ValueError(f"template placeholder {key} must appear exactly once")
        html = html.replace(key, value)
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--snapshot", action="append", required=True, help="Collector snapshot JSON (run or project); repeat for several")
    parser.add_argument("--label", action="append", help="Picker name for the snapshot in the same position; default the project name")
    parser.add_argument("--failed", action="append", help="N:SESSION:VERSIONS that failed the user's own check, e.g. 1:2:3,4")
    parser.add_argument("--title", default="Discovery chart studio", help="Browser tab title")
    parser.add_argument("--only", choices=CARDS, help="Draw this one chart, as the studio draws it, with no other cards and no switcher but Theme")
    parser.add_argument("--output", required=True, help="Where to write the HTML")
    args = parser.parse_args(argv)
    try:
        snapshots = []
        for path in args.snapshot:
            try:
                snapshots.append(json.loads(Path(path).read_text(encoding="utf-8")))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path} is not JSON ({error}); give a collector snapshot") from None
            except UnicodeDecodeError as error:
                raise ValueError(f"{path} is not UTF-8 text ({error}); give a collector snapshot") from None
        html = build(snapshots, args.label, args.failed, args.title, args.only)
        Path(args.output).write_text(html, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"build_studio.py: {error}", file=sys.stderr)
        return 2
    print(f"wrote {args.output} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
