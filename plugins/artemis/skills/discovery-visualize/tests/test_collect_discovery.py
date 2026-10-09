#!/usr/bin/env python3
"""Unit tests for the discovery snapshot collector."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
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
                {"name": "Falcon", "url": "https://artemis.turintech.ai/turintech-falcon"},
            ]
        }
        self.assertEqual(collector.infer_base_url(status), "https://artemis.turintech.ai")
        self.assertEqual(
            collector.infer_base_url(status, "https://example.test/"),
            "https://example.test",
        )


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
        self.assertIn("not an Artemis verdict", front["note"])

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

    def test_reference_pairs(self) -> None:
        names = ["MatMul_triton_tflops", "MatMul_cublas_tflops", "MatMul_triton_ms", "MatMul_cublas_ms", "simulation_fps"]
        pairs = collector.find_references(names)
        self.assertIn({"target": "MatMul_triton_tflops", "reference": "MatMul_cublas_tflops"}, pairs)
        self.assertIn({"target": "MatMul_triton_ms", "reference": "MatMul_cublas_ms"}, pairs)
        self.assertFalse(any(p["target"] == "simulation_fps" for p in pairs))

    def test_quartiles(self) -> None:
        q = collector.quartiles([4.0, 1.0, 3.0, 2.0])
        self.assertAlmostEqual(q["q1"], 1.75)
        self.assertAlmostEqual(q["median"], 2.5)
        self.assertAlmostEqual(q["q3"], 3.25)

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
                "metrics": [{"id": "m-fps", "name": "simulation_fps", "unit": "fps", "higherIsBetter": True}],
                "versions": [
                    {"sha": "sha-0", "isBaseline": True, "metrics": [dict(compared, value=100.0, readings=5, improvementPct=None, improvementLowPct=None, improvementHighPct=None, verdict=None)]},
                    {"sha": "sha-1", "isBaseline": False, "versionNumber": 1, "metrics": [compared],
                     "overallVerdict": {"verdict": "better", "improvementLowPct": 12.5, "improvementHighPct": 27.5, "provisional": False}},
                ],
            },
        }

    def test_maps_falcons_verdict_and_interval(self) -> None:
        snap = collector.build_snapshot(self.payloads(), collected_at="2026-01-01T00:00:00Z")
        metric = snap["versions"][0]["metrics"]["simulation_fps"]
        self.assertEqual(metric["pctBetter"], 20.0)
        self.assertAlmostEqual(metric["timesBetter"], 1.2)
        self.assertEqual(metric["vsBaseline"], {
            "source": "falcon", "verdict": "better", "improvementPct": 20.0, "ciLowPct": 12.5, "ciHighPct": 27.5,
            "readings": 5, "recommendedReadings": None, "recommendedReadingsReason": "settled", "spreadPct": 3.1,
        })
        self.assertEqual(snap["versions"][0]["overallVerdict"]["verdict"], "better")
        self.assertEqual(snap["baseline"]["readings"], {"simulation_fps": 5})
        definition = snap["metrics"][0]
        self.assertTrue(definition["higherIsBetter"])
        self.assertEqual(definition["unit"], "fps")
        self.assertIn("discovery compare", snap["provenance"]["verdictsSource"])

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
            cli = self.fake_cli(tmp, 'case "$*" in *"project get"*) echo "Usage: artemis project [command]";; *"project list"*) echo \'{"docs":[{"id":"p-2","name":"Other"},{"id":"p-1","name":"From list"}]}\';; esac\n')
            self.assertEqual(collector.project_name("p-1", cli=cli), "From list")

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
