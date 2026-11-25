#!/usr/bin/env python3
"""Unit tests for the discovery snapshot collector."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "synthetic"
sys.path.insert(0, str(SCRIPTS))

import collect_discovery as collector  # noqa: E402


class ExtractJsonTests(unittest.TestCase):
    def test_strips_logger_noise(self) -> None:
        raw = "WARNING foo\nINFO bar\n{\"ok\": true} trailing"
        self.assertEqual(collector.extract_json(raw), {"ok": True})

    def test_accepts_bare_array(self) -> None:
        self.assertEqual(collector.extract_json("[1, 2]"), [1, 2])

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            collector.extract_json("no json here")


class DocsAndUrlTests(unittest.TestCase):
    def test_as_docs_object_and_array(self) -> None:
        self.assertEqual(collector.as_docs({"docs": [{"id": 1}]}), [{"id": 1}])
        self.assertEqual(collector.as_docs([{"id": 2}]), [{"id": 2}])
        self.assertEqual(collector.as_docs({"id": 3}), [{"id": 3}])

    def test_infer_base_url(self) -> None:
        status = {
            "services": [
                {"name": "Agent", "url": "http://10.0.0.4:8000/agent"},
                {"name": "Falcon", "url": "https://Artemis.TurinTech.ai/turintech-falcon"},
            ]
        }
        self.assertEqual(collector.infer_base_url(status), "https://artemis.turintech.ai", "the first https service, its origin only")
        self.assertIsNone(collector.infer_base_url({"services": [{"url": "http://localhost:3000"}]}), "no https origin, no link")
        self.assertEqual(collector.infer_base_url(status, "https://artemis.acme.example/"), "https://artemis.acme.example")

    def test_the_base_url_is_an_https_origin_or_refused(self) -> None:
        self.assertEqual(collector.web_origin(" https://ARTEMIS.acme.example:8443/ "), "https://artemis.acme.example:8443")
        for bad in ("http://artemis.turintech.ai", "artemis.turintech.ai", "https://", "https://user:pw@artemis.turintech.ai",
                    "https://artemis.turintech.ai/projects", "https://artemis.turintech.ai?x=1", "https://artemis.turintech.ai#top",
                    "https://artemis.turintech.ai:99999", "https://bad_host.example", "javascript:alert(1)"):
            with self.subTest(url=bad), self.assertRaisesRegex(ValueError, r"--base-url must be an https origin such as https://artemis\.turintech\.ai"):
                collector.web_origin(bad)

    def test_a_wrong_base_url_stops_before_any_run_is_read(self) -> None:
        from unittest import mock
        for argv in (["--from-dir", str(FIXTURES)], ["--project", "p-1"], ["--run-id", "r-1"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with mock.patch.object(collector, "fetch_cli", side_effect=AssertionError("read a run")), \
                     mock.patch.object(collector, "compare_available", side_effect=AssertionError("called the CLI")), \
                     mock.patch.object(collector, "load_from_dir", side_effect=AssertionError("read a run")), \
                     contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(collector.main(argv + ["--base-url", "http://artemis.turintech.ai"]), 2)
                self.assertIn("--base-url must be an https origin", err.getvalue())


class MetricMathTests(unittest.TestCase):
    def test_times_better_reads_falcons_improvement(self) -> None:
        # Lower is better: 50% better means half the time, so 2x.
        self.assertAlmostEqual(collector.times_better(50.0, False), 2.0)
        self.assertAlmostEqual(collector.times_better(300.0, True), 4.0)
        self.assertIsNone(collector.times_better(None, True))
        self.assertIsNone(collector.times_better(20.0, None))
        self.assertIsNone(collector.times_better(100.0, False))

    def test_kind_classification(self) -> None:
        self.assertEqual(collector.classify_kind("compile_runtime", "worker"), "harness")
        self.assertEqual(collector.classify_kind("quality_score", "agent"), "quality")
        self.assertEqual(collector.classify_kind("latency_ms", "worker"), "target")

    def test_direction_is_never_guessed_from_a_name(self) -> None:
        self.assertFalse(hasattr(collector, "infer_higher_is_better"))


class SnapshotFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payloads = collector.load_from_dir(str(FIXTURES))
        cls.snapshot = collector.build_snapshot(
            payloads,
            collected_at="2026-09-02T00:00:00+00:00",
            base_url="https://artemis.example",
            pareto_axes=["latency_ms", "quality_score"],
        )

    def test_schema_and_provenance(self) -> None:
        snap = self.snapshot
        self.assertEqual(snap["schemaVersion"], 2)
        self.assertEqual(snap["run"]["id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(
            snap["run"]["webUrl"],
            "https://artemis.example/projects/22222222-2222-2222-2222-222222222222/discover/11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(snap["run"]["webOrigin"], "https://artemis.example", "the page links only under the run's own origin")
        kinds = {item["key"]: item["kind"] for item in snap["metrics"]}
        self.assertEqual(kinds["latency_ms"], "target")
        self.assertEqual(kinds["quality_score"], "quality")
        self.assertEqual(kinds["compile_runtime"], "harness")
        self.assertFalse(next(m for m in snap["metrics"] if m["key"] == "latency_ms")["higherIsBetter"])
        self.assertTrue(next(m for m in snap["metrics"] if m["key"] == "quality_score")["higherIsBetter"])

    def test_joins_and_percentages(self) -> None:
        by_label = {row["label"]: row for row in self.snapshot["versions"]}
        self.assertAlmostEqual(by_label["v1"]["metrics"]["latency_ms"]["pctBetter"], 20.0)
        self.assertAlmostEqual(by_label["v2"]["metrics"]["latency_ms"]["pctBetter"], 40.0)
        self.assertAlmostEqual(by_label["v4"]["metrics"]["quality_score"]["pctBetter"], 40.0)
        self.assertEqual(by_label["v3"]["metrics"], {})
        self.assertNotIn("latency_ms", by_label["v5"]["metrics"])

    def test_gaps_are_null_not_zero(self) -> None:
        series = self.snapshot["runningBest"]["latency_ms"]
        by_version = {row["version"]: row for row in series}
        self.assertIsNone(by_version[3]["mean"])
        self.assertIsNone(by_version[5]["mean"])
        self.assertEqual(by_version[3]["bestVersion"], 2)
        self.assertEqual(by_version[3]["bestMean"], 6.0)
        self.assertNotIn(0.0, [row["mean"] for row in series if row["version"] in (3, 5)])

    def test_winners_split_raw_and_eligible(self) -> None:
        latency = self.snapshot["perMetricWinners"]["latency_ms"]
        self.assertEqual(latency["raw"]["version"], 2)
        self.assertFalse(latency["raw"]["eligible"])
        self.assertEqual(latency["raw"]["experimentStatus"], "refuted")
        self.assertEqual(latency["eligible"]["version"], 4)
        quality = self.snapshot["perMetricWinners"]["quality_score"]
        self.assertEqual(quality["raw"]["version"], 4)
        self.assertEqual(quality["eligible"]["version"], 4)

    def test_rankings_and_summaries(self) -> None:
        ranked = [row["version"] for row in self.snapshot["rankings"]["latency_ms"]]
        self.assertEqual(ranked, [2, 4, 1])
        summary = self.snapshot["executionSummary"]
        self.assertEqual(summary["generation_failed"], 1)
        self.assertEqual(summary["execution_failed"], 1)
        self.assertEqual(summary["execution_success"], 3)
        missing = summary["missingTargetMetrics"]
        self.assertEqual(missing, [{"version": 5, "metrics": ["latency_ms"]}])
        self.assertEqual(self.snapshot["experimentSummary"]["refuted"], 2)
        self.assertEqual(self.snapshot["experimentSummary"]["validated"], 2)

    def test_no_universal_winner_field(self) -> None:
        self.assertNotIn("winner", self.snapshot)
        self.assertNotIn("bestVersion", self.snapshot)

    def test_pareto_is_opt_in_and_labelled(self) -> None:
        front = self.snapshot["pareto"]
        self.assertEqual([axis["key"] for axis in front["axes"]], ["latency_ms", "quality_score"])
        points = {row["version"]: row for row in front["points"]}
        self.assertFalse(points[2]["dominated"])
        self.assertFalse(points[4]["dominated"])
        self.assertTrue(points[1]["dominated"])
        self.assertIn("worked out here from Artemis's numbers", front["note"])

    def test_every_directed_pair_has_its_front_stored_by_the_one_rule(self) -> None:
        fronts = self.snapshot["fronts"]
        directed = [m["key"] for m in self.snapshot["metrics"] if m["higherIsBetter"] is not None]
        defs = {m["key"]: m for m in self.snapshot["metrics"]}
        pairs = [(a, b) for a, row in fronts.items() for b in row]
        self.assertTrue(pairs)
        self.assertTrue(all(a in directed and b in directed and directed.index(a) < directed.index(b) for a, b in pairs), pairs)
        for a, b in pairs:
            with self.subTest(pair=(a, b)):
                want = [p["label"] for p in collector.pareto_front(self.snapshot["versions"], [a, b], defs) if not p["dominated"]]
                self.assertEqual(fronts[a][b], want, "pareto_front, the one dominance rule")
        named = {p["label"] for p in self.snapshot["pareto"]["points"] if not p["dominated"]}
        stored = fronts.get("latency_ms", {}).get("quality_score") or fronts["quality_score"]["latency_ms"]
        self.assertEqual(set(stored), named, "the --pareto front and the stored one agree")

    def test_cli_from_dir_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "snapshot.json")
            code = collector.main(
                [
                    "--from-dir",
                    str(FIXTURES),
                    "--output",
                    out,
                    "--base-url",
                    "https://artemis.example",
                    "--pareto",
                    "latency_ms,quality_score",
                ]
            )
            self.assertEqual(code, 0)
            loaded = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual(loaded["schemaVersion"], 2)
            self.assertEqual(loaded["perMetricWinners"]["latency_ms"]["raw"]["version"], 2)


if __name__ == "__main__":
    unittest.main()


class WebUiBestTests(unittest.TestCase):
    """The Web UI's Best is falcon's pick, read from `discovery compare`; the collector ranks nothing itself."""

    @staticmethod
    def snapshot(best):
        payloads = collector.load_from_dir(str(FIXTURES))
        if best == "absent":
            del payloads["comparison"]["bestVersion"]
        else:
            payloads["comparison"]["bestVersion"] = best
        return collector.build_snapshot(payloads, collected_at="2026-09-02T00:00:00+00:00")

    def test_falcons_pick_is_best_even_when_another_version_scored_higher(self) -> None:
        # v2 has the highest Composite score (0.9); falcon names v4 (0.4), and the page follows falcon.
        snapshot = self.snapshot({"id": "ver-4", "versionNumber": 4, "sha": "sha-4"})
        self.assertEqual(snapshot["webUiBest"], {"version": 4, "label": "v4", "fitness": 0.4})

    def test_no_best_when_falcon_names_none(self) -> None:
        self.assertIsNone(self.snapshot(None)["webUiBest"])

    def test_a_compare_without_falcons_best_names_none_and_says_to_update(self) -> None:
        # Prod pins a CLI older than 1.1.20: it still gets a page, with no Best and a line saying to update, never a Best worked out here.
        snapshot = self.snapshot("absent")
        self.assertIsNone(snapshot["webUiBest"])
        self.assertFalse(snapshot["provenance"]["bestSent"])
        self.assertIn("update it to 1.1.20 or later", snapshot["bestLines"]["lede"])

    def test_a_best_missing_from_the_versions_list_names_no_best_and_says_so(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            snapshot = self.snapshot({"id": "ver-99", "versionNumber": 2, "sha": "sha-2"})
        self.assertIsNone(snapshot["webUiBest"])
        self.assertIn("ver-99 is not in the run's versions", err.getvalue())

    def test_fixture_snapshot_names_the_web_uis_best(self) -> None:
        snapshot = collector.build_snapshot(collector.load_from_dir(str(FIXTURES)), collected_at="2026-09-02T00:00:00+00:00")
        self.assertEqual(snapshot["webUiBest"], {"version": 2, "label": "v2", "fitness": 0.9})


class BestLinesTests(unittest.TestCase):
    @staticmethod
    def defs(**kinds: str) -> dict:
        directions = {"latency_ms": False, "fps": True, "quality": True, "compile_s": False}
        return {k: {"key": k, "kind": v, "higherIsBetter": directions.get(k, True), "unit": None} for k, v in kinds.items()}

    @staticmethod
    def version(n: int, **pcts: float | None) -> dict:
        return {"version": n, "label": f"v{n}", "metrics": {k: {"mean": 1.0, "pctBetter": p} for k, p in pcts.items()}}

    @staticmethod
    def winner(n: int, pct: float) -> dict:
        return {"raw": {"version": n, "label": f"v{n}", "pctBetter": pct}}

    def test_lede_names_a_measured_metric_whose_best_is_better(self) -> None:
        defs = self.defs(latency_ms="target", compile_s="harness", quality="quality")
        versions = [self.version(1, latency_ms=10.0, compile_s=5.0, quality=12.0), self.version(2, latency_ms=20.0, compile_s=-3.0, quality=9.0)]
        winners = {"latency_ms": self.winner(2, 20.0), "compile_s": self.winner(1, 5.0), "quality": self.winner(1, 12.0)}
        lines = collector.best_lines(defs, versions, winners, {"version": 2, "label": "v2", "fitness": 0.5})
        self.assertEqual(lines["version"], 2)
        self.assertTrue(lines["byComposite"])
        self.assertEqual(
            lines["lede"],
            "v2 is the Web UI\u2019s Best: the highest Composite score, the platform\u2019s roll-up of the metrics by importance. "
            "Best on a single metric instead: v1 on compile_s (+5.0%).",
        )
        # An AI Metric's own best is never named; a measured metric's is, in its panel note too.
        self.assertEqual(lines["notes"], {"compile_s": "v1 is best on compile_s"})

    def test_a_tie_is_not_another_best(self) -> None:
        defs = self.defs(latency_ms="target", compile_s="harness")
        versions = [self.version(1, latency_ms=10.0, compile_s=0.0), self.version(2, latency_ms=20.0, compile_s=0.0)]
        winners = {"latency_ms": self.winner(2, 20.0), "compile_s": self.winner(1, 0.0)}
        lines = collector.best_lines(defs, versions, winners, {"version": 2, "label": "v2", "fitness": 0.5})
        self.assertNotIn("instead", lines["lede"])
        self.assertEqual(lines["notes"], {})

    def test_a_metric_the_lead_did_not_measure_says_so(self) -> None:
        defs = self.defs(latency_ms="target", quality="quality")
        versions = [self.version(1, latency_ms=10.0, quality=1.0), self.version(2, latency_ms=20.0)]
        winners = {"latency_ms": self.winner(2, 20.0), "quality": self.winner(1, 1.0)}
        lines = collector.best_lines(defs, versions, winners, {"version": 2, "label": "v2", "fitness": 0.5})
        self.assertEqual(lines["notes"], {"quality": "v2 has no reading on quality; v1 is best on it"})

    def test_a_metric_no_version_measured_needs_no_note(self) -> None:
        defs = self.defs(latency_ms="target", quality="quality")
        versions = [self.version(1, latency_ms=10.0), self.version(2, latency_ms=20.0)]
        winners = {"latency_ms": self.winner(2, 20.0), "quality": {"raw": None}}
        lines = collector.best_lines(defs, versions, winners, {"version": 2, "label": "v2", "fitness": 0.5})
        self.assertEqual(lines["notes"], {})

    def test_without_a_web_ui_best_the_target_winner_leads_and_says_why(self) -> None:
        defs = self.defs(latency_ms="target")
        versions = [self.version(1, latency_ms=10.0), self.version(2, latency_ms=20.0)]
        lines = collector.best_lines(defs, versions, {"latency_ms": self.winner(2, 20.0)}, None)
        self.assertEqual((lines["version"], lines["byComposite"]), (2, False))
        self.assertIn("The Web UI shows no Best", lines["lede"])

    def test_a_web_ui_best_with_no_change_on_the_target_falls_back(self) -> None:
        defs = self.defs(latency_ms="target")
        versions = [self.version(1, latency_ms=None), self.version(2, latency_ms=20.0)]
        lines = collector.best_lines(defs, versions, {"latency_ms": self.winner(2, 20.0)}, {"version": 1, "label": "v1", "fitness": 0.9})
        self.assertEqual(lines["version"], 2)
        self.assertIn("The Web UI\u2019s Best is v1, by Composite score, but Artemis has no change on latency_ms", lines["lede"])

    def test_no_best_version_gives_none(self) -> None:
        self.assertIsNone(collector.best_lines(self.defs(latency_ms="target"), [self.version(1)], {"latency_ms": {"raw": None}}, None))

    @staticmethod
    def metric(kind: str, higher: bool, unit: str | None) -> dict:
        return {"kind": kind, "higherIsBetter": higher, "platformUnit": unit, "unit": unit}

    def test_a_stored_direction_its_platform_unit_contradicts_is_flagged_not_changed(self) -> None:
        defs = {
            "simulation_fps": self.metric("target", False, "fps"),
            "command 1_runtime": self.metric("harness", True, "s"),
            "frames_out": self.metric("harness", False, "frames/s"),
            "frame_time": self.metric("harness", False, "ms"),
            "throughput": self.metric("harness", True, "ops/s"),
        }
        self.assertEqual(
            collector.direction_checks(defs),
            [
                "simulation_fps is set as lower-is-better on this project; check Settings > Metrics.",
                "command 1_runtime is set as higher-is-better on this project; check Settings > Metrics.",
                "frames_out is set as lower-is-better on this project; check Settings > Metrics.",
            ],
        )
        self.assertFalse(defs["simulation_fps"]["higherIsBetter"])
        lines = collector.best_lines(
            {"simulation_fps": {"key": "simulation_fps", **defs["simulation_fps"]}},
            [{"version": 1, "label": "v1", "metrics": {"simulation_fps": {"mean": 1.0, "pctBetter": 5.0}}}],
            {"simulation_fps": self.winner(1, 5.0)}, None)
        self.assertIn("simulation_fps is set as lower-is-better on this project; check Settings > Metrics.", lines["lede"])
        self.assertEqual(lines["checks"], ["simulation_fps is set as lower-is-better on this project; check Settings > Metrics."])

    def test_the_lead_passes_over_a_more_important_metric_nobody_has_a_reading_on(self) -> None:
        defs = {
            "p99_ms": {"kind": "target", "importance": "high", "higherIsBetter": False},
            "latency_ms": {"kind": "target", "importance": "medium", "higherIsBetter": False},
        }
        versions = [{"version": 2, "label": "v2", "metrics": {"latency_ms": {"pctBetter": 40.0}}}]
        winners = {"p99_ms": {"raw": None}, "latency_ms": {"raw": {"version": 2, "label": "v2", "pctBetter": 40.0}}}
        self.assertEqual(collector.best_lines(defs, versions, winners, None)["metric"], "latency_ms")

    def test_a_tie_in_importance_leads_with_the_significant_change(self) -> None:
        # Staging run 470b9ac1: both "high"; answers held at 0.0% while p95 fell 96.7%, significantly.
        defs = {
            "answers_match": {"kind": "target", "importance": "high", "higherIsBetter": True},
            "p95_ms": {"kind": "target", "importance": "high", "higherIsBetter": False},
            "p50_ms": {"kind": "target", "importance": "high", "higherIsBetter": False},
        }
        stat = lambda pct, verdict: {"pctBetter": pct, "vsBaseline": {"verdict": verdict, "improvementPct": pct}}
        versions = [{"version": 8, "label": "v8", "metrics": {"answers_match": stat(0, "noise"), "p50_ms": stat(3.0, "noise"),
                                                              "p95_ms": stat(96.7, "better")}}]
        winners = {"answers_match": {"raw": {"version": 8, "label": "v8", "pctBetter": 0}},
                   "p50_ms": {"raw": {"version": 8, "label": "v8", "pctBetter": 3.0}},
                   "p95_ms": {"raw": {"version": 8, "label": "v8", "pctBetter": 96.7}}}
        self.assertEqual(collector.best_lines(defs, versions, winners, None)["metric"], "p95_ms")

    def test_a_metric_no_version_moved_never_leads_one_that_moved(self) -> None:
        defs = {
            "answers_match": {"kind": "target", "importance": "high", "higherIsBetter": True},
            "p95_ms": {"kind": "target", "importance": "medium", "higherIsBetter": False},
        }
        versions = [{"version": 8, "label": "v8", "metrics": {"answers_match": {"pctBetter": 0}, "p95_ms": {"pctBetter": 40.0}}}]
        winners = {"answers_match": {"raw": {"version": 8, "label": "v8", "pctBetter": 0}},
                   "p95_ms": {"raw": {"version": 8, "label": "v8", "pctBetter": 40.0}}}
        self.assertEqual(collector.best_lines(defs, versions, winners, None)["metric"], "p95_ms")

    def test_a_nan_from_artemis_is_missing_before_anything_is_ranked(self) -> None:
        payloads = collector.load_from_dir(str(FIXTURES))
        top = next(v for v in payloads["comparison"]["versions"] if v.get("versionNumber") == 2)
        next(m for m in top["metrics"] if m["name"] == "latency_ms")["improvementPct"] = float("nan")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([r["label"] for r in snap["rankings"]["latency_ms"]], ["v4", "v1"])
        self.assertEqual(snap["perMetricWinners"]["latency_ms"]["raw"]["label"], "v4")
        self.assertIn("run 11111111-1111-1111-1111-111111111111: 1 non-finite value(s) from Artemis read as missing: v2 latency_ms improvementPct", err.getvalue())
        self.assertEqual(snap["nonFinite"], ["v2 latency_ms improvementPct"])

    def test_every_non_finite_value_is_named_by_what_it_belongs_to(self) -> None:
        root = {"observations": [{"metricName": "latency_ms", "value": 1.0}], "comparison": {"versions": [{"versionNumber": 2, "metrics": {"latency_ms": {"mean": 1.0}}}]},
                "odd": [[1.0]]}
        self.assertEqual(collector.readable_path(root, "observations[0].value"), "latency_ms value")
        self.assertEqual(collector.readable_path(root, "comparison.versions[0].metrics.latency_ms.mean"), "v2 latency_ms mean")
        self.assertEqual(collector.readable_path(root, "odd[0][0]"), "odd[0][0]")  # nothing to name it by: the raw path
        root = {"run": {"baselineGroupId": "g-base"}, "versions": [{"versionNumber": 4, "observationGroupId": "g-4"}],
                "observations": [{"observationGroupId": "g-base", "metricName": "latency_ms", "value": 1.0}, {"observationGroupId": "g-4", "metricName": "latency_ms", "value": 1.0}]}
        self.assertEqual([collector.readable_path(root, f"observations[{i}].value") for i in (0, 1)], ["original latency_ms value", "v4 latency_ms value"])

    def test_nan_and_infinity_are_written_as_null_and_named(self) -> None:
        self.assertEqual(collector.finite({"a": [float("nan"), 1.5, float("inf")], "b": {"c": float("-inf")}}), {"a": [None, 1.5, None], "b": {"c": None}})
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(json.loads(collector.write_finite({"versions": [{"metrics": {"x": {"std": float("nan")}}}]})), {"versions": [{"metrics": {"x": {"std": None}}}]})
        self.assertIn("1 non-finite value(s) computed by the collector written as null: versions[0].metrics.x.std", err.getvalue())

    def test_names_and_unsure_units_never_flag(self) -> None:
        defs = {
            # Set the right way, and their names alone would have suggested the opposite.
            "memory_saved_mb": self.metric("harness", True, "MB"),
            "latency_reduction_pct": self.metric("harness", True, "%"),
            "throughput_drop": self.metric("harness", False, None),
            "runtime_improvement": self.metric("harness", True, None),
            # No platform unit, only one guessed from the name: silent.
            "wall_time_s": {"kind": "harness", "higherIsBetter": True, "platformUnit": None, "unit": "s"},
            # An AI Metric, and a metric with no stored direction.
            "speed_judgement": self.metric("quality", False, "fps"),
            "latency": self.metric("harness", None, "ms"),
        }
        self.assertEqual(collector.direction_checks(defs), [])


class SteeringTests(unittest.TestCase):
    TASK = "Make the kernel faster."
    VERSIONS = [
        {"version": 1, "label": "v1", "createdAt": "2026-10-13T11:47:53Z"},
        {"version": 2, "label": "v2", "createdAt": "2026-10-13T11:54:43Z"},
        {"version": 3, "label": "v3", "createdAt": "2026-10-13T12:36:23Z"},
        {"version": 4, "label": "v4", "createdAt": "2026-10-13T12:38:14Z"},
    ]

    @staticmethod
    def user(at: str, message: str, run: str) -> dict:
        return {"type": "user", "agentRunId": run, "timestamp": at, "payload": {"id": run, "message": message, "parts": None}}

    def chat(self) -> list:
        return [
            self.user("2026-10-13T11:46:49.635000Z", self.TASK, "run-1"),
            {"type": "assistant.end", "agentRunId": "run-1", "timestamp": "2026-10-13T11:50:00Z", "payload": {}},
            # A continue without guidance resends the task: not a steer.
            self.user("2026-10-13T12:35:33.287000Z", self.TASK, "run-2"),
            self.user("2026-10-13T12:35:39.627000Z", "  Focus on memory now.  ", "run-3"),
            self.user("2026-10-13T12:35:50Z", "/compact", "run-3"),
        ]

    def test_a_steer_is_placed_before_the_first_version_made_after_it(self) -> None:
        steering = collector.steering_points(self.chat(), self.VERSIONS)
        self.assertIsNone(steering["reason"])
        self.assertEqual(
            steering["points"],
            [{"at": "2026-10-13T12:35:39.627000Z", "guidance": "Focus on memory now.", "firstVersion": 3, "firstLabel": "v3"}],
        )

    def test_a_steer_after_the_last_version_has_no_first_version(self) -> None:
        chat = self.chat() + [self.user("2026-10-13T13:00:00Z", "Try the cache next.", "run-4")]
        last = collector.steering_points(chat, self.VERSIONS)["points"][-1]
        self.assertEqual((last["guidance"], last["firstVersion"]), ("Try the cache next.", None))

    def test_a_run_never_steered_has_no_points(self) -> None:
        steering = collector.steering_points(self.chat()[:3], self.VERSIONS)
        self.assertEqual((steering["points"], steering["reason"]), ([], None))

    def test_an_unreadable_chat_says_so(self) -> None:
        steering = collector.steering_points(None, self.VERSIONS)
        self.assertEqual(steering["points"], [])
        self.assertIn("could not be read", steering["reason"])

    def test_from_dir_reads_chat_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for item in FIXTURES.iterdir():
                shutil.copy(item, tmp)
            Path(tmp, "chat.json").write_text(json.dumps(self.chat()), encoding="utf-8")
            versions = json.loads(Path(tmp, "versions.json").read_text(encoding="utf-8"))
            for doc, row in zip(versions.get("docs", versions) if isinstance(versions, dict) else versions, self.VERSIONS + self.VERSIONS):
                doc["createdAt"] = row["createdAt"]
            Path(tmp, "versions.json").write_text(json.dumps(versions), encoding="utf-8")
            snapshot = collector.build_snapshot(collector.load_from_dir(tmp), collected_at="2026-09-02T00:00:00+00:00")
        self.assertEqual([p["guidance"] for p in snapshot["steering"]["points"]], ["Focus on memory now."])

    def test_fetch_cli_reads_the_runs_chat(self) -> None:
        calls = []

        def fake(args, cli="artemis", config=None):
            calls.append(args)
            if args[:2] == ["discovery", "get"]:
                return json.dumps({"id": "run", "projectId": "proj", "chatId": "chat-9"})
            if args[:2] == ["chat", "messages"]:
                return json.dumps(self.chat())
            return "{}"

        original = collector.run_artemis
        collector.run_artemis = fake
        try:
            payloads = collector.fetch_cli("run")
        finally:
            collector.run_artemis = original
        self.assertIn(["chat", "messages", "chat-9"], calls)
        self.assertEqual(payloads["chat"], self.chat())

    def test_fetch_chat_failure_is_not_fatal(self) -> None:
        def failing(args, cli="artemis", config=None):
            raise RuntimeError("artemis chat messages failed (1): 404")

        original = collector.run_artemis
        collector.run_artemis = failing
        try:
            self.assertIsNone(collector.fetch_chat("chat-9"))
            self.assertIsNone(collector.fetch_chat(None))
        finally:
            collector.run_artemis = original


class SeveralSeriesTests(unittest.TestCase):
    """A version or the baseline measured in more than one series keeps every metric and reading."""

    @staticmethod
    def payloads() -> dict:
        payloads = collector.load_from_dir(str(FIXTURES))
        rows = {r.get("versionNumber"): r for r in payloads["comparison"]["versions"]}
        baseline = next(r for r in payloads["comparison"]["versions"] if r.get("isBaseline"))
        # v1 was measured again into a second series, obs-1b, which also recorded a new metric.
        rows[1]["groupIds"] = ["obs-1", "obs-1b"]
        payloads["observations"].append({"metricId": "m-latency", "metricName": "latency_ms", "observationGroupId": "obs-1b",
                                         "value": 7.5, "createdAt": "2026-01-03T00:00:00Z"})
        payloads["metrics"].append({"metricId": "m-mem", "metricName": "peak_mem_mb", "observationGroupId": "obs-1b",
                                    "mean": 300.0, "min": 300.0, "max": 300.0, "count": 1})
        # The baseline is two series too, and only the second recorded peak_mem_mb.
        baseline["groupIds"] = ["obs-base", "obs-base-2"]
        payloads["metrics"].append({"metricId": "m-mem", "metricName": "peak_mem_mb", "observationGroupId": "obs-base-2",
                                    "mean": 320.0, "min": 320.0, "max": 320.0, "count": 1})
        return payloads

    def test_a_metric_only_in_a_later_series_is_kept(self) -> None:
        snapshot = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00")
        v1 = next(v for v in snapshot["versions"] if v["version"] == 1)
        self.assertIn("peak_mem_mb", v1["metrics"])
        self.assertIn("peak_mem_mb", snapshot["baseline"]["metrics"])
        self.assertEqual(v1["metrics"]["peak_mem_mb"]["mean"], 300.0)
        self.assertEqual(snapshot["baseline"]["metrics"]["peak_mem_mb"]["mean"], 320.0)

    def test_readings_come_from_every_series(self) -> None:
        snapshot = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00")
        v1 = next(v for v in snapshot["versions"] if v["version"] == 1)
        self.assertEqual(v1["metrics"]["latency_ms"].get("runs"), [8.0, 7.5])

    def test_a_pooled_row_is_found_from_any_of_its_series(self) -> None:
        # A pooled stats row names every series; observationGroupId is only the first, not the version's own.
        payloads = collector.load_from_dir(str(FIXTURES))
        payloads["metrics"] = [m for m in payloads["metrics"] if m["observationGroupId"] != "obs-2"]
        payloads["metrics"].append({"metricId": "m-latency", "metricName": "latency_ms", "observationGroupId": "obs-2a",
                                    "groupIds": ["obs-2a", "obs-2"], "mean": 6.0, "min": 6.0, "max": 6.0, "count": 2})
        snapshot = collector.build_snapshot(payloads, collected_at="2026-09-02T00:00:00+00:00")
        v2 = next(v for v in snapshot["versions"] if v["version"] == 2)
        self.assertIn("latency_ms", v2["metrics"])

    def test_one_series_snapshots_are_unchanged(self) -> None:
        before = collector.build_snapshot(collector.load_from_dir(str(FIXTURES)), collected_at="2026-09-02T00:00:00+00:00")
        self.assertEqual([sorted(v["metrics"]) for v in before["versions"]][:2], [["compile_runtime", "latency_ms", "quality_score"]] * 2)


class ObservationTests(unittest.TestCase):
    """Individual runs and the platform's direction come from `discovery metrics --all`."""

    def payloads(self, observations):
        return {
            "run": {"id": "run-1", "projectId": "p-1", "baselineGroupId": "g-base", "metricsSchema": [{"metricId": "m-fps", "source": "worker"}]},
            "versions": [{"id": "v-1", "versionNumber": 1, "observationGroupId": "g-1", "lifecycle": "completed", "executionStatus": "success"}],
            "metrics": [
                {"observationGroupId": "g-base", "metricId": "m-fps", "metricName": "frame_time", "mean": 10.0, "min": 9.0, "max": 11.0, "count": 2},
                {"observationGroupId": "g-1", "metricId": "m-fps", "metricName": "frame_time", "mean": 20.0, "min": 19.0, "max": 21.0, "count": 2},
            ],
            "observations": observations,
            "experiments": [],
        }

    def test_runs_and_direction_from_observations(self) -> None:
        observations = [
            {"observationGroupId": "g-base", "metricName": "frame_time", "value": 11.0, "higherIsBetter": True, "createdAt": "2026-01-01T00:00:02Z"},
            {"observationGroupId": "g-base", "metricName": "frame_time", "value": 9.0, "higherIsBetter": True, "createdAt": "2026-01-01T00:00:01Z"},
            {"observationGroupId": "g-1", "metricName": "frame_time", "value": 19.0, "higherIsBetter": True, "createdAt": "2026-01-01T00:00:03Z"},
            {"observationGroupId": "g-1", "metricName": "frame_time", "value": 21.0, "higherIsBetter": True, "createdAt": "2026-01-01T00:00:04Z"},
        ]
        snap = collector.build_snapshot(self.payloads(observations), collected_at="2026-01-01T00:00:00Z")
        metric = snap["metrics"][0]
        # The name says lower is better; the platform's stored direction wins.
        self.assertTrue(metric["higherIsBetter"])
        self.assertEqual(snap["baseline"]["metrics"]["frame_time"]["runs"], [9.0, 11.0])
        self.assertEqual(snap["versions"][0]["metrics"]["frame_time"]["runs"], [19.0, 21.0])
        # No comparison from falcon, so no change is claimed.
        self.assertIsNone(snap["versions"][0]["metrics"]["frame_time"]["pctBetter"])
        self.assertIsNone(snap["versions"][0]["metrics"]["frame_time"]["vsBaseline"])

    def test_without_a_platform_direction_nothing_is_ranked(self) -> None:
        snap = collector.build_snapshot(self.payloads(None), collected_at="2026-01-01T00:00:00Z")
        self.assertIsNone(snap["metrics"][0]["higherIsBetter"])
        self.assertEqual(snap["rankings"]["frame_time"], [])
        self.assertIsNone(snap["perMetricWinners"]["frame_time"]["raw"])
        self.assertNotIn("runs", snap["baseline"]["metrics"]["frame_time"])


