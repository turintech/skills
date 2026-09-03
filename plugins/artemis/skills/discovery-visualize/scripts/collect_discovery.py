#!/usr/bin/env python3
"""Collect a normalized Artemis discovery snapshot from the CLI or fixture files.

Stdlib only. Agents run this, then render the JSON with the host-specific adapter.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 1

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
    "artemis --output-format json discovery experiments list <run-id> --all",
)


def extract_json(text: str) -> Any:
    """Parse the first JSON value, ignoring logger text printed before it."""
    if text is None:
        raise ValueError("CLI produced no stdout")
    for index, char in enumerate(text):
        if char in "{[":
            obj, _end = json.JSONDecoder().raw_decode(text[index:])
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


def pct_better(baseline: float | None, value: float | None, higher_is_better: bool) -> float | None:
    if baseline is None or value is None:
        return None
    if baseline == 0:
        return 0.0
    if higher_is_better:
        return ((value - baseline) / abs(baseline)) * 100.0
    return ((baseline - value) / abs(baseline)) * 100.0


def infer_higher_is_better(name: str) -> bool:
    lowered = name.lower()
    for token in ("_ms", "runtime", "latency", "memory", "cpu", "error", "loss"):
        if token in lowered:
            return False
    return True


def classify_kind(name: str, source: str | None) -> str:
    if name in HARNESS_METRICS:
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
    return {
        "run": run,
        "versions": versions,
        "metrics": metrics,
        "experiments": experiments,
    }


def run_artemis(args: list[str]) -> str:
    completed = subprocess.run(
        ["artemis", "--output-format", "json", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"artemis {' '.join(args)} failed ({completed.returncode}): {detail}")
    return completed.stdout


def fetch_cli(run_id: str) -> dict[str, Any]:
    return {
        "run": extract_json(run_artemis(["discovery", "get", run_id])),
        "versions": extract_json(run_artemis(["discovery", "versions", "list", run_id, "--all"])),
        "metrics": extract_json(run_artemis(["discovery", "metrics", run_id, "--all", "--stats"])),
        "experiments": extract_json(run_artemis(["discovery", "experiments", "list", run_id, "--all"])),
        "status": extract_json(run_artemis(["status"])),
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


def _is_better(value: float, incumbent: float, higher_is_better: bool) -> bool:
    return value > incumbent if higher_is_better else value < incumbent


def _eligible(version: dict[str, Any]) -> bool:
    return (
        version.get("lifecycle") == "completed"
        and version.get("executionStatus") == "success"
        and version.get("experimentStatus") != "refuted"
    )


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
    web_url = f"{base_url}/projects/{project_id}/discovery/{run_id}" if base_url and project_id else None

    experiments_by_id = {item["id"]: item for item in experiments_raw if item.get("id")}

    stats_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    names_by_id: dict[str, str] = {}
    for row in stats_raw:
        group_id = row.get("observationGroupId")
        metric_id = row.get("metricId")
        name = row.get("metricName")
        if not group_id or not name:
            continue
        names_by_id[metric_id] = name
        stats_by_group.setdefault(group_id, {})[name] = _stat_payload(row)

    schema_by_id = {item.get("metricId"): item for item in (run.get("metricsSchema") or []) if item.get("metricId")}
    metric_defs: dict[str, dict[str, Any]] = {}
    for metric_id, name in names_by_id.items():
        schema = schema_by_id.get(metric_id) or {}
        source = schema.get("source")
        if "higherIsBetter" in schema:
            higher = bool(schema["higherIsBetter"])
            inferred = False
        else:
            higher = infer_higher_is_better(name)
            inferred = True
        metric_defs[name] = {
            "key": name,
            "metricId": metric_id,
            "label": metric_label(name),
            "source": source,
            "higherIsBetter": higher,
            "higherIsBetterInferred": inferred,
            "importance": schema.get("importance"),
            "kind": classify_kind(name, source),
            "description": schema.get("description"),
        }

    baseline_group = run.get("baselineGroupId")
    baseline_stats = stats_by_group.get(baseline_group or "", {})
    baseline_means = {key: (stat or {}).get("mean") for key, stat in baseline_stats.items()}

    versions: list[dict[str, Any]] = []
    for item in sorted(versions_raw, key=lambda row: (row.get("versionNumber") is None, row.get("versionNumber") or 0)):
        number = item.get("versionNumber")
        group_id = item.get("observationGroupId")
        experiment = experiments_by_id.get(item.get("experimentId") or "") or {}
        raw_metrics = stats_by_group.get(group_id or "", {})
        joined: dict[str, Any] = {}
        for name, stat in raw_metrics.items():
            definition = metric_defs.get(name) or {
                "higherIsBetter": infer_higher_is_better(name),
                "kind": classify_kind(name, None),
            }
            payload = dict(stat)
            payload["pctBetter"] = pct_better(
                baseline_means.get(name),
                stat.get("mean"),
                bool(definition["higherIsBetter"]),
            )
            joined[name] = payload
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
            "metrics": joined,
        }
        record["eligible"] = _eligible(record)
        versions.append(record)

    rankings: dict[str, list[dict[str, Any]]] = {}
    running_best: dict[str, list[dict[str, Any]]] = {}
    winners: dict[str, dict[str, Any]] = {}
    for name, definition in metric_defs.items():
        higher = bool(definition["higherIsBetter"])
        ranked: list[dict[str, Any]] = []
        for version in versions:
            stat = (version.get("metrics") or {}).get(name)
            if not stat or stat.get("mean") is None:
                continue
            ranked.append(
                {
                    "version": version["version"],
                    "label": version["label"],
                    "mean": stat["mean"],
                    "pctBetter": stat.get("pctBetter"),
                    "eligible": version["eligible"],
                    "lifecycle": version["lifecycle"],
                    "executionStatus": version["executionStatus"],
                    "experimentStatus": version.get("experimentStatus"),
                }
            )
        ranked.sort(key=lambda row: row["mean"], reverse=higher)
        rankings[name] = ranked
        raw = ranked[0] if ranked else None
        eligible_rows = [row for row in ranked if row["eligible"]]
        winners[name] = {
            "raw": raw,
            "eligible": eligible_rows[0] if eligible_rows else None,
        }

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
            "webUrl": web_url,
        },
        "metrics": list(metric_defs.values()),
        "baseline": {
            "sha": run.get("baselineVersionSha"),
            "observationGroupId": baseline_group,
            "metrics": baseline_stats,
        },
        "versions": versions,
        "experiments": experiment_records,
        "rankings": rankings,
        "runningBest": running_best,
        "perMetricWinners": winners,
        "executionSummary": {
            **lifecycle_counts,
            **{f"execution_{key}": value for key, value in execution_counts.items()},
            "missingTargetMetrics": missing_metrics,
        },
        "experimentSummary": status_counts,
        "pareto": pareto,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a normalized Artemis discovery snapshot.")
    parser.add_argument("--run-id", help="Discovery run UUID")
    parser.add_argument("--from-dir", help="Load run/versions/metrics/experiments JSON from a directory")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument("--base-url", help="Web UI origin, e.g. https://artemis.turintech.ai")
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
    if not args.run_id and not args.from_dir:
        print("collect_discovery.py: --run-id or --from-dir is required", file=sys.stderr)
        return 2
    if args.from_dir:
        payloads = load_from_dir(args.from_dir)
    else:
        payloads = fetch_cli(args.run_id)
    snapshot = build_snapshot(
        payloads,
        collected_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        base_url=args.base_url,
        pareto_axes=parse_pareto_axes(args.pareto),
    )
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
