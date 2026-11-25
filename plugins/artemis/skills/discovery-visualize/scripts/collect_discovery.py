#!/usr/bin/env python3
"""Collect a normalized Artemis discovery snapshot from the CLI or fixture files.

Stdlib only. Agents run this, then render the JSON with the host-specific adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
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


_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")


def web_origin(url: str) -> str:
    """The Web UI origin every link is built on: https and a host only, so the page links nothing else."""
    parsed = urlparse(url.strip())
    try:
        port = parsed.port
    except ValueError:
        port = -1
    if (parsed.scheme != "https" or not _HOST.match(parsed.hostname or "") or port == -1 or parsed.username or parsed.password
            or parsed.path.strip("/") or parsed.params or parsed.query or parsed.fragment):
        raise ValueError(f"--base-url must be an https origin such as https://artemis.turintech.ai, not {url!r}")
    return f"https://{parsed.hostname}" + (f":{port}" if port else "")


def infer_base_url(status: Any | None = None, explicit: str | None = None) -> str | None:
    """The run's own Web UI origin: --base-url, else the first https service status names; None links nothing."""
    if explicit:
        return web_origin(explicit)
    if not isinstance(status, dict):
        return None
    for service in status.get("services") or []:
        parsed = urlparse((service or {}).get("url") or "")
        try:
            return web_origin(f"{parsed.scheme}://{parsed.netloc}")
        except ValueError:
            continue
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
    ("ms", "ms"), ("us", "\u00b5s"), ("ns", "ns"), ("seconds", "s"), ("secs", "s"), ("sec", "s"), ("s", "s"), ("runtime", "s"),
    ("mb", "MB"), ("gb", "GB"), ("memory", "bytes"),
)


RATE_NOUNS = ("tokens", "samples", "requests", "frames", "images", "items", "ops", "queries", "rows", "steps")
RATES = ("tflops", "gflops", "fps", "qps", "throughput")  # already a rate: "tflops_s" or "gflops_per_s" is no unit we can name
TIME_WORDS = ("time", "wall", "latency", "duration", "elapsed", "runtime", "compile", "build", "step", "proc", "cpu", "total", "run",
              "ttft", "tpot", "epoch", "train", "inference", "e2e", "query")


def infer_unit(name: str) -> str | None:
    lowered = name.lower()
    words = [w for w in re.split(r"[_\s]", lowered) if w]
    if not words:
        return None
    single = {suffix: unit for suffix, unit in UNIT_SUFFIXES if "_" not in suffix}
    times = {"s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s", "ms": "ms", "us": "\u00b5s", "ns": "ns"}
    if words.count("per") > 1:
        return None  # a rate of a rate, "tokens_per_s_per_gpu": no unit we can name
    if "per" in words[:-1]:
        # A rate: "mb_per_s" is MB/s, "frames_per_sec" is frames/s, and one that leads with a unit, "ms_per_chunk", is in ms.
        i = len(words) - 2 - words[-2::-1].index("per")  # the last "per" that has a word after it
        before, after = words[i - 1] if i else "", words[i + 1]
        if before in RATES:
            return None
        if before in single and before not in times and after in times:
            return single[before] + "/" + times[after]
        if (before in RATE_NOUNS or before == "tok") and after in times:
            return ("tokens" if before == "tok" else before) + "/" + times[after]
        if before in times:  # a time per something, wherever it sits: "ms_per_chunk", "latency_ms_per_token"
            return times[before]
        if after in times or i == len(words) - 2:
            return None  # "widgets_per_s", "score_per_step": a rate too unsure to name
        # "time_per_iter_ms": the unit comes after the rate, so the suffix rule below reads it
    elif len(words) > 1 and words[-1] in times and words[-2] in ("tokens", "tok"):
        return "tokens/s"  # "tokens_s", "decode_tok_s": tokens a second
    elif len(words) > 1 and words[-1] in times and words[-2] in RATE_NOUNS + RATES + ("mb", "gb"):
        return None  # "iters_s", "mb_s": a rate written without "per", too unsure to name
    for suffix, unit in UNIT_SUFFIXES:
        if lowered == suffix or lowered.endswith("_" + suffix) or words[-1] == suffix:
            # A bare "s" is seconds only after a word for time ("proc_wall_s"); "iters_s" or "req_s" is a rate.
            if suffix in ("s", "sec", "secs") and len(words) > 1 and words[-2] not in TIME_WORDS:
                return None
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


# Flags every artemis call carries, set once from the command line: --ssl-cert-file for a deployment with its own CA.
CLI_FLAGS: list[str] = []