class ClassificationAndReferenceTests(unittest.TestCase):
    def test_harness_names(self) -> None:
        for name in ("compile_runtime", "Benchmark_cpu", "command 2_memory", "unit_test_runtime"):
            self.assertEqual(collector.classify_kind(name, "worker"), "harness", name)
        self.assertEqual(collector.classify_kind("simulation_fps", "worker"), "target")
        self.assertEqual(collector.classify_kind("benchmark_integrity", "agent"), "quality")

    def test_units_from_names(self) -> None:
        self.assertEqual(collector.infer_unit("simulation_fps"), "fps")
        self.assertEqual(collector.infer_unit("MatMul(M=4096)_triton_tflops"), "TFLOPS")
        self.assertEqual(collector.infer_unit("latency_ms"), "ms")
        self.assertIsNone(collector.infer_unit("score"))

    def test_the_lead_metric_is_the_most_important_target_never_a_reference(self) -> None:
        defs = {
            "cublas_ms": {"kind": "target", "role": "reference", "importance": "high", "higherIsBetter": False},
            "wall_ms": {"kind": "target", "importance": "medium", "higherIsBetter": False},
            "rtfx": {"kind": "target", "importance": "high", "higherIsBetter": True},
            "judge": {"kind": "quality", "importance": "high", "higherIsBetter": True},
        }
        versions = [{"version": 1, "label": "v1", "metrics": {"rtfx": {"pctBetter": 10.0}, "wall_ms": {"pctBetter": 5.0}}}]
        winners = {k: {"raw": {"version": 1, "label": "v1", "pctBetter": 10.0}} for k in ("rtfx", "wall_ms", "cublas_ms")}
        lines = collector.best_lines(defs, versions, winners, None)
        self.assertEqual(lines["metric"], "rtfx")
        # A more important target with no direction cannot lead: it has no ranking or winner.
        defs = dict({"der": {"kind": "target", "importance": "high", "higherIsBetter": None}}, **defs)
        self.assertEqual(collector.best_lines(defs, versions, winners, None)["metric"], "rtfx")
        self.assertIn("best version on rtfx", lines["lede"])

    def test_units_from_real_run_names(self) -> None:
        # NeMo's metrics: a leading unit before "per", and a bare "s" at the end.
        self.assertEqual(collector.infer_unit("ms_per_chunk"), "ms")
        self.assertEqual(collector.infer_unit("proc_wall_s"), "s")
        self.assertEqual(collector.infer_unit("wall_sec"), "s")
        self.assertEqual(collector.infer_unit("tokens_per_s"), "tokens/s")
        self.assertEqual(collector.infer_unit("decode_tokens_per_s"), "tokens/s")
        self.assertEqual(collector.infer_unit("mb_per_s"), "MB/s")
        for name, unit in (("frames_per_s", "frames/s"), ("images_per_sec", "images/s"), ("requests_per_sec", "requests/s"),
                           ("samples_per_s", "samples/s"), ("throughput_mb_per_s", "MB/s"), ("tokens_s", "tokens/s"), ("mb_s", None),
                           ("items_s", None), ("widgets_per_s", None), ("decode_ms_per_token", "ms"), ("wall_s_per_iter", "s"), ("latency ms", "ms"), ("", None), ("_", None),
                           ("time_per_iter_ms", "ms"), ("latency_per_token_us", "\u00b5s"), ("energy_per_op_ns", "ns"), ("bytes_per_step_mb", "MB"),
                           ("gpu_memory_per_batch_gb", "GB"), ("tokens_per_second", "tokens/s"), ("requests_per_second", "requests/s"), ("tok_s", "tokens/s"),
                           ("throughput_s", None), ("tflops_s", None), ("gflops_s", None), ("qps_s", None), ("fps_s", None),
                           ("gflops_per_s", None), ("tflops_per_s", None),
                           ("decode_tok_s", "tokens/s"), ("throughput_tok_s", "tokens/s"), ("ttft_s", "s"), ("epoch_s", "s"), ("inference_s", "s"), ("iters_s", None), ("req_s", None), ("bytes_s", None),
                           ("wall_time_s", "s"), ("elapsed_sec", "s"), ("prefill_tok_s", "tokens/s"), ("tok_per_s", "tokens/s"), ("x_per_s_per", None),
                           ("tokens_per_s_per_gpu", None), ("samples_per_sec_per_gpu", None), ("req_per_s_per_node", None)):
            self.assertEqual(collector.infer_unit(name), unit, name)
        for name in ("der_long", "rtfx", "speaker_prob_parity_safety", "tokens_per_step"):
            self.assertIsNone(collector.infer_unit(name), name)

    def test_reference_pairs(self) -> None:
        names = ["MatMul_triton_tflops", "MatMul_cublas_tflops", "MatMul_triton_ms", "MatMul_cublas_ms", "simulation_fps"]
        pairs = collector.find_references(names)
        self.assertIn({"target": "MatMul_triton_tflops", "reference": "MatMul_cublas_tflops"}, pairs)
        self.assertIn({"target": "MatMul_triton_ms", "reference": "MatMul_cublas_ms"}, pairs)
        self.assertFalse(any(p["target"] == "simulation_fps" for p in pairs))

    def test_quartiles_are_falcons_never_the_collectors(self) -> None:
        # Falcon returns q1, median and q3 on each compared cell; the collector computes none of its own from the runs.
        payloads = collector.load_from_dir(str(FIXTURES))
        cell = next(m for row in payloads["comparison"]["versions"] if row.get("versionNumber") == 1 for m in row["metrics"] if m["name"] == "latency_ms")
        cell.update(q1=7.1, median=7.2, q3=7.3)
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        stat = next(v for v in snap["versions"] if v["version"] == 1)["metrics"]["latency_ms"]
        self.assertTrue(stat["runs"], "the version keeps its runs to draw")
        self.assertEqual((stat["q1"], stat["median"], stat["q3"]), (7.1, 7.2, 7.3))
        for k in ("q1", "median", "q3"):
            cell.pop(k)
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        stat = next(v for v in snap["versions"] if v["version"] == 1)["metrics"]["latency_ms"]
        self.assertTrue(stat["runs"])
        self.assertFalse({"q1", "median", "q3"} & set(stat), "no falcon quartiles, so none at all")
        self.assertTrue(snap["provenance"]["quartilesSent"], "the other cells carry the keys, so this CLI sends quartiles")
        for row in payloads["comparison"]["versions"]:
            for m in row["metrics"]:
                for k in ("q1", "median", "q3"):
                    m.pop(k, None)
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        self.assertFalse(snap["provenance"]["quartilesSent"], "no cell has the keys: a CLI before 1.1.25")

    def test_reference_ratio_in_snapshot(self) -> None:
        def obs(group, name, value, higher):
            return {"observationGroupId": group, "metricName": name, "value": value, "higherIsBetter": higher, "createdAt": "2026-01-01T00:00:00Z"}
        stats = lambda group, name, mean: {"observationGroupId": group, "metricId": name, "metricName": name, "mean": mean, "min": mean, "max": mean, "count": 1}
        payloads = {
            "run": {"id": "r", "projectId": "p", "baselineGroupId": "gb"},
            "versions": [{"id": "v", "versionNumber": 1, "observationGroupId": "g1", "lifecycle": "completed", "executionStatus": "success"}],
            "metrics": [stats("gb", "k_triton_ms", 8.0), stats("gb", "k_cublas_ms", 6.0), stats("g1", "k_triton_ms", 5.0), stats("g1", "k_cublas_ms", 6.0)],
            "observations": [obs("gb", "k_triton_ms", 8.0, False), obs("gb", "k_cublas_ms", 6.0, False), obs("g1", "k_triton_ms", 5.0, False), obs("g1", "k_cublas_ms", 6.0, False)],
            "experiments": [],
        }
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        # Lower is better, so the ratio is reference / target: above 1 means faster than the reference.
        self.assertAlmostEqual(snap["versions"][0]["metrics"]["k_triton_ms"]["vsReference"]["ratio"], 1.2)
        self.assertAlmostEqual(snap["baseline"]["metrics"]["k_triton_ms"]["vsReference"]["ratio"], 0.75)
        roles = {m["key"]: m.get("role") for m in snap["metrics"]}
        self.assertEqual(roles["k_cublas_ms"], "reference")


