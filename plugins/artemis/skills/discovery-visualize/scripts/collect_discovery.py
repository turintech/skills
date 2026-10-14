#!/usr/bin/env python3
"""Collect a normalized Artemis discovery snapshot from the CLI or fixture files.

Stdlib only. Agents run this, then render the JSON with the host-specific adapter.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 2

HARNESS_METRICS = frozenset(
    {
        "compile_runtime",
        "compile_cpu",
        "compile_memory",
        "unit_test_runtime",
        "unit_test_cpu",
        "unit_test_memory",
        "benchmark_runtime",
        "benchmark_cpu",
        "benchmark_memory",
    }
)

COMMANDS = (
    "artemis --output-format json discovery get <run-id>",
    "artemis --output-format json discovery versions list <run-id> --all",
    "artemis --output-format json discovery metrics <run-id> --all --stats",
    "artemis --output-format json discovery metrics <run-id> --all",
    "artemis --output-format json discovery experiments list <run-id> --all",
    "artemis --output-format json discovery compare <run-id>",
    "artemis --output-format json chat messages <chat-id>",
    "artemis --output-format json project list --all",
)

# Verdict words falcon returns for a metric and for a version overall.
VERDICTS = ("better", "worse", "noise", "pending")


def extract_json(text: str) -> Any:
    """Parse the first JSON value, ignoring logger text printed before it."""
    if text is None:
        raise ValueError("CLI produced no stdout")
    for index, char in enumerate(text):
        if char in "{[":
            try:
                obj, _end = json.JSONDecoder().raw_decode(text[index:])
            except json.JSONDecodeError:
                continue  # a bracket inside logger text, not the payload
            return obj
    raise ValueError("no JSON object or array in CLI output")


def as_docs(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        docs = payload.get("docs")
        if isinstance(docs, list):
            return [item for item in docs if isinstance(item, dict)]
        return [payload]
    raise ValueError(f"unexpected payload type: {type(payload).__name__}")


def infer_base_url(status: Any | None = None, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.rstrip("/")
    if not isinstance(status, dict):
        return None
    for service in status.get("services") or []:
        url = (service or {}).get("url")
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def times_better(improvement_pct: float | None, higher_is_better: bool | None) -> float | None:
    """falcon's improvement as a ratio, so 2.0 reads as "2x faster" in either direction."""
    if improvement_pct is None or higher_is_better is None:
        return None
    if higher_is_better:
        ratio = 1.0 + improvement_pct / 100.0
    else:
        remaining = 1.0 - improvement_pct / 100.0
        ratio = 1.0 / remaining if remaining > 0 else None
    return ratio if ratio and ratio > 0 else None


# The runner's own timings of each command: "compile_runtime", "Benchmark_cpu", "command 2_memory".
HARNESS_PATTERN = re.compile(r"^(compile|unit_test|test|benchmark|setup|teardown|command \d+)_(runtime|cpu|memory)$", re.I)

# A metric measured beside the target in the same benchmark process, used as a control for machine drift.
REFERENCE_TOKENS = ("cublas", "cudnn", "torch", "pytorch", "numpy", "mkl", "eigen", "openblas", "reference", "ref", "baseline_impl")

# Units recognised from a metric's name when the platform stores none.
UNIT_SUFFIXES = (
    ("tflops", "TFLOPS"), ("gflops", "GFLOPS"), ("fps", "fps"), ("tokens_per_s", "tokens/s"), ("tok_s", "tokens/s"),
    ("ms", "ms"), ("us", "\u00b5s"), ("ns", "ns"), ("seconds", "s"), ("runtime", "s"), ("mb", "MB"), ("gb", "GB"), ("memory", "bytes"),
)


def infer_unit(name: str) -> str | None:
    tail = re.split(r"[_\s]", name.lower())[-1]
    for suffix, unit in UNIT_SUFFIXES:
        if tail == suffix or name.lower().endswith("_" + suffix):
            return unit
    return None


def find_references(names: list[str]) -> list[dict[str, str]]:
    """Pair a target with a reference whose name differs only by a reference token, e.g. X_triton_ms and X_cublas_ms."""
    pairs = []
    lowered = {name.lower(): name for name in names}
    for name in names:
        parts = re.split(r"(_)", name)
        for i, part in enumerate(parts):
            if part.lower() in REFERENCE_TOKENS:
                continue
            for token in REFERENCE_TOKENS:
                candidate = "".join(parts[:i] + [token] + parts[i + 1:])
                if candidate.lower() in lowered and lowered[candidate.lower()] != name:
                    pair = {"target": name, "reference": lowered[candidate.lower()]}
                    if pair not in pairs:
                        pairs.append(pair)
    return pairs


def classify_kind(name: str, source: str | None) -> str:
    if name in HARNESS_METRICS or HARNESS_PATTERN.match(name):
        return "harness"
    if source == "agent":
        return "quality"
    return "target"