def run_artemis(args: list[str], cli: str = "artemis", config: str | None = None) -> str:
    completed = subprocess.run(
        [cli, *(["--config", config] if config else []), *CLI_FLAGS, "--output-format", "json", *args],
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


class CliTooOld(RuntimeError):
    """The CLI cannot give what the collector needs; every run would fail the same way, so the collector stops once."""


def compare_available(cli: str = "artemis", config: str | None = None) -> bool:
    """Whether this CLI has `discovery compare`. CLIs before 1.1.14 print the parent's help (and exit 0) instead."""
    completed = subprocess.run(
        [cli, *(["--config", config] if config else []), *CLI_FLAGS, "discovery", "compare", "--help"],
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
            raise CliTooOld(UPGRADE_HINT) from error
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
    """falcon's summary of one metric's readings, which `discovery compare` carries from CLI 1.1.17 (its quartiles from 1.1.25); {} on older CLIs."""
    if not compared or compared.get("mean") is None:
        return {}
    stats = {"mean": compared["mean"], "min": compared.get("min"), "max": compared.get("max"), "count": compared.get("readings")}
    for optional in ("std", "ste", "median", "q1", "q3"):
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


def falcon_vs_baseline(compared: dict[str, Any] | None) -> dict[str, Any] | None:
    """falcon's comparison of one metric on one version against the run's baseline, as `discovery compare` returns it."""
    if not compared or compared.get("verdict") is None:
        return None
    return {
        "source": "falcon",
        "verdict": compared.get("verdict"),
        "improvementPct": compared.get("improvementPct"),
        "improvementPoints": compared.get("improvementPoints"),
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


GATE_NAMES = {"eligible", "is_eligible", "eligibility", "gate", "gate_ok", "gate_pass", "gate_passed", "passed_gate", "passes_gate"}


def detect_gate_metric(metric_defs: dict[str, dict[str, Any]], versions: list[dict[str, Any]]) -> str | None:
    """The run's own gate when no --gate-metric is given: the one metric named as a gate (GATE_NAMES) whose every reading is
    between 0 and 1. A failed version can read 0 on everything else (no output, no errors), so without the gate it wins.
    None when there is no such metric, or several: then nothing is guessed."""
    found = []
    for name in metric_defs:
        if name.lower() not in GATE_NAMES:
            continue
        readings = [((v.get("metrics") or {}).get(name) or {}).get("mean") for v in versions]
        readings = [r for r in readings if r is not None]
        if readings and all(0 <= r <= 1 for r in readings):
            found.append(name)
    if len(found) > 1:
        print(f"collect_discovery.py: {', '.join(found)} could each be the run's gate, so none is applied; pass --gate-metric", file=sys.stderr)
    return found[0] if len(found) == 1 else None


def parse_reference_specs(values: list[str]) -> list[dict[str, str]]:
    """--reference label=NAME,file=PATH[,note=PATH][,failures=PATH]: a model scored by the run's own referee outside Discovery
    (a stock rival, say), so it is not in the platform data. The label and file are required; the paths are kept as the source."""
    specs = []
    for value in values:
        parts = dict(part.split("=", 1) for part in value.split(",") if "=" in part)
        unknown = set(parts) - {"label", "file", "note", "failures"}
        if unknown or not parts.get("label") or not parts.get("file"):
            raise ValueError(f"--reference {value!r}: give label=NAME,file=PATH[,note=PATH][,failures=PATH]")
        specs.append({k: v.strip() for k, v in parts.items()})
    return specs


def external_references(specs: list[dict[str, str]], metric_defs: dict[str, dict[str, Any]], gate_metric: str | None) -> list[dict[str, Any]]:
    """Each --reference as the snapshot carries it: its readings on the run's own metrics (only those the run measures, finite
    numbers only), whether it fails the run's gate, its failures as the referee wrote them, and its source: the file's path and
    sha256 and the provenance note. Nothing is filled in that the file does not say."""
    out = []
    for spec in specs:
        raw = Path(spec["file"]).read_bytes()
        doc = json.loads(raw)
        readings = doc.get("metrics", doc) if isinstance(doc, dict) else {}
        values = {k: float(v) for k, v in readings.items()
                  if k in metric_defs and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
        if not values:
            raise ValueError(f"--reference {spec['label']}: {spec['file']} has no reading on this run's metrics")
        gate = values.get(gate_metric) if gate_metric else None
        out.append({
            "label": spec["label"],
            "metrics": values,
            "gateFailed": gate is not None and gate < 1,
            "failures": [line.strip() for line in Path(spec["failures"]).read_text(encoding="utf-8").splitlines() if line.strip()] if spec.get("failures") else [],
            "source": {"file": Path(spec["file"]).name, "sha256": hashlib.sha256(raw).hexdigest(),  # never a local path
                       "note": Path(spec["note"]).read_text(encoding="utf-8") if spec.get("note") else None},
        })
    return out


BYTE_UNITS = {"b": 1, "byte": 1, "bytes": 1, "kb": 10**3, "mb": 10**6, "gb": 10**9, "tb": 10**12,
              "kib": 2**10, "mib": 2**20, "gib": 2**30, "tib": 2**40}
_CAP_LEAD = (r"at most|no more than|not more than|under|below|max(?:imum)?(?: of)?|(?:size )?cap(?:ped at| of)?:?|"
             r"limit(?:ed to| of)?:?|fits? (?:in|within|into)|≤|<=")
_CAP = re.compile(
    rf"(?:{_CAP_LEAD})\s*(\d[\d,]*(?:\.\d+)?)\s*(bytes?|[kmgt]i?b)\b(?!\s*/)"
    r"|bytes\s*(?:≤|<=)\s*(\d[\d,]*)", re.IGNORECASE)
_SIZE = re.compile(r"\s*(\d[\d,]*(?:\.\d+)?)\s*(bytes?|[kmgt]i?b)\s*", re.IGNORECASE)


def parse_size_cap(value: str) -> dict[str, Any]:
    """--size-cap "1.3 GB": the cap given outright, which beats reading it from the brief."""
    match = _SIZE.fullmatch(value or "")
    if not match:
        raise ValueError(f"--size-cap {value!r}: give a size with a unit, e.g. \"1.3 GB\", \"500 MiB\" or \"1319830496 bytes\"")
    unit = match.group(2)
    return {"bytes": round(float(match.group(1).replace(",", "")) * BYTE_UNITS[unit.lower()]), "text": f"--size-cap {value.strip()}", "unit": unit}


def _brief_caps(brief: Any) -> list[dict[str, Any]]:
    """Every byte cap a run's brief states, as {bytes, text, unit}: "at most 1,319,830,496 bytes", "under 1.3 GB",
    "<= 500 MiB", "bytes ≤ N". MB and GB are decimal, MiB and GiB binary; a rate ("under 5 MB/s") is not a cap."""
    # One cap stated twice ("at most 1,517,290,464 bytes", "under 1,517.3 MB") is one cap: two readings agree when they are
    # within the rounding of the less precise one (half its last digit, in bytes). The more precise phrase is kept.
    read: list[tuple[dict[str, Any], float]] = []
    for match in _CAP.finditer(brief if isinstance(brief, str) else ""):
        number, unit = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), "bytes")
        digits = number.replace(",", "")
        scale = BYTE_UNITS[unit.lower()]
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        read.append(({"bytes": round(float(digits) * scale), "text": match.group(0).strip(), "unit": unit}, 0.5 * 10 ** -decimals * scale))
    kept: list[tuple[dict[str, Any], float]] = []
    for cap, slack in read:
        same = next((i for i, (k, ks) in enumerate(kept) if abs(k["bytes"] - cap["bytes"]) <= max(slack, ks)), None)
        if same is None:
            kept.append((cap, slack))
        elif slack < kept[same][1]:
            kept[same] = (cap, slack)
    return [cap for cap, _ in kept]


def size_caps(brief: Any) -> dict[int, str]:
    """Every byte cap a run's brief states, {bytes: the phrase it was read from}."""
    return {cap["bytes"]: cap["text"] for cap in _brief_caps(brief)}


def size_cap(brief: Any) -> dict[str, Any] | None:
    """The size cap a run's brief states, as {bytes, text, unit}, `text` the phrase it was read from so a reader can check it
    and `unit` the unit it is written in. None when the brief states none, or two that differ: nothing is guessed."""
    found = _brief_caps(brief)
    return found[0] if len(found) == 1 else None


def is_byte_target(d: dict[str, Any]) -> bool:
    return d["kind"] == "target" and d.get("role") is None and str(d.get("unit") or "").lower() in BYTE_UNITS


def budget_metric(metric_defs: dict[str, dict[str, Any]], cap: dict[str, Any] | None, named: str | None = None) -> str | None:
    """The target metric the run's size cap applies to, its budget. Only with a stated cap, and only a byte-unit target:
    the one --budget-metric names, else the run's only byte-unit target, else the only one in the cap's own unit. Otherwise
    there is no budget (pass --budget-metric). No ratio decides it: a compression run often starts well above its cap."""
    if named and (named not in metric_defs or not is_byte_target(metric_defs[named])):  # a wrong name is said, cap or not
        raise ValueError(f"--budget-metric {named}: not a target metric measured in a byte unit (B, KB, MB, GB, KiB, MiB, GiB)")
    if not cap:
        return None
    if named:
        return named
    candidates = [name for name, d in metric_defs.items() if is_byte_target(d)]
    if len(candidates) == 1:
        return candidates[0]
    # Several byte metrics can be one size in different units (model_bytes in B, model_size_mb in MB): the one written in
    # the cap's own unit is the one the brief means. None or several in that unit: no budget, nothing guessed.
    scale = BYTE_UNITS.get(str(cap.get("unit") or "").lower())
    same_unit = [name for name in candidates if scale and BYTE_UNITS[str(metric_defs[name]["unit"]).lower()] == scale]
    if len(same_unit) != 1:
        return None
    print(f"collect_discovery.py: the size cap ({cap['text']}) applies to {same_unit[0]}, the byte metric in the cap's own unit "
          "(pass --budget-metric to name another)", file=sys.stderr)
    return same_unit[0]


def drawable_tradeoff(metric_defs: dict[str, dict[str, Any]], usable: list[dict[str, Any]]) -> list[str]:
    """The metrics a trade-off can draw: directed targets falcon compared on two or more of `usable` (the versions that
    passed the gate). The page and build_studio.py read the list; neither works it out again."""
    compared = lambda name: sum(1 for v in usable if (((v.get("metrics") or {}).get(name) or {}).get("vsBaseline") or {}).get("improvementPct") is not None)
    return [name for name, d in metric_defs.items() if d["kind"] == "target" and d["higherIsBetter"] is not None and compared(name) >= 2]


def falcon_best(comparison: Any, versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The version the Web UI badges Best, as falcon names it in `discovery compare`'s `bestVersion` (CLI 1.1.20+);
    None when falcon names none, there is no compare, or the CLI is too old to send the field (the snapshot's
    `provenance.bestSent` says which, so the page can say to update the CLI). Never worked out here."""
    if not isinstance(comparison, dict) or "bestVersion" not in comparison:
        return None
    named = comparison["bestVersion"]
    if not named:
        return None
    best = next((v for v in versions if v.get("id") == named.get("id")), None)
    if best is None:
        print(f"collect_discovery.py: falcon's best version {named.get('id')} is not in the run's versions, so the page names no Best", file=sys.stderr)
        return None
    return {"version": best["version"], "label": best["label"], "fitness": best["fitness"]}


# Units that say which way a metric improves. Only the unit the platform stores counts, never the name or a
# unit guessed from it, and anything else stays silent: a wrong hint is worse than none. The flag only asks the
# user to check; the direction itself always comes from the platform.
_HIGHER_UNITS = {"fps", "ops/s", "req/s", "tokens/s", "items/s", "/s"}
_LOWER_UNITS = {"s", "ms", "us", "\u00b5s", "ns", "sec", "secs", "second", "seconds"}


def finite(value: Any, path: str = "", nulled: list[str] | None = None) -> Any:
    """NaN and Infinity as null: they are not JSON, and a browser's JSON.parse refuses the whole snapshot for one.
    Each path nulled is added to `nulled`, so the caller can say where."""
    if isinstance(value, float) and not math.isfinite(value):
        if nulled is not None:
            nulled.append(path or "the snapshot")
        return None
    if isinstance(value, list):
        return [finite(v, f"{path}[{i}]", nulled) for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: finite(v, f"{path}.{k}" if path else k, nulled) for k, v in value.items()}
    return value


CONTAINERS = {"run", "versions", "metrics", "observations", "comparison", "experiments", "baseline", "docs", "runs", "groups"}


def readable_path(root: Any, path: str) -> str:
    """A payload path in a reader's words: each list item by its version or metric where it has one, and each metric
    key of a mapping, so "comparison.versions[2].metrics[0].improvementPct" reads "v2 latency_ms improvementPct".
    When no item can be named, the raw path is kept, so the line always says where."""
    words, named, node = [], False, root
    run = root.get("run") if isinstance(root, dict) else None
    run = run["docs"][0] if isinstance(run, dict) and isinstance(run.get("docs"), list) and run["docs"] else run
    groups = {run.get("baselineGroupId"): "original"} if isinstance(run, dict) and run.get("baselineGroupId") else {}
    for v in as_docs(root.get("versions")) if isinstance(root, dict) and root.get("versions") is not None else []:
        if isinstance(v, dict) and v.get("observationGroupId") and v.get("versionNumber") is not None:
            groups[v["observationGroupId"]] = f"v{v['versionNumber']}"
    for key, index in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path):
        if key:
            parent, node = node, node.get(key) if isinstance(node, dict) else None
            if not isinstance(node, (dict, list)):
                words.append(key)  # the field itself
            elif key not in CONTAINERS and isinstance(parent, dict) and isinstance(node, dict):
                words.append(key)  # a metric name used as a mapping key
                named = True
        else:
            node = node[int(index)] if isinstance(node, list) and int(index) < len(node) else None
            if isinstance(node, dict):
                group = node.get("observationGroupId")
                who = groups.get(group) if group else None  # an observation: whose reading it is, the original or vN
                if who:
                    words.append(who)
                label = (f"v{node['versionNumber']}" if node.get("versionNumber") is not None
                         else node.get("name") or node.get("metricName") or node.get("label"))
                if label:
                    words.append(str(label))
                    named = True
    return " ".join(words) if named else path


def write_finite(value: Any) -> str:
    """The snapshot as JSON, with each NaN or Infinity written as null and named on stderr: a version whose only reading
    was NaN shows as not measured, so the cause is said here."""
    nulled: list[str] = []
    encoded = json.dumps(finite(value, "", nulled), indent=2)
    if nulled:
        shown = ", ".join(nulled[:5]) + (f" and {len(nulled) - 5} more" if len(nulled) > 5 else "")
        print(f"collect_discovery.py: {len(nulled)} non-finite value(s) computed by the collector written as null: {shown}", file=sys.stderr)
    return encoded


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
    gated: tuple[dict[str, Any], str] | None = None,
    best_sent: bool = True,
) -> dict[str, Any] | None:
    """The sentences every report and chat answer carries verbatim: which version leads and why, and each
    measured metric whose own best is another version. None when there is no target metric, or the lead metric has no
    best version and the Web UI's Best has no change on it."""
    # The lead metric: a target with a direction first, then one some version moved, then the most important (high,
    # medium, low), then one where falcon calls a change significant, ties in snapshot order; never a control. A metric
    # no version moved (a correctness count that held at 0.0%) never leads a page while another one moved. The first in
    # that order with a best version leads, so a more important metric that no version has a reading on yet never hides
    # a clear winner on the next one.
    rank = {"high": 0, "medium": 1, "low": 2}
    stats = lambda n: [s for s in ((v.get("metrics") or {}).get(n) for v in versions) if s]
    moved = lambda n: any(s.get("pctBetter") not in (None, 0) for s in stats(n))
    significant = lambda n: any((s.get("vsBaseline") or {}).get("verdict") in ("better", "worse") for s in stats(n))
    targets = sorted((n for n, d in metric_defs.items() if d["kind"] == "target" and d.get("role") != "reference"),
                     key=lambda n: (metric_defs[n].get("higherIsBetter") is None, not moved(n),
                                    rank.get(metric_defs[n].get("importance"), 3), not significant(n)))
    if not targets:
        return None
    by_number = {v["version"]: v for v in versions}

    def has_best(name: str) -> bool:
        ui = (by_number.get(ui_best["version"], {}).get("metrics") or {}).get(name) if ui_best else None
        return bool((ui and ui.get("pctBetter") is not None) or (winners.get(name) or {}).get("raw"))

    key = next((n for n in targets if has_best(n)), targets[0])
    ui_stat = (by_number.get(ui_best["version"], {}).get("metrics") or {}).get(key) if ui_best else None
    by_composite = bool(ui_stat and ui_stat.get("pctBetter") is not None)
    raw = (winners.get(key) or {}).get("raw")
    lead = by_number.get(ui_best["version"]) if by_composite else (by_number.get(raw["version"]) if raw else None)
    if lead is None:
        return None
    if by_composite:
        lede = f"{lead['label']} is the Web UI\u2019s Best: the highest Composite score, the platform\u2019s roll-up of the metrics by importance."
    elif gated:  # the Web UI's Best failed the run's own gate (gated = (that Best, the gate metric)), so it is not led with
        lede = (f"The Web UI\u2019s Best is {gated[0]['label']}, by Composite score, but it failed the gate ({gated[1]} = 0) "
                f"and its values are not usable, so this page leads with the best version on {key}.")
    elif ui_best:
        lede = (f"The Web UI\u2019s Best is {ui_best['label']}, by Composite score, but Artemis has no change on {key} for it, "
                f"so this page leads with the best version on {key}.")
    elif not best_sent:
        lede = (f"This artemis CLI does not send the Web UI\u2019s Best (update it to 1.1.20 or later to see it), "
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
    checks = direction_checks(metric_defs)
    for line in checks:
        lede += " " + line
    # checks: the same lines on their own, so a page that does not print the lede can still carry each word for word.
    # order: every target in the lead order above, so a page lays out its panels the way the headline chose, not a second sort.
    return {"version": lead["version"], "label": lead["label"], "metric": key, "byComposite": by_composite, "lede": lede, "notes": notes,
            "checks": checks, "order": targets}


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


def stored_fronts(usable: list[dict[str, Any]], metric_defs: dict[str, dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    """The Pareto front of every pair of directed metrics, by pareto_front over `usable` (the versions that passed the gate):
    fronts[a][b] lists the labels on it, a before b in metric order. The page draws these and works out no front itself."""
    measured = lambda name: sum(1 for v in usable if (((v.get("metrics") or {}).get(name) or {}).get("mean")) is not None)
    keys = [name for name, d in metric_defs.items() if d["higherIsBetter"] is not None and measured(name) >= 2]
    fronts: dict[str, dict[str, list[str]]] = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            fronts.setdefault(a, {})[b] = [p["label"] for p in pareto_front(usable, [a, b], metric_defs) if not p["dominated"]]
    return fronts


# A snapshot ends up in pages people publish, so text the user's machines wrote (a brief's commands, a rationale, a steer)
# loses its hosts and absolute paths by default: each runner name becomes "runner-N", the same everywhere so a machine
# grouping still works, an absolute path "<path>", and user@host or an IP address "<host>". --keep-raw-text keeps them.
_ABS_PATH = re.compile(r"(?<![\w.:/~-])(?:~/|/)(?:[\w.@+-]+/)*[\w.@+-]+/?|\b[A-Za-z]:\\(?:[\w.@+ -]+\\)*[\w.@+-]*")
_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
_IP = _OCTET + r"(?:\." + _OCTET + r"){3}"
# user@<IP> goes whole, user and all; user@host when the host starts with a letter. A package pin (numpy@1.26) is neither.
_USER_AT_IP = re.compile(r"\b[A-Za-z_][\w.-]*@" + _IP + r"(?!\w|\.\d)")
_USER_HOST = re.compile(r"\b[A-Za-z_][\w.-]*@[A-Za-z][\w-]*(?:\.[A-Za-z][\w-]*)*\b(?![\d.]*\d)")
# An IP address, also at the end of a sentence ("on 10.0.0.12."): only a following word or ".digit" means it is not one.
_IPV4 = re.compile(r"(?<!\w)(?<!\d\.)" + _IP + r"(?!\w|\.\d)")
# Values kept as they are: ids, links, times and the names of metrics and statuses. Every other text value is redacted.
_KEEP_KEYS = frozenset({
    "id", "runId", "projectId", "versionId", "experimentId", "chatId", "agentRunId", "changesetId", "baselineChangesetId",
    "observationGroupId", "baselineGroupId", "groupIds", "sha", "versionSha", "baselineVersionSha", "baselineSha",
    "webUrl", "projectUrl", "webOrigin", "createdAt", "updatedAt", "collectedAt", "schemaVersion",
    "metricId", "key", "metric", "name", "metricName", "unit", "aggregator", "kind", "role", "importance", "source",
    "status", "displayStatus", "lifecycle", "executionStatus", "experimentStatus", "verdict", "label", "projectName",
})


def has_measured_version(payloads: dict[str, Any]) -> bool:
    """Whether any version (not the baseline) has a reading: from its stats rows, or its row in falcon's comparison."""
    groups = {v.get("observationGroupId") for v in as_docs(payloads.get("versions")) if v.get("observationGroupId")}
    if any(row.get("observationGroupId") in groups for row in as_docs(payloads.get("metrics"))):
        return True
    comparison = payloads.get("comparison") or {}
    if isinstance(comparison.get("docs"), list) and comparison["docs"]:
        comparison = comparison["docs"][0]
    return any(not row.get("isBaseline") and any(isinstance(m, dict) and m.get("readings") for m in row.get("metrics") or [])
               for row in comparison.get("versions") or [] if isinstance(row, dict))


_GENERIC_PART = re.compile(r"(?i)^(gpu|cpu|node|worker|runner|slot|rank|a|h|v|t)\d+$")


def runner_names(snaps: list[dict[str, Any]]) -> dict[str, str]:
    """One map for every runner name in these snapshots (a project's runs share it): run-level and per-reading names,
    each to "runner-N" in the order first seen, so a machine is the same placeholder in every session."""
    runners: dict[str, str] = {}

    def add(name: Any) -> None:
        if isinstance(name, str) and name and name not in runners:
            runners[name] = f"runner-{len(runners) + 1}"

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif key in ("runner", "runnerName", "machine"):
            add(value)

    for snap in snaps:
        run = snap.get("run") or {}
        add(run.get("runnerName"))
        add(run.get("runner"))
        walk(snap)
    # A brief names the machine in its own words ("on the rig2 runner" for runner someone-rig2-gpu1): each host-like part
    # of a runner name (letters and digits, 4+ characters, not a generic gpu1 or node3) maps to the same placeholder.
    for name, placeholder in list(runners.items()):
        for part in re.split(r"[-_.\s]+", name):
            if len(part) >= 4 and re.search(r"[A-Za-z]", part) and re.search(r"\d", part) and not _GENERIC_PART.match(part):
                runners.setdefault(part, placeholder)
    return runners


def redact_text(value: str, runners: dict[str, str]) -> str:
    """Runner names to their placeholders, user@host and IP addresses to <host>, absolute paths to <path>."""
    for name in sorted(runners, key=len, reverse=True):  # whole word, any case, with any domain after it (rig2.lan)
        value = re.sub(r"(?i)(?<![\w])" + re.escape(name) + r"(?:\.[A-Za-z][\w-]*)*(?![\w])", runners[name], value)
    value = _USER_AT_IP.sub("<host>", value)
    value = _USER_HOST.sub("<host>", value)
    value = _IPV4.sub("<host>", value)
    return _ABS_PATH.sub("<path>", value)


def redact_snapshot(snap: dict[str, Any], runners: dict[str, str] | None = None) -> dict[str, Any]:
    """The snapshot with hosts and absolute paths replaced in its text; ids, URLs, names and numbers untouched."""
    runners = runner_names([snap]) if runners is None else runners

    def walk(value: Any, key: str) -> Any:
        if isinstance(value, dict):
            return {k: walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, key) for v in value]
        if isinstance(value, str):
            if key in ("runner", "runnerName", "machine") and value in runners:
                return runners[value]
            return value if key in _KEEP_KEYS else redact_text(value, runners)
        return value

    return walk(snap, "")


def build_snapshot(
    payloads: dict[str, Any],
    *,
    collected_at: str,
    base_url: str | None = None,
    pareto_axes: list[str] | None = None,
    gate_metric: str | None = None,
    reference_specs: list[dict[str, str]] | None = None,
    budget_name: str | None = None,
    size_cap_given: dict[str, Any] | None = None,
    keep_raw_text: bool = False,
) -> dict[str, Any]:
    snap = _build_snapshot(payloads, collected_at=collected_at, base_url=base_url, pareto_axes=pareto_axes, gate_metric=gate_metric,
                           reference_specs=reference_specs, budget_name=budget_name, size_cap_given=size_cap_given)
    return snap if keep_raw_text else redact_snapshot(snap)


def _build_snapshot(
    payloads: dict[str, Any],
    *,
    collected_at: str,
    base_url: str | None = None,
    pareto_axes: list[str] | None = None,
    gate_metric: str | None = None,
    reference_specs: list[dict[str, str]] | None = None,
    budget_name: str | None = None,
    size_cap_given: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # A NaN or Infinity from Artemis becomes null before anything is ranked or picked from it (a NaN breaks the sort),
    # and each one is named, so a version that loses its % this way is not quietly ranked last.
    raw_paths: list[str] = []
    named = finite(payloads, "", raw_paths)
    nulled = [readable_path(payloads, p) for p in raw_paths]  # "v2 latency_ms improvementPct", not raw indices
    payloads = named
    if nulled:
        shown = ", ".join(nulled[:5]) + (f" and {len(nulled) - 5} more" if len(nulled) > 5 else "")
        head = payloads.get("run")
        head = head["docs"][0] if isinstance(head, dict) and isinstance(head.get("docs"), list) and head["docs"] else head
        run_id = head.get("id") if isinstance(head, dict) else None
        print(f"collect_discovery.py: run {run_id or 'unknown'}: {len(nulled)} non-finite value(s) from Artemis read as missing: {shown}", file=sys.stderr)
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
    # Whether this CLI's compare carries falcon's quartiles (1.1.25+): the keys are there, null or not. Without them a page
    # says to update the CLI, not that Artemis sent none.
    quartiles_sent = any(
        "q1" in m
        for row in [compared_baseline or {}, *compared_rows.values()]
        for m in row.get("metrics") or []
        if isinstance(m, dict)
    )
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

    # A version or the baseline can be several series. A pooled row names them all in `groupIds`
    # (`observationGroupId` is only the first), so each row is filed under every series it covers.
    stats_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    names_by_id: dict[str, str] = {}
    for row in stats_raw:
        ids = [g for g in row.get("groupIds") or [] if g] or [row.get("observationGroupId")]
        metric_id = row.get("metricId")
        name = row.get("metricName")
        if not ids[0] or not name:
            continue
        names_by_id[metric_id] = name
        payload = _stat_payload(row)
        for group_id in ids:
            stats_by_group.setdefault(group_id, {}).setdefault(name, payload)

    def series_stats(*id_lists: Any) -> dict[str, dict[str, Any]]:
        """Every metric any of these series recorded, with the readings of all of them."""
        ids = list(dict.fromkeys(g for ids_ in id_lists for g in (ids_ or []) if g))
        joined: dict[str, dict[str, Any]] = {}
        for group_id in ids:
            for name, stat in stats_by_group.get(group_id, {}).items():
                joined.setdefault(name, dict(stat))
        for name, stat in joined.items():
            readings = sorted(
                (item for group_id in ids for item in runs_by_group.get(group_id, {}).get(name, [])),
                key=lambda item: item.get("createdAt") or "",
            )
            if readings:
                stat["runs"] = [item["value"] for item in readings]
        return joined

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
    baseline_stats = series_stats([baseline_group], (compared_baseline or {}).get("groupIds"))
    falcon_baseline = {m.get("name"): m for m in (compared_baseline or {}).get("metrics") or [] if isinstance(m, dict)}
    for name, stat in baseline_stats.items():
        use_falcon_stats(stat, falcon_baseline.get(name))
    add_reference_ratios(baseline_stats)

    versions: list[dict[str, Any]] = []
    for item in sorted(versions_raw, key=lambda row: (row.get("versionNumber") is None, row.get("versionNumber") or 0)):
        number = item.get("versionNumber")
        group_id = item.get("observationGroupId")
        experiment = experiments_by_id.get(item.get("experimentId") or "") or {}
        compared_row = compared_rows.get(number) or compared_rows.get(item.get("versionSha")) or {}
        raw_metrics = series_stats([group_id], compared_row.get("groupIds"))
        compared_by_name = {m.get("name"): m for m in compared_row.get("metrics") or [] if isinstance(m, dict)}
        joined: dict[str, Any] = {}
        for name, stat in raw_metrics.items():
            compared = compared_by_name.get(name) or {}
            payload = dict(stat)
            use_falcon_stats(payload, compared)
            payload["pctBetter"] = compared.get("improvementPct")
            # An AI score is an opinion of the code, not a measurement, so it gets no "x better"; its % stays falcon's.
            definition = metric_defs.get(name) or {}
            payload["timesBetter"] = None if definition.get("kind") == "quality" else times_better(compared.get("improvementPct"), definition.get("higherIsBetter"))
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

    # --gate-metric: a 0/1 metric the run's own gate writes. A version that reads 0 failed it, and its other readings are not
    # usable (a load failure can write 0 for every error rate), so it is never ranked, never a winner, never on the front.
    gate = None
    if gate_metric is None:
        gate_metric = detect_gate_metric(metric_defs, versions)
        if gate_metric:
            print(f"collect_discovery.py: gating on the run's own {gate_metric} metric (pass --gate-metric to name another, or none)", file=sys.stderr)
    elif gate_metric == "none":
        gate_metric = None
    if gate_metric:
        if gate_metric not in metric_defs:
            raise ValueError(f"unknown gate metric: {gate_metric}")
        for version in versions:
            reading = ((version.get("metrics") or {}).get(gate_metric) or {}).get("mean")
            version["gateFailed"] = reading is not None and reading < 1
        gate = {"metric": gate_metric, "failed": [v["label"] for v in versions if v["gateFailed"]]}
    usable = [v for v in versions if not v.get("gateFailed")]

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
        for version in usable:
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
                    "verdict": (stat.get("vsBaseline") or {}).get("verdict"),
                    "timesBetter": stat.get("timesBetter"),
                    "eligible": version["eligible"],
                    "lifecycle": version["lifecycle"],
                    "executionStatus": version["executionStatus"],
                    "experimentStatus": version.get("experimentStatus"),
                }
            )
        # As the Web UI ranks one metric (artemis-ui src/routes/_authenticated/projects.$id.discover.$runId.versions.index.tsx,
        # the compared version): falcon's "better" verdicts first, then the largest change on the metric's own aggregator;
        # a tie keeps version order. Pending and no-verdict versions rank by their change; no change, no rank.
        ranked.sort(key=lambda row: (row["verdict"] != "better", -row["pctBetter"]))
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
            mean = stat.get("mean") if stat and not version.get("gateFailed") else None
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
            "points": pareto_front(usable, pareto_axes, metric_defs),
            "note": "The front over the named axes: worked out here from Artemis's numbers.",
        }

    ui_best = falcon_best(payloads.get("comparison"), versions)
    ui_gated = bool(ui_best and ui_best["label"] in (gate or {}).get("failed", []))
    best_sent = isinstance(payloads.get("comparison"), dict) and "bestVersion" in payloads["comparison"]
    lines = best_lines(metric_defs, usable, winners, None if ui_gated else ui_best, (ui_best, gate_metric) if ui_gated else None, best_sent=best_sent)
    # The size cap and the metric it applies to; and the metrics a trade-off can draw: directed targets falcon compared on
    # two or more versions that passed the gate. The page and build_studio.py read these and decide nothing themselves.
    # Each silent way to lose the within-the-cap view says so on stderr, with the flag that fixes it.
    caps = {} if size_cap_given else size_caps(run.get("taskDescription"))
    if len(caps) > 1:
        print(f"collect_discovery.py: the brief states {len(caps)} different size limits ({'; '.join(caps.values())}), so no size cap is set; pass --size-cap", file=sys.stderr)
    cap = size_cap_given or size_cap(run.get("taskDescription"))
    budget = budget_metric(metric_defs, cap, budget_name)
    if budget_name and not cap:
        print(f"collect_discovery.py: --budget-metric {budget_name} has no size cap to apply to: none found in the brief; pass --size-cap", file=sys.stderr)
    several = [name for name, d in metric_defs.items() if is_byte_target(d)]
    if cap and not budget and len(several) > 1:
        print(f"collect_discovery.py: the size cap ({cap['text']}) could apply to {', '.join(several)}; pass --budget-metric to name one", file=sys.stderr)
    if budget:  # the cap in the metric's own unit, so a page compares like with like and never converts units itself
        metric_defs[budget].update(role="budget", cap=cap["bytes"] / BYTE_UNITS[str(metric_defs[budget]["unit"]).lower()])
    tradeoff_metrics = drawable_tradeoff(metric_defs, usable)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "collectedAt": collected_at,
        "provenance": {
            "source": "artemis discovery metrics --all --stats",
            "statsSource": "artemis discovery compare (falcon)" if stats_from_falcon else "artemis discovery metrics --all --stats",
            "runsSource": "artemis discovery metrics --all" if runs_by_group else None,
            "verdictsSource": "artemis discovery compare (falcon)" if compared_metrics or compared_rows else None,
            "quartilesSent": quartiles_sent,
            "bestSent": best_sent,
            "commands": list(COMMANDS),
            "cli": "artemis",
        },
        "run": {
            "id": run_id,
            "projectId": project_id,
            "status": run.get("status"),
            "displayStatus": run.get("displayStatus"),
            "taskDescription": run.get("taskDescription"),
            "sizeCap": cap,
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
            "webOrigin": base_url,
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
        "webUiBest": ui_best,
        "bestLines": lines,
        "gate": gate,  # null without --gate-metric
        "externalReferences": external_references(reference_specs or [], metric_defs, gate_metric),
        "tradeoffMetrics": tradeoff_metrics,
        # The stored-direction warnings on their own as well, so a page carries them even when no version leads.
        "directionChecks": direction_checks(metric_defs),
        "nonFinite": nulled,  # the values Artemis sent as NaN or Infinity, read as missing
        "steering": steering_points(payloads.get("chat"), versions),
        "executionSummary": {
            **lifecycle_counts,
            **{f"execution_{key}": value for key, value in execution_counts.items()},
            "missingTargetMetrics": missing_metrics,
        },
        "experimentSummary": status_counts,
        "pareto": pareto,
        "fronts": stored_fronts(usable, metric_defs),
        "references": reference_pairs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a normalized Artemis discovery snapshot.")
    parser.add_argument("--run-id", help="Discovery run UUID")
    parser.add_argument("--project", help="Project UUID: collect every Discovery run in it, one snapshot each")
    parser.add_argument("--from-dir", help="Load run/versions/metrics/experiments JSON from a directory")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument("--base-url", help="Web UI origin the page links to, e.g. https://artemis.turintech.ai")
    parser.add_argument("--cli", default="artemis", help="The artemis binary to run (default: artemis on PATH)")
    parser.add_argument("--config", help="Passed to every artemis call as --config")
    parser.add_argument("--keep-raw-text", action="store_true",
                        help="Keep runner names, hosts and absolute paths in the snapshot's text (by default they are replaced, since pages get published)")
    parser.add_argument("--ssl-cert-file", help="Passed to every artemis call as --ssl-cert-file, for a deployment whose TLS uses its own CA")
    parser.add_argument(
        "--pareto",
        action="append",
        default=[],
        help="Comma-separated metric keys for an optional Pareto view. Repeatable.",
    )
    parser.add_argument(
        "--size-cap",
        help='The run\'s size cap, e.g. "1.3 GB" or "500 MiB": used instead of reading one from the brief',
    )
    parser.add_argument(
        "--budget-metric",
        help="With a size cap in the brief: the byte-unit metric the cap applies to, when the run has more than one (e.g. model_size_mb)",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="label=NAME,file=PATH[,note=PATH][,failures=PATH]: a model the run's referee scored outside Discovery, drawn as a sourced reference. Repeatable.",
    )
    parser.add_argument(
        "--gate-metric",
        help="A 0/1 metric the run's own gate writes, e.g. eligible: a version that reads 0 failed it and is never ranked, a winner or on the front. "
        "Default: the run's one metric named as a gate (eligible, gate, gate_ok, ...); none turns the gate off",
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
    CLI_FLAGS[:] = ["--ssl-cert-file", args.ssl_cert_file] if args.ssl_cert_file else []
    if not args.run_id and not args.from_dir and not args.project:
        print("collect_discovery.py: --run-id, --project or --from-dir is required", file=sys.stderr)
        return 2
    if args.base_url:  # every link is built on it, so a wrong one stops here, before any run is read
        try:
            web_origin(args.base_url)
        except ValueError as error:
            print(f"collect_discovery.py: {error}", file=sys.stderr)
            return 2
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if args.project:
        if not compare_available(args.cli, args.config):
            print(f"collect_discovery.py: {UPGRADE_HINT}", file=sys.stderr)
            return 1
        runs, skipped = [], []
        names: dict[str, str | None] = {}
        try:  # a bad --reference or --size-cap is the user's to fix, once, before any run is read
            specs = parse_reference_specs(args.reference)
            given_cap = parse_size_cap(args.size_cap) if args.size_cap else None
        except ValueError as error:
            print(f"collect_discovery.py: {error}", file=sys.stderr)
            return 2
        for item in sorted(list_project_runs(args.project, args.cli, args.config), key=lambda r: r.get("createdAt") or ""):
            try:
                fetched = fetch_cli(item["id"], args.cli, args.config, names)
                if not has_measured_version(fetched):
                    # A cancelled or failed run with nothing scored: say that, not whichever flag happened to fail first.
                    skipped.append({"id": item.get("id"), "status": item.get("status"), "reason": "no measured version"})
                    continue
                runs.append(build_snapshot(fetched, collected_at=collected_at, base_url=args.base_url, gate_metric=args.gate_metric, reference_specs=specs, budget_name=args.budget_metric, size_cap_given=given_cap, keep_raw_text=True))
            except CliTooOld as error:
                print(f"collect_discovery.py: {error}", file=sys.stderr)
                return 1
            except (OSError, RuntimeError, ValueError) as error:
                skipped.append({"id": item.get("id"), "status": item.get("status"), "reason": str(error)[:200]})
        if not args.keep_raw_text:  # one runner map for the whole project, so a machine is the same placeholder in every session
            runners = runner_names(runs)
            runs = [redact_snapshot(r, runners) for r in runs]
            skipped = [dict(item, reason=redact_text(item["reason"], runners)) for item in skipped]
        result = {"schemaVersion": SCHEMA_VERSION, "kind": "project", "projectId": args.project, "collectedAt": collected_at, "runs": runs, "skipped": skipped}
        encoded = write_finite(result)
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
            gate_metric=args.gate_metric,
            reference_specs=parse_reference_specs(args.reference),
            budget_name=args.budget_metric,
            size_cap_given=parse_size_cap(args.size_cap) if args.size_cap else None,
            keep_raw_text=args.keep_raw_text,
        )
    except (OSError, ValueError) as error:  # a --reference file that is missing or not JSON is a message, not a traceback
        print(f"collect_discovery.py: {error}", file=sys.stderr)
        return 2
    except CliTooOld as error:  # a compare too old to name falcon's best version: the upgrade hint, as a fetch gives it
        print(f"collect_discovery.py: {error}", file=sys.stderr)
        return 1
    encoded = write_finite(snapshot)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