class FalconComparisonTests(unittest.TestCase):
    """Verdicts and intervals come from `discovery compare` (falcon); the collector computes none."""

    def payloads(self):
        compared = {
            "metricId": "m-fps", "name": "simulation_fps", "value": 120.0, "readings": 5,
            "improvementPct": 20.0, "improvementLowPct": 12.5, "improvementHighPct": 27.5, "verdict": "better",
            "recommendedReadings": None, "recommendedReadingsReason": "settled", "spreadPct": 3.1,
        }
        return {
            "run": {"id": "run-1", "projectId": "p-1", "baselineGroupId": "g-base"},
            "versions": [{"id": "v-1", "versionNumber": 1, "versionSha": "sha-1", "observationGroupId": "g-1", "lifecycle": "completed", "executionStatus": "success"}],
            "metrics": [
                {"observationGroupId": "g-base", "metricId": "m-fps", "metricName": "simulation_fps", "mean": 100.0, "min": 98.0, "max": 102.0, "count": 5},
                {"observationGroupId": "g-1", "metricId": "m-fps", "metricName": "simulation_fps", "mean": 120.0, "min": 117.0, "max": 123.0, "count": 5},
            ],
            "observations": None,
            "experiments": [],
            "comparison": {
                "baselineSha": "sha-0",
                "bestVersion": None,
                "metrics": [{"id": "m-fps", "name": "simulation_fps", "unit": "fps", "higherIsBetter": True}],
                "versions": [
                    {"sha": "sha-0", "isBaseline": True, "metrics": [dict(compared, value=100.0, readings=5, improvementPct=None, improvementLowPct=None, improvementHighPct=None, verdict=None)]},
                    {"sha": "sha-1", "isBaseline": False, "versionNumber": 1, "metrics": [compared],
                     "overallVerdict": {"verdict": "better", "improvementLowPct": 12.5, "improvementHighPct": 27.5, "provisional": False}},
                ],
            },
        }

    def test_falcons_points_change_is_passed_through(self) -> None:
        payloads = self.payloads()
        payloads["comparison"]["versions"][1]["metrics"][0]["improvementPoints"] = 0.12
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        self.assertEqual(snap["versions"][0]["metrics"]["simulation_fps"]["vsBaseline"]["improvementPoints"], 0.12)

    def test_an_ai_score_has_no_times_better(self) -> None:
        # A score is an opinion of the code, so no page can print "1.43x worse" for it; its % stays falcon's.
        snap = collector.build_snapshot(collector.load_from_dir(str(FIXTURES)), collected_at="2026-01-01T00:00:00Z")
        quality = [m["key"] for m in snap["metrics"] if m["kind"] == "quality"]
        self.assertTrue(quality, "the fixture needs an AI Metric")
        for v in snap["versions"]:
            for key in quality:
                stat = v["metrics"].get(key)
                if stat:
                    self.assertIsNone(stat["timesBetter"], (v["label"], key))
        for key in quality:
            for row in snap["rankings"].get(key, []):
                self.assertIsNone(row["timesBetter"], key)
            for pick in (snap["perMetricWinners"].get(key) or {}).values():
                if isinstance(pick, dict):
                    self.assertIsNone(pick.get("timesBetter"), key)
        # A measured metric keeps its ratio.
        self.assertAlmostEqual(snap["versions"][0]["metrics"]["latency_ms"]["timesBetter"], 1.25)

    def test_maps_falcons_verdict_and_interval(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="2026-01-01T00:00:00Z")
        metric = snap["versions"][0]["metrics"]["simulation_fps"]
        self.assertEqual(metric["pctBetter"], 20.0)
        self.assertAlmostEqual(metric["timesBetter"], 1.2)
        self.assertEqual(metric["vsBaseline"], {
            "source": "falcon", "verdict": "better", "improvementPct": 20.0, "improvementPoints": None, "ciLowPct": 12.5, "ciHighPct": 27.5,
            "readings": 5, "recommendedReadings": None, "recommendedReadingsReason": "settled", "spreadPct": 3.1,
        })
        self.assertEqual(snap["versions"][0]["overallVerdict"]["verdict"], "better")
        self.assertEqual(snap["baseline"]["readings"], {"simulation_fps": 5})
        definition = snap["metrics"][0]
        self.assertTrue(definition["higherIsBetter"])
        self.assertEqual(definition["unit"], "fps")
        self.assertIn("discovery compare", snap["provenance"]["verdictsSource"])

    def test_stats_come_from_compare_when_it_carries_them(self) -> None:
        # CLI 1.1.17 adds falcon's summary to each compared metric; it replaces the CLI's own --stats.
        payloads = self.payloads()
        base, version = (row["metrics"][0] for row in payloads["comparison"]["versions"])
        base.update(mean=101.0, min=97.0, max=104.0, std=2.5, ste=1.1)
        version.update(mean=121.0, min=116.0, max=124.0, std=None, ste=None)
        # The CLI's own std must not survive beside falcon's mean.
        payloads["metrics"][1].update(std=9.0, ste=4.0)
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        self.assertEqual(snap["baseline"]["metrics"]["simulation_fps"],
                         {"mean": 101.0, "min": 97.0, "max": 104.0, "count": 5, "std": 2.5, "ste": 1.1})
        metric = snap["versions"][0]["metrics"]["simulation_fps"]
        self.assertEqual((metric["mean"], metric["min"], metric["max"], metric["count"]), (121.0, 116.0, 124.0, 5))
        self.assertNotIn("std", metric)
        self.assertIn("compare", snap["provenance"]["statsSource"])

    def test_stats_fall_back_to_metrics_stats_on_older_clis(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual(snap["versions"][0]["metrics"]["simulation_fps"]["mean"], 120.0)
        self.assertEqual(snap["baseline"]["metrics"]["simulation_fps"]["mean"], 100.0)
        self.assertIn("--stats", snap["provenance"]["statsSource"])

    def test_fixture_snapshot_carries_falcons_verdict_words(self) -> None:
        payloads = collector.load_from_dir(str(FIXTURES))
        snap = collector.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        verdicts = {
            (v["label"], name): m["vsBaseline"]["verdict"]
            for v in snap["versions"] for name, m in v["metrics"].items() if m.get("vsBaseline")
        }
        self.assertTrue(verdicts)
        self.assertTrue(set(verdicts.values()) <= set(collector.VERDICTS))

    def two_versions(self, first: dict, second: dict, baseline: bool = True) -> dict:
        """Two versions of a higher-is-better metric with the given falcon rows; v1 has the higher mean."""
        payloads = self.payloads()
        payloads["versions"].append({"id": "v-2", "versionNumber": 2, "versionSha": "sha-2", "observationGroupId": "g-2", "lifecycle": "completed", "executionStatus": "success"})
        payloads["metrics"].append({"observationGroupId": "g-2", "metricId": "m-fps", "metricName": "simulation_fps", "mean": 110.0, "min": 105.0, "max": 115.0, "count": 5})
        base_row = payloads["comparison"]["versions"][0]
        rows = [{"sha": "sha-1", "isBaseline": False, "versionNumber": 1, "metrics": [first]},
                {"sha": "sha-2", "isBaseline": False, "versionNumber": 2, "metrics": [second]}]
        payloads["comparison"]["versions"] = ([base_row] if baseline else []) + rows
        return payloads

    def falcon_row(self, pct, verdict):
        return {"metricId": "m-fps", "name": "simulation_fps", "readings": 5, "improvementPct": pct,
                "improvementLowPct": None if pct is None else pct - 4, "improvementHighPct": None if pct is None else pct + 4,
                "verdict": verdict, "recommendedReadings": None, "recommendedReadingsReason": None, "spreadPct": 2.0}

    def test_worse_and_noise_verdicts_are_falcons(self) -> None:
        snap = collector.build_snapshot(self.two_versions(self.falcon_row(-8.0, "worse"), self.falcon_row(1.0, "noise")), collected_at="2026-01-01T00:00:00Z")
        verdicts = [v["metrics"]["simulation_fps"]["vsBaseline"]["verdict"] for v in snap["versions"]]
        self.assertEqual(verdicts, ["worse", "noise"])

    def test_ranking_follows_falcons_change_not_the_mean(self) -> None:
        # v1 has the higher mean, but falcon (median aggregator, say) puts v2 ahead.
        snap = collector.build_snapshot(self.two_versions(self.falcon_row(-8.0, "worse"), self.falcon_row(1.0, "noise")), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["version"] for row in snap["rankings"]["simulation_fps"]], [2, 1])
        self.assertEqual(snap["perMetricWinners"]["simulation_fps"]["raw"]["version"], 2)

    def test_one_metric_ranks_as_the_web_ui_falcons_better_verdict_first(self) -> None:
        # The Web UI's compared version on one metric (artemis-ui versions.index.tsx): significantly improved first, then the
        # largest change. v1's +12% is within noise, v2's +6% is significant, so v2 leads; ranking by change alone picks v1.
        snap = collector.build_snapshot(self.two_versions(self.falcon_row(12.0, "noise"), self.falcon_row(6.0, "better")), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["version"] for row in snap["rankings"]["simulation_fps"]], [2, 1])
        self.assertEqual(snap["perMetricWinners"]["simulation_fps"]["raw"]["version"], 2)
        self.assertEqual([row["verdict"] for row in snap["rankings"]["simulation_fps"]], ["better", "noise"])

    def test_a_pending_change_ranks_after_a_significant_one_and_a_tie_keeps_version_order(self) -> None:
        pending = collector.build_snapshot(self.two_versions(self.falcon_row(20.0, "pending"), self.falcon_row(3.0, "better")), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["version"] for row in pending["rankings"]["simulation_fps"]], [2, 1])
        tie = collector.build_snapshot(self.two_versions(self.falcon_row(6.0, "better"), self.falcon_row(6.0, "better")), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["version"] for row in tie["rankings"]["simulation_fps"]], [1, 2], "a tie keeps version order, as the Web UI's")

    def test_without_a_baseline_row_no_change_is_claimed(self) -> None:
        empty = self.falcon_row(None, None)
        snap = collector.build_snapshot(self.two_versions(empty, dict(empty), baseline=False), collected_at="2026-01-01T00:00:00Z")
        for version in snap["versions"]:
            metric = version["metrics"]["simulation_fps"]
            self.assertIsNone(metric["pctBetter"])
            self.assertIsNone(metric["vsBaseline"])
        # With no falcon number, nothing is ranked and the winner says why.
        self.assertEqual(snap["rankings"]["simulation_fps"], [])
        winner = snap["perMetricWinners"]["simulation_fps"]
        self.assertIsNone(winner["raw"])
        self.assertIn("no change", winner["reason"])
        self.assertEqual(winner["unranked"], ["v1", "v2"])

    def test_a_version_without_falcons_number_is_not_ranked(self) -> None:
        # v1 has the higher mean but no falcon change; it must not outrank v2, which falcon says is worse.
        snap = collector.build_snapshot(self.two_versions(self.falcon_row(None, None), self.falcon_row(-30.0, "worse")), collected_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["version"] for row in snap["rankings"]["simulation_fps"]], [2])
        winner = snap["perMetricWinners"]["simulation_fps"]
        self.assertEqual(winner["raw"]["pctBetter"], -30.0)
        self.assertEqual(winner["unranked"], ["v1"])

    def test_an_old_cli_gets_an_upgrade_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "artemis"
            # CLI 1.0.11 prints the parent's help and exits 0 for an unknown subcommand.
            fake.write_text("#!/bin/sh\necho 'Usage: artemis discovery [command]'\n", encoding="utf-8")
            fake.chmod(0o755)
            with self.assertRaises(RuntimeError) as caught:
                collector.fetch_comparison("run-1", cli=str(fake))
            self.assertIn("1.1.14", str(caught.exception))
            self.assertIn("cli-setup", str(caught.exception))

    def fake_cli(self, tmp: str, script: str) -> str:
        fake = Path(tmp) / "artemis"
        fake.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        fake.chmod(0o755)
        return str(fake)

    def test_other_compare_failures_pass_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # A CLI that has compare, failing for another reason (auth).
            cli = self.fake_cli(tmp, 'case "$*" in *--help*) printf "Usage:\\n  artemis discovery compare <run-id> [flags]\\n";; *) echo "401 Unauthorized" >&2; exit 3;; esac\n')
            with self.assertRaises(RuntimeError) as caught:
                collector.fetch_comparison("run-1", cli=cli)
            self.assertIn("401 Unauthorized", str(caught.exception))
            self.assertNotIn("1.1.14", str(caught.exception))

    def test_project_mode_stops_on_an_old_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli = self.fake_cli(tmp, "echo 'Usage: artemis discovery [command]'\n")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = collector.main(["--project", "p-1", "--cli", cli])
            self.assertEqual(code, 1)
            self.assertIn("1.1.14", err.getvalue())

    def test_from_dir_needs_falcons_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("run.json", "versions.json", "metrics.json", "experiments.json"):
                shutil.copy(FIXTURES / name, Path(tmp) / name)
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = collector.main(["--from-dir", tmp])
            self.assertEqual(code, 1)
            self.assertIn("comparison.json", err.getvalue())

    def test_from_dir_with_a_compare_too_old_to_name_falcons_best_still_gives_a_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("run.json", "versions.json", "metrics.json", "observations.json", "experiments.json"):
                shutil.copy(FIXTURES / name, Path(tmp) / name)
            comparison = json.loads((FIXTURES / "comparison.json").read_text())
            del comparison["bestVersion"]
            (Path(tmp) / "comparison.json").write_text(json.dumps(comparison))
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
                code = collector.main(["--from-dir", tmp])
            self.assertEqual(code, 0)
            snap = json.loads(out.getvalue())
            self.assertIsNone(snap["webUiBest"])
            self.assertIn("1.1.20", snap["bestLines"]["lede"])

    def test_project_mode_collects_every_run_when_compare_does_not_name_falcons_best(self) -> None:
        # A CLI from 1.1.14 to 1.1.19 has compare but no bestVersion: each run gets its page with no Best, none is skipped.
        payloads = collector.load_from_dir(str(FIXTURES))
        del payloads["comparison"]["bestVersion"]
        runs = [{"id": "run-a", "createdAt": "1"}, {"id": "run-b", "createdAt": "2"}]
        with mock.patch.object(collector, "compare_available", return_value=True), \
             mock.patch.object(collector, "list_project_runs", return_value=runs), \
             mock.patch.object(collector, "fetch_cli", side_effect=lambda *a, **k: copy.deepcopy(payloads)), \
             contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            code = collector.main(["--project", "p-1"])
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual((len(result["runs"]), result["skipped"]), (2, []))
        self.assertTrue(all(r["webUiBest"] is None for r in result["runs"]))

    def test_project_mode_skips_a_run_with_nothing_measured_for_that_reason(self) -> None:
        # Try 8: a cancelled run was skipped as "--budget-metric model_bytes: not a target metric"; the truth is it scored nothing.
        good = collector.load_from_dir(str(FIXTURES))
        empty = copy.deepcopy(good)
        empty["metrics"] = [r for r in empty["metrics"] if r.get("observationGroupId") == empty["run"].get("baselineGroupId")]
        empty["comparison"]["versions"] = [r for r in empty["comparison"]["versions"] if r.get("isBaseline")]
        runs = [{"id": "run-a", "createdAt": "1", "status": "cancelled"}, {"id": "run-b", "createdAt": "2", "status": "completed"}]
        with mock.patch.object(collector, "compare_available", return_value=True), \
             mock.patch.object(collector, "list_project_runs", return_value=runs), \
             mock.patch.object(collector, "fetch_cli", side_effect=[empty, good]), \
             contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            code = collector.main(["--project", "p-1", "--budget-metric", "model_bytes"])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["skipped"][0], {"id": "run-a", "status": "cancelled", "reason": "no measured version"})

    def test_project_mode_carries_each_reference_into_every_run(self) -> None:
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            scored, out = Path(tmp) / "rival.json", Path(tmp) / "project.json"
            scored.write_text(json.dumps({"latency_ms": 9.5}), encoding="utf-8")
            with mock.patch.object(collector, "compare_available", return_value=True), \
                 mock.patch.object(collector, "list_project_runs", return_value=[{"id": "r-1", "createdAt": "2026-01-01"}]), \
                 mock.patch.object(collector, "fetch_cli", side_effect=lambda *a, **k: collector.load_from_dir(str(FIXTURES))), \
                 contextlib.redirect_stderr(io.StringIO()):
                code = collector.main(["--project", "p-1", "--reference", f"label=rival,file={scored}", "--output", str(out)])
            self.assertEqual(code, 0)
            [run] = json.loads(out.read_text(encoding="utf-8"))["runs"]
            self.assertEqual([r["label"] for r in run["externalReferences"]], ["rival"])
            err = io.StringIO()
            with mock.patch.object(collector, "compare_available", return_value=True), contextlib.redirect_stderr(err):
                self.assertEqual(collector.main(["--project", "p-1", "--reference", "file=x.json"]), 2, "a bad spec stops before any run is read")
            self.assertIn("label=NAME", err.getvalue())

    def test_a_missing_reference_file_is_a_message_not_a_traceback(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = collector.main(["--from-dir", str(FIXTURES), "--reference", "label=rival,file=/no/such/file.json"])
        self.assertEqual(code, 2)
        self.assertIn("file.json", err.getvalue())

    def test_a_bad_pareto_axis_is_a_message_not_a_traceback(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = collector.main(["--from-dir", str(FIXTURES), "--pareto", "nosuch,other"])
        self.assertEqual(code, 2)
        self.assertIn("Pareto", err.getvalue())

    def test_no_statistics_are_computed_here(self) -> None:
        source = (SCRIPTS / "collect_discovery.py").read_text(encoding="utf-8")
        for name in ("betainc", "t_quantile", "welch", "t_two_sided_p", "pct_better"):
            self.assertNotIn(name, source)


class ProjectNameTests(unittest.TestCase):
    def fake_cli(self, tmp: str, script: str) -> str:
        fake = Path(tmp) / "artemis"
        fake.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        fake.chmod(0o755)
        return str(fake)

    def test_reads_project_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli = self.fake_cli(tmp, 'case "$*" in *"project get p-1"*) echo \'{"id":"p-1","name":"From get"}\';; *) echo "unexpected: $*" >&2; exit 9;; esac\n')
            self.assertEqual(collector.project_name("p-1", cli=cli), "From get")

    def test_an_old_cli_without_project_get_falls_back_to_the_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli = self.fake_cli(tmp, 'case "$*" in *"project get"*) echo \'Error: unknown command "get" for "artemis project"\' >&2; exit 1;; *"project list"*) echo \'{"docs":[{"id":"p-2","name":"Other"},{"id":"p-1","name":"From list"}]}\';; esac\n')
            self.assertEqual(collector.project_name("p-1", cli=cli), "From list")

    def test_a_get_answer_for_another_project_is_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cli = self.fake_cli(tmp, 'case "$*" in *"project get"*) echo \'{"id":"p-9","name":"Wrong"}\';; *"project list"*) echo \'{"docs":[{"id":"p-1","name":"Right"}]}\';; esac\n')
            self.assertEqual(collector.project_name("p-1", cli=cli), "Right")

    def test_the_cache_saves_a_second_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "calls"
            cli = self.fake_cli(tmp, f'echo "$*" >> {log}\necho \'{{"id":"p-1","name":"Cached"}}\'\n')
            cache: dict[str, str | None] = {}
            self.assertEqual(collector.project_name("p-1", cli=cli, cache=cache), "Cached")
            self.assertEqual(collector.project_name("p-1", cli=cli, cache=cache), "Cached")
            self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 1)

    def test_no_project_id_makes_no_call(self) -> None:
        self.assertIsNone(collector.project_name(None, cli="/nonexistent/artemis"))


class GateMetricTests(unittest.TestCase):
    """--gate-metric: a version that reads 0 on the run's own 0/1 gate has no usable readings, so it is never ranked, a winner or on the front."""

    @staticmethod
    def payloads() -> dict:
        payloads = collector.load_from_dir(str(FIXTURES))
        for group in sorted({m["observationGroupId"] for m in payloads["metrics"]}):
            payloads["metrics"].append({"metricId": "m-gate", "metricName": "gate_ok", "observationGroupId": group,
                                        "mean": 0.0 if group == "obs-2" else 1.0, "min": 0.0, "max": 1.0, "count": 1})
        return payloads

    def test_a_gate_failure_is_never_ranked_a_winner_or_on_the_front(self) -> None:
        plain = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", pareto_axes=["latency_ms", "quality_score"], gate_metric="none")
        self.assertEqual(plain["perMetricWinners"]["latency_ms"]["raw"]["label"], "v2", "without the flag v2 wins, so the test means something")
        self.assertIsNone(plain["gate"])
        snap = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", pareto_axes=["latency_ms", "quality_score"], gate_metric="gate_ok")
        self.assertEqual(snap["gate"], {"metric": "gate_ok", "failed": ["v2"]})
        self.assertEqual([v["label"] for v in snap["versions"] if v["gateFailed"]], ["v2"])
        self.assertNotIn("v2", [r["label"] for r in snap["rankings"]["latency_ms"]])
        self.assertEqual(snap["perMetricWinners"]["latency_ms"]["raw"]["label"], "v4")
        self.assertNotIn(2, [p["version"] for p in snap["pareto"]["points"]])
        self.assertFalse(any("v2" in labels for row in snap["fronts"].values() for labels in row.values()), "no stored front holds a gate failure")
        self.assertNotIn(2, [row["bestVersion"] for row in snap["runningBest"]["latency_ms"]])
        v2 = next(v for v in snap["versions"] if v["version"] == 2)
        self.assertIsNotNone(v2["metrics"]["latency_ms"]["mean"], "the snapshot keeps its raw readings; only the picks leave it out")

    def test_a_gated_web_ui_best_is_named_and_not_led_with(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", gate_metric="gate_ok")
        self.assertEqual(snap["webUiBest"]["label"], "v2", "the Web UI's own Best is reported as it is")
        self.assertEqual(snap["bestLines"]["label"], "v4")
        self.assertIn("Best is v2, by Composite score, but it failed the gate (gate_ok = 0)", snap["bestLines"]["lede"])
        self.assertNotIn("no change on", snap["bestLines"]["lede"])

    def test_the_snapshot_draws_its_trade_off_from_versions_that_passed_the_gate(self) -> None:
        from unittest import mock
        seen = []
        real = collector.drawable_tradeoff
        with mock.patch.object(collector, "drawable_tradeoff", side_effect=lambda defs, usable: seen.append([v["label"] for v in usable]) or real(defs, usable)):
            collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", gate_metric="gate_ok")
        self.assertEqual(len(seen), 1)
        self.assertNotIn("v2", seen[0], "the gate failure is not counted")

    def test_the_tradeoff_metrics_count_only_versions_that_passed_the_gate(self) -> None:
        plain = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", gate_metric="none")
        gated = collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", gate_metric="gate_ok")
        count = lambda s, k: sum(1 for v in s["versions"] if not v.get("gateFailed") and ((v["metrics"].get(k) or {}).get("vsBaseline") or {}).get("improvementPct") is not None)
        for snap in (plain, gated):
            for key in snap["tradeoffMetrics"]:
                self.assertGreaterEqual(count(snap, key), 2, key)
                self.assertIsNotNone(next(m for m in snap["metrics"] if m["key"] == key)["higherIsBetter"])
            self.assertTrue(all(count(snap, m["key"]) < 2 or m["higherIsBetter"] is None or m["kind"] != "target" or m["key"] in snap["tradeoffMetrics"] for m in snap["metrics"]))

    def test_an_unknown_gate_metric_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            collector.build_snapshot(self.payloads(), collected_at="2026-09-02T00:00:00+00:00", gate_metric="no_such_metric")


class RunGateTests(unittest.TestCase):
    """With no --gate-metric the run's own gate still applies: a failed version that reads 0 on every error rate wins nothing."""

    @staticmethod
    def payloads(*gates: str) -> dict:
        payloads = collector.load_from_dir(str(FIXTURES))
        for name in gates:
            for group in sorted({m["observationGroupId"] for m in payloads["metrics"]}):
                payloads["metrics"].append({"metricId": f"m-{name}", "metricName": name, "observationGroupId": group,
                                            "mean": 0.0 if group == "obs-2" else 1.0, "min": 0.0, "max": 1.0, "count": 1})
        return payloads

    @staticmethod
    def slots(snap: dict) -> set:
        return {(name, kind) for name, won in snap["perMetricWinners"].items() for kind in ("raw", "eligible") if (won.get(kind) or {}).get("label") == "v2"}

    def snapshot(self, *gates: str, **flags) -> dict:
        with contextlib.redirect_stderr(io.StringIO()):
            return collector.build_snapshot(self.payloads(*gates), collected_at="2026-09-02T00:00:00+00:00", **flags)

    def test_a_version_that_failed_the_runs_gate_wins_no_slot(self) -> None:
        self.assertTrue(self.slots(self.snapshot("eligible", gate_metric="none")), "ungated, v2 wins a slot, so the test means something")
        snap = self.snapshot("eligible")
        self.assertEqual(snap["gate"], {"metric": "eligible", "failed": ["v2"]})
        self.assertEqual(self.slots(snap), set())
        self.assertNotIn("v2", [row["label"] for rows in snap["rankings"].values() for row in rows])
        self.assertNotEqual(snap["bestLines"]["label"], "v2")

    def test_the_collector_says_which_gate_it_applied(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            collector.build_snapshot(self.payloads("eligible"), collected_at="2026-09-02T00:00:00+00:00")
        self.assertIn("gating on the run's own eligible metric", err.getvalue())

    def test_two_gate_names_apply_neither(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            snap = collector.build_snapshot(self.payloads("eligible", "gate_ok"), collected_at="2026-09-02T00:00:00+00:00")
        self.assertIsNone(snap["gate"])
        self.assertIn("pass --gate-metric", err.getvalue())

    def test_a_metric_not_named_as_a_gate_is_not_one(self) -> None:
        self.assertIsNone(self.snapshot("accuracy_ok")["gate"], "0/1 readings alone don't make a gate")

    def test_a_gate_name_with_readings_past_1_is_not_one(self) -> None:
        payloads = self.payloads("eligible")
        for m in payloads["metrics"]:
            if m["metricName"] == "eligible" and m["mean"] == 1.0:
                m["mean"] = 3.0
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(collector.build_snapshot(payloads, collected_at="2026-09-02T00:00:00+00:00")["gate"])

    def test_the_flag_names_another_gate_or_turns_it_off(self) -> None:
        self.assertEqual(self.snapshot("eligible", "gate_ok", gate_metric="gate_ok")["gate"]["metric"], "gate_ok")
        self.assertIsNone(self.snapshot("eligible", gate_metric="none")["gate"])


class SizeCapTests(unittest.TestCase):
    """A run's brief can state a file-size cap; the snapshot carries it only when the brief states exactly one."""

    def test_the_cap_is_read_in_any_common_form(self) -> None:
        for brief, size in [("whose GGUF file is at most 1,319,830,496 bytes. That is", 1319830496), ("Keep it under 1.3 GB.", 1_300_000_000),
                            ("no more than 500 MiB", 500 * 2**20), ("Eligible if: bytes <= 1,319,830,496", 1319830496), ("≤ 2 GB", 2_000_000_000)]:
            with self.subTest(brief=brief):
                self.assertEqual(collector.size_cap(brief)["bytes"], size)
        self.assertEqual(collector.size_cap("is at most 1,319,830,496 bytes.")["text"], "at most 1,319,830,496 bytes", "the phrase it was read from")
        self.assertEqual(collector.size_cap("at most 1,319,830,496 bytes; bytes ≤ 1,319,830,496")["bytes"], 1319830496, "the same cap twice is one cap")

    def test_no_cap_two_caps_or_a_rate_is_none(self) -> None:
        for brief in ("Make it faster.", None, "at most 1,000,000 bytes, or bytes <= 2,000,000", "stream at under 5 MB/s"):
            with self.subTest(brief=brief):
                self.assertIsNone(collector.size_cap(brief))

    def test_a_trade_off_draws_directed_targets_compared_on_two_usable_versions(self) -> None:
        d = lambda higher=False, kind="target": {"kind": kind, "higherIsBetter": higher}
        defs = {"two": d(), "one": d(), "undirected": d(None), "judged": d(True, "quality")}
        cmp = lambda *keys: {"metrics": {k: {"vsBaseline": {"improvementPct": 1.0}} for k in keys}}
        usable = [cmp("two", "one", "undirected", "judged"), cmp("two", "undirected", "judged"), {"metrics": {"one": {"vsBaseline": {"improvementPct": None}}}}]
        self.assertEqual(collector.drawable_tradeoff(defs, usable), ["two"])
        self.assertEqual(collector.drawable_tradeoff(defs, usable[:1]), [], "one compared version is not a trade-off")

    def test_the_budget_is_the_only_byte_metric_or_the_named_one(self) -> None:
        cap = {"bytes": 1_300_000_000}
        d = lambda unit, kind="target": {"kind": kind, "unit": unit, "higherIsBetter": False}
        one = {"model_size_mb": d("MB"), "pooled_wer": d(None)}
        self.assertEqual(collector.budget_metric(one, cap), "model_size_mb", "the run's only byte metric")
        self.assertIsNone(collector.budget_metric(one, None), "no stated cap: no budget")
        two = dict(one, rss_mb=d("MB"))
        self.assertIsNone(collector.budget_metric(two, cap), "two byte metrics and none named: no budget, never a guess")
        self.assertEqual(collector.budget_metric(two, cap, "model_size_mb"), "model_size_mb", "--budget-metric names it")
        for bad in ("pooled_wer", "no_such_metric"):
            with self.subTest(named=bad), self.assertRaises(ValueError):
                collector.budget_metric(two, cap, bad)
        control = {"seed_size_mb": dict(d("MB"), role="reference")}
        self.assertIsNone(collector.budget_metric(control, cap), "a reference control is never the budget")
        self.assertIsNone(collector.budget_metric({"fps": d("fps")}, cap), "no byte metric: the cap stays a sentence")

    def test_of_several_byte_metrics_the_one_in_the_caps_unit_is_the_budget(self) -> None:
        d = lambda unit: {"kind": "target", "unit": unit, "higherIsBetter": False}
        both = {"model_bytes": d("B"), "model_size_mb": d("MB"), "objective": d(None)}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(collector.budget_metric(both, collector.size_cap("whose GGUF file is at most 1,319,830,496 bytes.")), "model_bytes")
            self.assertEqual(collector.budget_metric(both, collector.size_cap("Keep it under 1.3 GB.")), None, "no metric in GB: no guess")
            self.assertEqual(collector.budget_metric(both, collector.parse_size_cap("1319 MB")), "model_size_mb", "--size-cap's unit counts too")
            self.assertEqual(collector.budget_metric(both, collector.size_cap("Eligible if: bytes <= 1,319,830,496")), "model_bytes")
            given = {"bytes": 1_319_000_000, "text": "1319 MB", "unit": "MB"}  # the unit decides, not the wording
            self.assertEqual(collector.budget_metric(both, given), "model_size_mb", "a cap given as a size alone")
            twice = dict(both, file_bytes=d("bytes"))
            self.assertIsNone(collector.budget_metric(twice, collector.size_cap("at most 1,319,830,496 bytes")), "two in the cap's unit: no guess")
        self.assertIn("applies to model_bytes, the byte metric in the cap's own unit", err.getvalue())

    @staticmethod
    def sized(brief: str, original_mb: float, extra: tuple[str, ...] = ()) -> dict:
        payloads = collector.load_from_dir(str(FIXTURES))
        payloads["run"]["taskDescription"] = brief
        for group in sorted({m["observationGroupId"] for m in payloads["metrics"]}):
            for key in ("model_size_mb",) + extra:
                payloads["metrics"].append({"metricId": "m-" + key, "metricName": key, "observationGroupId": group, "mean": original_mb, "min": original_mb, "max": original_mb, "count": 1})
        return payloads

    def test_an_original_above_or_below_the_cap_still_has_its_budget(self) -> None:
        # The common compression brief starts above its cap: FP16 at 2,600 MB against "at most 1.3 GB".
        for original in (2600.0, 1100.0):
            with self.subTest(original=original):
                snap = collector.build_snapshot(self.sized("The GGUF file must be at most 1.3 GB.", original), collected_at="x")
                size = next(m for m in snap["metrics"] if m["key"] == "model_size_mb")
                self.assertEqual((size.get("role"), size.get("cap"), size["unit"]), ("budget", 1300.0, "MB"), "the cap in the metric's own unit")

    def test_two_byte_metrics_need_the_flag_and_a_rate_is_no_cap(self) -> None:
        two = self.sized("The GGUF file must be at most 1.3 GB.", 2600.0, ("rss_mb",))
        roles = lambda snap: {m["key"]: m.get("role") for m in snap["metrics"] if m["key"] in ("model_size_mb", "rss_mb")}
        self.assertEqual(roles(collector.build_snapshot(copy.deepcopy(two), collected_at="x")), {"model_size_mb": None, "rss_mb": None})
        self.assertEqual(roles(collector.build_snapshot(copy.deepcopy(two), collected_at="x", budget_name="model_size_mb")), {"model_size_mb": "budget", "rss_mb": None})
        rate = collector.build_snapshot(self.sized("Stream it at under 5 MB/s.", 2600.0), collected_at="x")
        self.assertIsNone(rate["run"]["sizeCap"])
        self.assertFalse([m for m in rate["metrics"] if m.get("role") == "budget"])

    def test_two_different_caps_are_named_on_stderr(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            snap = collector.build_snapshot(self.sized("Peak RAM below 8 GB, and a model of at most 1.3 GB.", 2600.0), collected_at="x")
        self.assertIsNone(snap["run"]["sizeCap"])
        self.assertIn("2 different size limits (below 8 GB; at most 1.3 GB), so no size cap is set", err.getvalue())

    def test_common_cap_wordings_are_read_and_a_throughput_is_not(self) -> None:
        for brief, size in [("Size cap: 1.3 GB", 1_300_000_000), ("max 1.3 GB", 1_300_000_000), ("It must fit in 1.3 GB.", 1_300_000_000),
                            ("a maximum of 2 GB", 2_000_000_000), ("capped at 500 MiB", 500 * 2**20), ("a limit of 1 GB", 1_000_000_000)]:
            with self.subTest(brief=brief):
                self.assertEqual(collector.size_cap(brief)["bytes"], size)
        self.assertIsNone(collector.size_cap("a max throughput of 3 GB/s"))

    def test_an_explicit_size_cap_beats_the_brief(self) -> None:
        self.assertEqual(collector.parse_size_cap("1.3 GB"), {"bytes": 1_300_000_000, "text": "--size-cap 1.3 GB", "unit": "GB"})
        for bad in ("1.3", "big", "1.3 GB/s"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                collector.parse_size_cap(bad)
        snap = collector.build_snapshot(self.sized("Make the model small.", 2600.0), collected_at="x", size_cap_given=collector.parse_size_cap("1.3 GB"))
        size = next(m for m in snap["metrics"] if m["key"] == "model_size_mb")
        self.assertEqual((snap["run"]["sizeCap"]["text"], size.get("role"), size.get("cap")), ("--size-cap 1.3 GB", "budget", 1300.0))
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collector.main(["--from-dir", str(FIXTURES), "--size-cap", "huge"]), 2)
        self.assertIn("--size-cap 'huge': give a size with a unit", err.getvalue())

    def test_each_silent_way_to_lose_the_budget_says_so(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            collector.build_snapshot(self.sized("Make the model small.", 2600.0), collected_at="x", budget_name="model_size_mb")
        self.assertIn("--budget-metric model_size_mb has no size cap to apply to: none found in the brief; pass --size-cap", err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            collector.build_snapshot(self.sized("The file must be at most 1.3 GB.", 2600.0, ("rss_mb",)), collected_at="x")
        self.assertIn("the size cap (at most 1.3 GB) could apply to model_size_mb, rss_mb; pass --budget-metric to name one", err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            collector.build_snapshot(self.sized("The file must be at most 1.3 GB.", 2600.0), collected_at="x")
        self.assertEqual(err.getvalue(), "", "one byte metric and one cap: nothing to say")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            collector.build_snapshot(self.sized("Peak RAM below 8 GB, and a model of at most 1.3 GB.", 2600.0), collected_at="x", size_cap_given=collector.parse_size_cap("1.3 GB"))
        self.assertEqual(err.getvalue(), "", "--size-cap given: the brief's limits are not read, so there is no clash to report")

    def test_a_bad_budget_metric_is_a_message_not_a_traceback(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = collector.main(["--from-dir", str(FIXTURES), "--budget-metric", "latency_ms"])
        self.assertEqual(code, 2)
        self.assertIn("--budget-metric latency_ms: not a target metric measured in a byte unit", err.getvalue())


class ExternalReferenceTests(unittest.TestCase):
    """--reference: a model the run's referee scored outside Discovery, carried with its source, never filled in."""

    def test_a_reference_keeps_the_runs_metrics_its_gate_and_its_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scored = Path(tmp) / "handy.json"
            scored.write_text(json.dumps({"latency_ms": 9.5, "eligible": 0, "not_a_metric": 3, "label": "x"}), encoding="utf-8")
            note, fails = Path(tmp) / "SOURCE.md", Path(tmp) / "fails.txt"
            note.write_text("Copy of rig2 /raid/x.json", encoding="utf-8")
            fails.write_text("nonspeech: 23 runaway clips\n", encoding="utf-8")
            payloads = collector.load_from_dir(str(FIXTURES))
            for group in sorted({m["observationGroupId"] for m in payloads["metrics"]}):
                payloads["metrics"].append({"metricId": "m-el", "metricName": "eligible", "observationGroupId": group, "mean": 1.0, "min": 1.0, "max": 1.0, "count": 1})
            specs = collector.parse_reference_specs([f"label=stock Q4_K_M,file={scored},note={note},failures={fails}"])
            snap = collector.build_snapshot(payloads, collected_at="2026-09-02T00:00:00+00:00", gate_metric="eligible", reference_specs=specs)
        [ref] = snap["externalReferences"]
        self.assertEqual(ref["label"], "stock Q4_K_M")
        self.assertEqual(ref["metrics"], {"latency_ms": 9.5, "eligible": 0.0}, "only the run's own metrics, as the file reads them")
        self.assertTrue(ref["gateFailed"])
        self.assertEqual(ref["failures"], ["nonspeech: 23 runaway clips"])
        self.assertEqual(ref["source"]["file"], "handy.json", "the file name only: a published page never shows a local path")
        self.assertEqual(len(ref["source"]["sha256"]), 64)
        self.assertIn("rig2", ref["source"]["note"])
        self.assertEqual(collector.build_snapshot(collector.load_from_dir(str(FIXTURES)), collected_at="x")["externalReferences"], [])

    def test_a_bad_reference_is_refused(self) -> None:
        for bad in ("file=/x.json", "label=a", "label=a,file=/x.json,size=3"):
            with self.subTest(spec=bad), self.assertRaises(ValueError):
                collector.parse_reference_specs([bad])


class SslCertFileTests(unittest.TestCase):
    def test_every_cli_call_carries_the_ssl_cert_file(self) -> None:
        # A deployment with its own CA (dev's is self-signed) needs the flag on every read, not a wrapper script.
        done = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
        with mock.patch.object(collector.subprocess, "run", return_value=done) as ran, mock.patch.object(collector, "compare_available", return_value=False):
            with contextlib.redirect_stderr(io.StringIO()):
                collector.main(["--run-id", "r-1", "--ssl-cert-file", "/tmp/dev-ca.pem"])
            collector.run_artemis(["discovery", "get", "r-1"])
        self.assertTrue(ran.called)
        for call in ran.call_args_list:
            argv = call.args[0]
            self.assertIn("--ssl-cert-file", argv)
            self.assertEqual(argv[argv.index("--ssl-cert-file") + 1], "/tmp/dev-ca.pem")
        collector.CLI_FLAGS[:] = []


class OneCapTwoUnitsTests(unittest.TestCase):
    def test_one_cap_in_bytes_and_in_mb_is_one_cap(self) -> None:
        # Speech Run D's brief: the same cap in bytes and in decimal MB, rounded. Two "different" caps meant no Within-the-cap view.
        cap = collector.size_cap("Keep the model at most 1,517,290,464 bytes (under 1,517.3 MB).")
        self.assertEqual(cap, {"bytes": 1517290464, "text": "at most 1,517,290,464 bytes", "unit": "bytes"})

    def test_two_caps_that_really_differ_still_give_none(self) -> None:
        self.assertIsNone(collector.size_cap("under 1.2 GB, or at most 1.3 GB"))


class RedactionTests(unittest.TestCase):
    """Pages get published, so a snapshot's text loses the user's hosts and paths unless --keep-raw-text asks to keep them."""

    def payloads(self):
        p = collector.load_from_dir(str(FIXTURES))
        p["run"].update(runnerName="rig2", taskDescription="Run `ssh someone@rig2 'cd /raid/models/qwen && ./bench.sh'` on 10.0.0.12; keep tokens/s high.")
        return p

    def test_hosts_and_paths_are_replaced_by_default(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="x", base_url="https://dev.artemis.turintech.ai")
        text = json.dumps(snap)
        for leak in ("rig2", "/raid/", "someone@", "10.0.0.12"):
            self.assertNotIn(leak, text)
        self.assertEqual(snap["run"]["runner"], "runner-1")
        self.assertEqual(snap["run"]["taskDescription"], "Run `ssh <host> 'cd <path> && ./bench.sh'` on <host>; keep tokens/s high.")
        self.assertTrue(snap["run"]["webUrl"].startswith("https://dev.artemis.turintech.ai/projects/"), "links are kept")

    def test_keep_raw_text_keeps_them(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="x", keep_raw_text=True)
        self.assertEqual(snap["run"]["runner"], "rig2")
        self.assertIn("/raid/models/qwen", snap["run"]["taskDescription"])


class ProjectRedactionTests(unittest.TestCase):
    def test_a_project_shares_one_runner_map_and_redacts_skip_reasons(self) -> None:
        good = collector.load_from_dir(str(FIXTURES))
        a, b = copy.deepcopy(good), copy.deepcopy(good)
        a["run"]["runnerName"], b["run"]["runnerName"] = "rig2", "rig3"
        runs = [{"id": "run-a", "createdAt": "1"}, {"id": "run-b", "createdAt": "2"}, {"id": "run-c", "createdAt": "3", "status": "failed"}]

        def fetch(run_id, *rest):
            if run_id == "run-c":
                raise RuntimeError("artemis failed: open /raid/someone/cache on rig2: no space")
            return copy.deepcopy(a if run_id == "run-a" else b)

        with mock.patch.object(collector, "compare_available", return_value=True), \
             mock.patch.object(collector, "list_project_runs", return_value=runs), \
             mock.patch.object(collector, "fetch_cli", side_effect=fetch), \
             contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            collector.main(["--project", "p-1"])
        text = out.getvalue()
        for leak in ("rig2", "rig3", "/raid/"):
            self.assertNotIn(leak, text)
        result = json.loads(text)
        self.assertEqual([r["run"]["runner"] for r in result["runs"]], ["runner-1", "runner-2"], "one map, so two machines stay two")
        self.assertIn("runner-1", result["skipped"][0]["reason"])

    def test_keys_are_kept_only_by_exact_name(self) -> None:
        snap = collector.redact_snapshot({"run": {"format": "/home/someone/leak", "hostname": "/raid/x", "steerAt": "~/y", "id": "/not/a/path"}})
        self.assertEqual(snap["run"], {"format": "<path>", "hostname": "<path>", "steerAt": "<path>", "id": "/not/a/path"})

    def test_an_ip_at_a_sentence_end_and_a_user_at_an_ip_are_redacted_whole(self) -> None:
        self.assertEqual(collector.redact_text("Run it on 10.0.0.12.", {}), "Run it on <host>.")
        self.assertEqual(collector.redact_text("ssh someone@10.0.0.12 then someone@10.0.0.13.", {}), "ssh <host> then <host>.")
        self.assertEqual(collector.redact_text("build v1.2.3.4.5", {}), "build v1.2.3.4.5", "five parts is a version, not an address")

    def test_package_pins_are_not_hosts(self) -> None:
        self.assertEqual(collector.redact_text("pip install numpy@1.26 torch@2.1.0", {}), "pip install numpy@1.26 torch@2.1.0")


class RunnerNameInProseTests(unittest.TestCase):
    def test_the_host_inside_a_runner_name_is_redacted_in_prose(self) -> None:
        # Run A: runner someone-rig2-gpu1, and the brief says "on the rig2 runner"; the host survived in snapshot and page.
        p = collector.load_from_dir(str(FIXTURES))
        p["run"].update(runnerName="someone-rig2-gpu1", taskDescription="Measure on the rig2 runner (A100 80 GB, GPU 1 only, 4 CPU threads). RIG2.lan is the same box.")
        snap = collector.build_snapshot(p, collected_at="x")
        self.assertNotIn("rig2", json.dumps(snap).lower())
        self.assertEqual(snap["run"]["taskDescription"], "Measure on the runner-1 runner (A100 80 GB, GPU 1 only, 4 CPU threads). runner-1 is the same box.")
        self.assertEqual(collector.redact_text("rig20 and gpu1 stay", collector.runner_names([{"run": {"runnerName": "someone-rig2-gpu1"}}])), "rig20 and gpu1 stay")