def metric_label(name: str) -> str:
    return name.replace("_", " ")


def load_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def first_existing(directory: str, names: tuple[str, ...]) -> str:
    for name in names:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(f"none of {names} found in {directory}")


def load_from_dir(directory: str) -> dict[str, Any]:
    run = extract_json(load_text(os.path.join(directory, "run.json")))
    versions = extract_json(load_text(first_existing(directory, ("versions.json",))))
    metrics = extract_json(load_text(first_existing(directory, ("metrics.json", "stats.json"))))
    experiments = extract_json(load_text(os.path.join(directory, "experiments.json")))
    observations_path = os.path.join(directory, "observations.json")
    observations = extract_json(load_text(observations_path)) if os.path.isfile(observations_path) else None
    comparison_path = os.path.join(directory, "comparison.json")
    if not os.path.isfile(comparison_path):
        raise FileNotFoundError(
            f"no comparison.json in {directory}: save `artemis --output-format json discovery compare <run-id>` there, "
            "since the verdicts and changes come from it"
        )
    comparison = extract_json(load_text(comparison_path))
    chat_path = os.path.join(directory, "chat.json")
    chat = extract_json(load_text(chat_path)) if os.path.isfile(chat_path) else None
    return {
        "run": run,
        "versions": versions,
        "metrics": metrics,
        "observations": observations,
        "experiments": experiments,
        "comparison": comparison,
        "chat": chat,
    }


def run_artemis(args: list[str], cli: str = "artemis", config: str | None = None) -> str:
    completed = subprocess.run(
        [cli, *(["--config", config] if config else []), "--output-format", "json", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"artemis {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed.stdout


def list_project_runs(project_id: str, cli: str = "artemis", config: str | None = None) -> list[dict[str, Any]]:
    return as_docs(extract_json(run_artemis(["discovery", "list", "--project", project_id, "--all"], cli, config)))


def project_name(project_id: str | None, cli: str = "artemis", config: str | None = None, cache: dict[str, str | None] | None = None) -> str | None:
    """A project's name from `project get` (CLI 1.1.16+), else from `project list` on older CLIs; None if neither works."""
    if not project_id:
        return None
    if cache is not None and project_id in cache:
        return cache[project_id]
    name = None
    try:
        doc = extract_json(run_artemis(["project", "get", project_id], cli, config))
        name = doc.get("name") if isinstance(doc, dict) and doc.get("id") == project_id else None
    except (RuntimeError, ValueError):
        pass
    if not name:
        try:
            name = next((p.get("name") for p in as_docs(extract_json(run_artemis(["project", "list", "--all"], cli, config))) if p.get("id") == project_id), None)
        except (RuntimeError, ValueError):
            name = None
    if cache is not None:
        cache[project_id] = name
    return name


UPGRADE_HINT = "artemis discovery compare needs artemis CLI 1.1.14 or newer: follow cli-setup to upgrade"


def compare_available(cli: str = "artemis", config: str | None = None) -> bool:
    """Whether this CLI has `discovery compare`. CLIs before 1.1.14 print the parent's help (and exit 0) instead."""
    completed = subprocess.run(
        [cli, *(["--config", config] if config else []), "discovery", "compare", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    return "artemis discovery compare" in (completed.stdout or "")


def fetch_comparison(run_id: str, cli: str = "artemis", config: str | None = None) -> Any:
    """Falcon's verdicts from `discovery compare`. A CLI too old to have it gets the upgrade hint; other errors pass through."""
    try:
        return extract_json(run_artemis(["discovery", "compare", run_id], cli, config))
    except (RuntimeError, ValueError) as error:
        if not compare_available(cli, config):
            raise RuntimeError(UPGRADE_HINT) from error
        raise RuntimeError(f"artemis discovery compare failed: {error}") from error


def fetch_chat(chat_id: str | None, cli: str = "artemis", config: str | None = None) -> Any:
    """The run's chat log, where each steer is a user message. None when the run has no chat or it cannot be read."""
    if not chat_id:
        return None
    try:
        return extract_json(run_artemis(["chat", "messages", chat_id], cli, config))
    except (RuntimeError, ValueError):
        return None


def fetch_cli(run_id: str, cli: str = "artemis", config: str | None = None, names: dict[str, str | None] | None = None) -> dict[str, Any]:
    call = lambda *args: extract_json(run_artemis(list(args), cli, config))
    run = call("discovery", "get", run_id)
    record = (run.get("docs") or [run])[0] if isinstance(run, dict) else {}
    project_id = record.get("projectId")
    return {
        "run": run,
        "versions": call("discovery", "versions", "list", run_id, "--all"),
        "metrics": call("discovery", "metrics", run_id, "--all", "--stats"),
        "observations": call("discovery", "metrics", run_id, "--all"),
        "experiments": call("discovery", "experiments", "list", run_id, "--all"),
        "comparison": fetch_comparison(run_id, cli, config),
        "status": call("status"),
        "projectName": project_name(project_id, cli, config, names),
        "chat": fetch_chat(record.get("chatId"), cli, config),
    }


def _stat_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "mean": row.get("mean"),
        "min": row.get("min"),
        "max": row.get("max"),
        "count": row.get("count"),
    }
    for optional in ("std", "ste", "improvement"):
        if optional in row:
            payload[optional] = row[optional]
    return payload


def falcon_stats(compared: dict[str, Any] | None) -> dict[str, Any]:
    """falcon's summary of one metric's readings, which `discovery compare` carries from CLI 1.1.17; {} on older CLIs."""
    if not compared or compared.get("mean") is None:
        return {}
    stats = {"mean": compared["mean"], "min": compared.get("min"), "max": compared.get("max"), "count": compared.get("readings")}
    for optional in ("std", "ste"):
        if compared.get(optional) is not None:
            stats[optional] = compared[optional]
    return stats


def use_falcon_stats(stat: dict[str, Any], compared: dict[str, Any] | None) -> None:
    """Swap the CLI's summary for falcon's when compare carries one, std and ste included, so a row has one source."""
    falcon = falcon_stats(compared)
    if falcon:
        stat.pop("std", None)
        stat.pop("ste", None)
        stat.update(falcon)


def quartiles(values: list[float]) -> dict[str, float]:
    """First quartile, median and third quartile by linear interpolation (the usual "type 7")."""
    ordered = sorted(values)

    def at(p: float) -> float:
        index = (len(ordered) - 1) * p
        low, high = int(index), min(int(index) + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (index - low)

    return {"q1": at(0.25), "median": at(0.5), "q3": at(0.75)}


def falcon_vs_baseline(compared: dict[str, Any] | None) -> dict[str, Any] | None:
    """falcon's comparison of one metric on one version against the run's baseline, as `discovery compare` returns it."""
    if not compared or compared.get("verdict") is None:
        return None
    return {
        "source": "falcon",
        "verdict": compared.get("verdict"),
        "improvementPct": compared.get("improvementPct"),
        "ciLowPct": compared.get("improvementLowPct"),
        "ciHighPct": compared.get("improvementHighPct"),
        "readings": compared.get("readings"),
        "recommendedReadings": compared.get("recommendedReadings"),
        "recommendedReadingsReason": compared.get("recommendedReadingsReason"),
        "spreadPct": compared.get("spreadPct"),
    }


def index_comparison(comparison: Any) -> tuple[dict[str, dict[str, Any]], dict[Any, dict[str, Any]], dict[str, Any] | None]:
    """Metric definitions by name, compared rows by version number or sha, and the baseline row."""
    if isinstance(comparison, dict) and isinstance(comparison.get("docs"), list) and comparison["docs"]:
        comparison = comparison["docs"][0]
    if not isinstance(comparison, dict):
        return {}, {}, None
    metrics = {m["name"]: m for m in comparison.get("metrics") or [] if isinstance(m, dict) and m.get("name")}
    rows: dict[Any, dict[str, Any]] = {}
    baseline = None
    for row in comparison.get("versions") or []:
        if not isinstance(row, dict):
            continue
        if row.get("isBaseline"):
            baseline = row
            continue
        if row.get("versionNumber") is not None:
            rows[row["versionNumber"]] = row
        if row.get("sha"):
            rows[row["sha"]] = row
    return metrics, rows, baseline


def _is_better(value: float, incumbent: float, higher_is_better: bool) -> bool:
    return value > incumbent if higher_is_better else value < incumbent


def _eligible(version: dict[str, Any]) -> bool:
    return (
        version.get("lifecycle") == "completed"
        and version.get("executionStatus") == "success"
        and version.get("experimentStatus") != "refuted"
    )


def web_ui_best(versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The version the Web UI badges Best: the highest Composite score among versions that scored, have a sha and
    did not fail, the earlier one on a tie, and none unless that score is above 0 (better than the baseline)."""
    best = None
    for version in versions:  # in version order, so a tie keeps the earlier version
        if version.get("fitness") is None or not version.get("versionSha"):
            continue
        if version.get("displayStatus") in ("generation_failed", "execution_failed", "scoring_failed"):
            continue
        if best is None or version["fitness"] > best["fitness"]:
            best = version
    if best is None or best["fitness"] <= 0:
        return None
    return {"version": best["version"], "label": best["label"], "fitness": best["fitness"]}


# Units that say which way a metric improves. Only the unit the platform stores counts, never the name or a
# unit guessed from it, and anything else stays silent: a wrong hint is worse than none. The flag only asks the
# user to check; the direction itself always comes from the platform.
_HIGHER_UNITS = {"fps", "ops/s", "req/s", "tokens/s", "items/s", "/s"}
_LOWER_UNITS = {"s", "ms", "us", "\u00b5s", "ns", "sec", "secs", "second", "seconds"}


def direction_checks(metric_defs: dict[str, dict[str, Any]]) -> list[str]:
    """A plain line for each measured metric whose stored direction contradicts its platform unit."""
    lines = []
    for name, definition in metric_defs.items():
        higher = definition.get("higherIsBetter")
        unit = (definition.get("platformUnit") or "").strip().lower()
        if higher is None or definition["kind"] == "quality" or not unit:
            continue
        if (unit in _HIGHER_UNITS or unit.endswith("/s")) and not higher:
            lines.append(f"{name} is set as lower-is-better on this project; check Settings > Metrics.")
        elif unit in _LOWER_UNITS and higher:
            lines.append(f"{name} is set as higher-is-better on this project; check Settings > Metrics.")
    return lines


def _pct(value: float) -> str:
    """A change as the report kit prints it: a sign (a true minus for a fall) and one decimal."""
    return ("+" if value >= 0 else "\u2212") + f"{abs(value):.1f}%"


def best_lines(
    metric_defs: dict[str, dict[str, Any]],
    versions: list[dict[str, Any]],
    winners: dict[str, dict[str, Any]],
    ui_best: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """The sentences every report and chat answer carries verbatim: which version leads and why, and each
    measured metric whose own best is another version. None when no target metric has a best version."""
    key = next((n for n, d in metric_defs.items() if d["kind"] == "target" and d.get("role") != "reference"), None)
    if key is None:
        return None
    by_number = {v["version"]: v for v in versions}
    ui_stat = (by_number.get(ui_best["version"], {}).get("metrics") or {}).get(key) if ui_best else None
    by_composite = bool(ui_stat and ui_stat.get("pctBetter") is not None)
    raw = (winners.get(key) or {}).get("raw")
    lead = by_number.get(ui_best["version"]) if by_composite else (by_number.get(raw["version"]) if raw else None)
    if lead is None:
        return None
    if by_composite:
        lede = f"{lead['label']} is the Web UI\u2019s Best: the highest Composite score, the platform\u2019s roll-up of the metrics by importance."
    elif ui_best:
        lede = (f"The Web UI\u2019s Best is {ui_best['label']}, by Composite score, but Artemis has no change on {key} for it, "
                f"so this page leads with the best version on {key}.")
    else:
        lede = (f"The Web UI shows no Best, as no version\u2019s Composite score is above the baseline, "
                f"so this page leads with the best version on {key}.")
    elsewhere, notes = [], {}
    for name, definition in metric_defs.items():
        if definition.get("role") == "reference":
            continue
        own = (winners.get(name) or {}).get("raw")
        stat = (lead.get("metrics") or {}).get(name) or {}
        if stat.get("mean") is None:
            # Only when another version has the reading; with none, the page has no panel to put the note on.
            if own:
                notes[name] = f"{lead['label']} has no reading on {name}; {own['label']} is best on it"
            continue
        if definition["kind"] == "quality" or not own or own["version"] == lead["version"]:
            continue
        if stat.get("pctBetter") is not None and not own["pctBetter"] > stat["pctBetter"]:
            continue
        elsewhere.append(f"{own['label']} on {name} ({_pct(own['pctBetter'])})")
        notes[name] = f"{own['label']} is best on {name}"
    if elsewhere:
        lede += " Best on a single metric instead: " + "; ".join(elsewhere) + "."
    for line in direction_checks(metric_defs):
        lede += " " + line
    return {"version": lead["version"], "label": lead["label"], "byComposite": by_composite, "lede": lede, "notes": notes}


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def steering_points(chat: Any, versions: list[dict[str, Any]]) -> dict[str, Any]:
    """Each steer on the run, from its chat log: every user message after the first (the task) that brings new
    guidance, placed before the first version made after it. A continue without guidance resends the task, so it
    is not a steer."""
    if chat is None:
        return {"points": [], "source": None, "reason": "the run's chat could not be read, so its steers are unknown"}
    events = chat if isinstance(chat, list) else as_docs(chat)
    messages = []
    for event in events:
        payload = event.get("payload") if isinstance(event, dict) else None
        if event.get("type") != "user" or not isinstance(payload, dict):
            continue
        text = (payload.get("message") or "").strip()
        at = _instant(event.get("timestamp") or event.get("createdAt"))
        if text and at:
            messages.append((at, text))
    messages.sort(key=lambda item: item[0])
    points = []
    task = messages[0][1] if messages else None
    made = [(v, _instant(v.get("createdAt"))) for v in versions]
    for at, text in messages[1:]:
        # A resent task is a continue without guidance; a "/" command such as /compact is not guidance either.
        if text == task or text.startswith("/"):
            continue
        after = [v for v, created in made if created and created >= at]
        first = min(after, key=lambda v: v.get("version") or 0) if after else None
        points.append(
            {
                "at": at.isoformat().replace("+00:00", "Z"),
                "guidance": text,
                "firstVersion": first["version"] if first else None,
                "firstLabel": first["label"] if first else None,
            }
        )
    return {"points": points, "source": "artemis chat messages <chat-id>", "reason": None}


def pareto_front(
    versions: list[dict[str, Any]],
    axes: list[str],
    metric_defs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for version in versions:
        values: dict[str, float] = {}
        complete = True
        for axis in axes:
            stat = (version.get("metrics") or {}).get(axis) or {}
            mean = stat.get("mean")
            if mean is None:
                complete = False
                break
            values[axis] = mean
        if not complete:
            continue
        points.append(
            {
                "version": version["version"],
                "label": version["label"],
                "values": values,
                "eligible": version.get("eligible"),
            }
        )

    front: list[dict[str, Any]] = []
    for candidate in points:
        dominated = False
        for other in points:
            if other is candidate:
                continue
            better_or_equal = True
            strictly_better = False
            for axis in axes:
                higher = bool(metric_defs[axis]["higherIsBetter"])
                cand = candidate["values"][axis]
                alt = other["values"][axis]
                if higher:
                    if alt < cand:
                        better_or_equal = False
                        break
                    if alt > cand:
                        strictly_better = True
                else:
                    if alt > cand:
                        better_or_equal = False
                        break
                    if alt < cand:
                        strictly_better = True
            if better_or_equal and strictly_better:
                dominated = True
                break
        front.append({**candidate, "dominated": dominated})
    return front


def build_snapshot(
    payloads: dict[str, Any],
    *,
    collected_at: str,
    base_url: str | None = None,
    pareto_axes: list[str] | None = None,
) -> dict[str, Any]:
    run = payloads["run"]
    if isinstance(run, dict) and isinstance(run.get("docs"), list) and run["docs"]:
        run = run["docs"][0]
    if not isinstance(run, dict) or not run.get("id"):
        raise ValueError("run record is missing an id")

    versions_raw = as_docs(payloads["versions"])
    stats_raw = as_docs(payloads["metrics"])
    experiments_raw = as_docs(payloads["experiments"])

    base_url = infer_base_url(payloads.get("status"), base_url)
    project_id = run.get("projectId")
    run_id = run["id"]
    # Run paths differ between deployments; the project page is the stable link.
    project_url = f"{base_url}/projects/{project_id}" if base_url and project_id else None
    web_url = f"{project_url}/discover/{run_id}" if project_url else None

    experiments_by_id = {item["id"]: item for item in experiments_raw if item.get("id")}
    compared_metrics, compared_rows, compared_baseline = index_comparison(payloads.get("comparison"))
    stats_from_falcon = any(
        falcon_stats(m)
        for row in [compared_baseline or {}, *compared_rows.values()]
        for m in row.get("metrics") or []
        if isinstance(m, dict)
    )

    # Individual measurements, and the direction the platform stores with each one.
    runs_by_group: dict[str, dict[str, list[dict[str, Any]]]] = {}
    direction_by_name: dict[str, bool] = {}
    unit_by_name: dict[str, str] = {}
    for row in as_docs(payloads.get("observations")) if payloads.get("observations") is not None else []:
        group_id = row.get("observationGroupId")
        name = row.get("metricName")
        if not group_id or not name or row.get("value") is None:
            continue
        runs_by_group.setdefault(group_id, {}).setdefault(name, []).append(
            {"value": row["value"], "createdAt": row.get("createdAt")}
        )
        if row.get("higherIsBetter") is not None:
            direction_by_name[name] = bool(row["higherIsBetter"])
        if row.get("unit"):
            unit_by_name[name] = row["unit"]
    for metrics in runs_by_group.values():
        for rows in metrics.values():
            rows.sort(key=lambda item: item.get("createdAt") or "")

    stats_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    names_by_id: dict[str, str] = {}
    for row in stats_raw:
        group_id = row.get("observationGroupId")
        metric_id = row.get("metricId")
        name = row.get("metricName")
        if not group_id or not name:
            continue
        names_by_id[metric_id] = name
        payload = _stat_payload(row)
        runs = runs_by_group.get(group_id, {}).get(name)
        if runs:
            payload["runs"] = [item["value"] for item in runs]
            payload.update(quartiles(payload["runs"]))
        stats_by_group.setdefault(group_id, {})[name] = payload

    schema_by_id = {item.get("metricId"): item for item in (run.get("metricsSchema") or []) if item.get("metricId")}
    metric_defs: dict[str, dict[str, Any]] = {}
    for metric_id, name in names_by_id.items():
        schema = schema_by_id.get(metric_id) or {}
        source = schema.get("source")
        compared = compared_metrics.get(name) or {}
        # Direction only from the platform: falcon's comparison, the run's schema, then the stored measurements.
        if "higherIsBetter" in compared:
            higher: bool | None = bool(compared["higherIsBetter"])
        elif "higherIsBetter" in schema:
            higher = bool(schema["higherIsBetter"])
        elif name in direction_by_name:
            higher = direction_by_name[name]
        else:
            higher = None
        metric_defs[name] = {
            "key": name,
            "metricId": metric_id,
            "label": metric_label(name),
            "source": source,
            "higherIsBetter": higher,
            "importance": schema.get("importance"),
            "kind": classify_kind(name, source),
            "unit": compared.get("unit") or unit_by_name.get(name) or infer_unit(name),
            "platformUnit": compared.get("unit") or unit_by_name.get(name),
            "description": schema.get("description"),
        }

    # Controls measured beside a target: both worker metrics, same direction.
    reference_pairs = [
        pair for pair in find_references([n for n, d in metric_defs.items() if d["kind"] == "target"])
        if metric_defs[pair["target"]]["higherIsBetter"] is not None
        and metric_defs[pair["target"]]["higherIsBetter"] == metric_defs[pair["reference"]]["higherIsBetter"]
    ]
    for pair in reference_pairs:
        metric_defs[pair["reference"]]["role"] = "reference"
        metric_defs[pair["target"]]["reference"] = pair["reference"]

    def add_reference_ratios(metrics: dict[str, dict[str, Any]]) -> None:
        for pair in reference_pairs:
            target, reference = metrics.get(pair["target"]), metrics.get(pair["reference"])
            if not target or not reference or not target.get("mean") or not reference.get("mean"):
                continue
            higher = metric_defs[pair["target"]]["higherIsBetter"]
            ratio = target["mean"] / reference["mean"] if higher else reference["mean"] / target["mean"]
            target["vsReference"] = {"reference": pair["reference"], "ratio": ratio}

    baseline_group = run.get("baselineGroupId")
    baseline_stats = stats_by_group.get(baseline_group or "", {})
    falcon_baseline = {m.get("name"): m for m in (compared_baseline or {}).get("metrics") or [] if isinstance(m, dict)}
    for name, stat in baseline_stats.items():
        use_falcon_stats(stat, falcon_baseline.get(name))
    add_reference_ratios(baseline_stats)

    versions: list[dict[str, Any]] = []
    for item in sorted(versions_raw, key=lambda row: (row.get("versionNumber") is None, row.get("versionNumber") or 0)):
        number = item.get("versionNumber")
        group_id = item.get("observationGroupId")
        experiment = experiments_by_id.get(item.get("experimentId") or "") or {}
        raw_metrics = stats_by_group.get(group_id or "", {})
        compared_row = compared_rows.get(number) or compared_rows.get(item.get("versionSha")) or {}
        compared_by_name = {m.get("name"): m for m in compared_row.get("metrics") or [] if isinstance(m, dict)}
        joined: dict[str, Any] = {}
        for name, stat in raw_metrics.items():
            compared = compared_by_name.get(name) or {}
            payload = dict(stat)
            use_falcon_stats(payload, compared)
            payload["pctBetter"] = compared.get("improvementPct")
            payload["timesBetter"] = times_better(compared.get("improvementPct"), (metric_defs.get(name) or {}).get("higherIsBetter"))
            payload["vsBaseline"] = falcon_vs_baseline(compared)
            joined[name] = payload
        add_reference_ratios(joined)
        record = {
            "label": f"v{number}" if number is not None else item.get("id"),
            "version": number,
            "id": item.get("id"),
            "lifecycle": item.get("lifecycle"),
            "executionStatus": item.get("executionStatus"),
            "displayStatus": item.get("displayStatus"),
            "fitness": item.get("fitnessScore"),
            "changesetId": item.get("changesetId"),
            "versionSha": item.get("versionSha"),
            "observationGroupId": group_id,
            "experimentId": item.get("experimentId"),
            "experimentTitle": experiment.get("title"),
            "experimentStatus": experiment.get("status"),
            "experimentConfidence": experiment.get("confidence"),
            "experimentConclusion": experiment.get("conclusion"),
            "parentExperimentIds": experiment.get("parentExperimentIds") or [],
            "llmRationale": item.get("llmRationale"),
            "createdAt": item.get("createdAt"),
            "overallVerdict": compared_row.get("overallVerdict"),
            "metrics": joined,
        }
        record["eligible"] = _eligible(record)
        versions.append(record)

    rankings: dict[str, list[dict[str, Any]]] = {}
    running_best: dict[str, list[dict[str, Any]]] = {}
    winners: dict[str, dict[str, Any]] = {}
    for name, definition in metric_defs.items():
        if definition["higherIsBetter"] is None:
            # No direction from the platform: nothing is "best" until someone says which way is better.
            rankings[name], running_best[name] = [], []
            winners[name] = {"raw": None, "eligible": None, "reason": "the platform stores no direction for this metric"}
            continue
        higher = bool(definition["higherIsBetter"])
        ranked: list[dict[str, Any]] = []
        unranked: list[str] = []
        for version in versions:
            stat = (version.get("metrics") or {}).get(name)
            if not stat or stat.get("mean") is None:
                continue
            if stat.get("pctBetter") is None:
                # Falcon has no change for this version (no baseline readings, or not compared yet): no rank.
                unranked.append(version["label"])
                continue
            ranked.append(
                {
                    "version": version["version"],
                    "label": version["label"],
                    "mean": stat["mean"],
                    "pctBetter": stat.get("pctBetter"),
                    "timesBetter": stat.get("timesBetter"),
                    "eligible": version["eligible"],
                    "lifecycle": version["lifecycle"],
                    "executionStatus": version["executionStatus"],
                    "experimentStatus": version.get("experimentStatus"),
                }
            )
        # Falcon's change, on the metric's own aggregator, as the Web UI ranks.
        ranked.sort(key=lambda row: -row["pctBetter"])
        rankings[name] = ranked
        raw = ranked[0] if ranked else None
        eligible_rows = [row for row in ranked if row["eligible"]]
        winners[name] = {
            "raw": raw,
            "eligible": eligible_rows[0] if eligible_rows else None,
            "unranked": unranked,
        }
        if raw is None:
            winners[name]["reason"] = "Artemis has no change against the baseline for any version yet"

        best_version = None
        best_mean = None
        series = []
        for version in versions:
            stat = (version.get("metrics") or {}).get(name)
            mean = stat.get("mean") if stat else None
            if mean is not None and (best_mean is None or _is_better(mean, best_mean, higher)):
                best_mean = mean
                best_version = version["version"]
            series.append(
                {
                    "version": version["version"],
                    "label": version["label"],
                    "mean": mean,
                    "bestVersion": best_version,
                    "bestMean": best_mean,
                }
            )
        running_best[name] = series

    experiment_records = []
    versions_by_experiment = {item.get("experimentId"): item for item in versions}
    status_counts = {"validated": 0, "refuted": 0, "inconclusive": 0}
    for experiment in experiments_raw:
        status = experiment.get("status")
        if status in status_counts:
            status_counts[status] += 1
        linked = versions_by_experiment.get(experiment.get("id")) or {}
        experiment_records.append(
            {
                "id": experiment.get("id"),
                "title": experiment.get("title"),
                "status": status,
                "confidence": experiment.get("confidence"),
                "parentExperimentIds": experiment.get("parentExperimentIds") or [],
                "version": linked.get("version"),
                "conclusion": experiment.get("conclusion"),
            }
        )

    lifecycle_counts = {"completed": 0, "generation_failed": 0, "scoring_failed": 0}
    execution_counts = {"success": 0, "failed": 0, "pending": 0}
    missing_metrics = []
    target_keys = [name for name, definition in metric_defs.items() if definition["kind"] == "target"]
    for version in versions:
        lifecycle = version.get("lifecycle")
        if lifecycle in lifecycle_counts:
            lifecycle_counts[lifecycle] += 1
        execution = version.get("executionStatus")
        if execution in execution_counts:
            execution_counts[execution] += 1
        if lifecycle == "completed":
            absent = [key for key in target_keys if key not in (version.get("metrics") or {})]
            if absent:
                missing_metrics.append({"version": version["version"], "metrics": absent})

    pareto = None
    if pareto_axes:
        unknown = [axis for axis in pareto_axes if axis not in metric_defs]
        if unknown:
            raise ValueError(f"unknown Pareto axes: {', '.join(unknown)}")
        undirected = [axis for axis in pareto_axes if metric_defs[axis]["higherIsBetter"] is None]
        if undirected:
            raise ValueError(f"no direction stored for Pareto axes: {', '.join(undirected)}")
        pareto = {
            "axes": [
                {
                    "key": axis,
                    "higherIsBetter": metric_defs[axis]["higherIsBetter"],
                    "kind": metric_defs[axis]["kind"],
                }
                for axis in pareto_axes
            ],
            "points": pareto_front(versions, pareto_axes, metric_defs),
            "note": "Analytical view over the named axes, not an Artemis verdict.",
        }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "collectedAt": collected_at,
        "provenance": {
            "source": "artemis discovery metrics --all --stats",
            "statsSource": "artemis discovery compare (falcon)" if stats_from_falcon else "artemis discovery metrics --all --stats",
            "runsSource": "artemis discovery metrics --all" if runs_by_group else None,
            "verdictsSource": "artemis discovery compare (falcon)" if compared_metrics or compared_rows else None,
            "commands": list(COMMANDS),
            "cli": "artemis",
        },
        "run": {
            "id": run_id,
            "projectId": project_id,
            "status": run.get("status"),
            "displayStatus": run.get("displayStatus"),
            "taskDescription": run.get("taskDescription"),
            "targetFiles": run.get("targetFiles") or [],
            "versionCount": run.get("versionCount"),
            "numVersions": run.get("numVersions"),
            "experimentCount": run.get("experimentCount"),
            "baselineGroupId": baseline_group,
            "baselineVersionSha": run.get("baselineVersionSha"),
            "baselineChangesetId": run.get("baselineChangesetId"),
            "createdAt": run.get("createdAt"),
            "updatedAt": run.get("updatedAt"),
            "runnerName": run.get("runnerName"),
            "runner": run.get("runnerName") or run.get("runnerId") or run.get("runnerUserId"),
            "projectName": payloads.get("projectName") or run.get("projectName"),
            "projectUrl": project_url,
            "webUrl": web_url,
        },
        "metrics": list(metric_defs.values()),
        "baseline": {
            "sha": run.get("baselineVersionSha"),
            "observationGroupId": baseline_group,
            "metrics": baseline_stats,
            "readings": {m.get("name"): m.get("readings") for m in (compared_baseline or {}).get("metrics") or [] if isinstance(m, dict)},
        },
        "versions": versions,
        "experiments": experiment_records,
        "rankings": rankings,
        "runningBest": running_best,
        "perMetricWinners": winners,
        "webUiBest": web_ui_best(versions),
        "bestLines": best_lines(metric_defs, versions, winners, web_ui_best(versions)),
        "steering": steering_points(payloads.get("chat"), versions),
        "executionSummary": {
            **lifecycle_counts,
            **{f"execution_{key}": value for key, value in execution_counts.items()},
            "missingTargetMetrics": missing_metrics,
        },
        "experimentSummary": status_counts,
        "pareto": pareto,
        "references": reference_pairs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a normalized Artemis discovery snapshot.")
    parser.add_argument("--run-id", help="Discovery run UUID")
    parser.add_argument("--project", help="Project UUID: collect every Discovery run in it, one snapshot each")
    parser.add_argument("--from-dir", help="Load run/versions/metrics/experiments JSON from a directory")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument("--base-url", help="Web UI origin, e.g. https://artemis.turintech.ai")
    parser.add_argument("--cli", default="artemis", help="The artemis binary to run (default: artemis on PATH)")
    parser.add_argument("--config", help="Passed to every artemis call as --config")
    parser.add_argument(
        "--pareto",
        action="append",
        default=[],
        help="Comma-separated metric keys for an optional Pareto view. Repeatable.",
    )
    return parser.parse_args(argv)


def parse_pareto_axes(values: list[str]) -> list[str]:
    axes: list[str] = []
    for value in values:
        for part in value.split(","):
            key = part.strip()
            if key and key not in axes:
                axes.append(key)
    return axes


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.run_id and not args.from_dir and not args.project:
        print("collect_discovery.py: --run-id, --project or --from-dir is required", file=sys.stderr)
        return 2
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if args.project:
        if not compare_available(args.cli, args.config):
            print(f"collect_discovery.py: {UPGRADE_HINT}", file=sys.stderr)
            return 1
        runs, skipped = [], []
        names: dict[str, str | None] = {}
        for item in sorted(list_project_runs(args.project, args.cli, args.config), key=lambda r: r.get("createdAt") or ""):
            try:
                runs.append(build_snapshot(fetch_cli(item["id"], args.cli, args.config, names), collected_at=collected_at, base_url=args.base_url))
            except (RuntimeError, ValueError) as error:
                skipped.append({"id": item.get("id"), "status": item.get("status"), "reason": str(error)[:200]})
        result = {"schemaVersion": SCHEMA_VERSION, "kind": "project", "projectId": args.project, "collectedAt": collected_at, "runs": runs, "skipped": skipped}
        encoded = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
        else:
            print(encoded)
        return 0
    if args.from_dir:
        try:
            payloads = load_from_dir(args.from_dir)
        except FileNotFoundError as error:
            print(f"collect_discovery.py: {error}", file=sys.stderr)
            return 1
    else:
        try:
            payloads = fetch_cli(args.run_id, args.cli, args.config)
        except RuntimeError as error:
            print(f"collect_discovery.py: {error}", file=sys.stderr)
            return 1
    try:
        snapshot = build_snapshot(
            payloads,
            collected_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            base_url=args.base_url,
            pareto_axes=parse_pareto_axes(args.pareto),
        )
    except ValueError as error:
        print(f"collect_discovery.py: {error}", file=sys.stderr)
        return 2
    encoded = json.dumps(snapshot, indent=2, sort_keys=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
