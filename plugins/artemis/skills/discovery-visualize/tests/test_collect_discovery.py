#!/usr/bin/env python3
"""Unit tests for the discovery snapshot collector."""

from __future__ import annotations

import json
import os
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
    def test_pct_better_both_directions(self) -> None:
        self.assertAlmostEqual(collector.pct_better(10.0, 6.0, False), 40.0)
        self.assertAlmostEqual(collector.pct_better(0.5, 0.7, True), 40.0)
        self.assertIsNone(collector.pct_better(None, 1.0, False))
        self.assertEqual(collector.pct_better(0.0, 1.0, False), 0.0)

    def test_kind_classification(self) -> None:
        self.assertEqual(collector.classify_kind("compile_runtime", "worker"), "harness")
        self.assertEqual(collector.classify_kind("quality_score", "agent"), "quality")
        self.assertEqual(collector.classify_kind("latency_ms", "worker"), "target")

    def test_higher_is_better_heuristic(self) -> None:
        self.assertFalse(collector.infer_higher_is_better("decode_b8_ms"))
        self.assertTrue(collector.infer_higher_is_better("quality_score"))


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
        self.assertEqual(snap["schemaVersion"], 1)
        self.assertEqual(snap["run"]["id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(
            snap["run"]["webUrl"],
            "https://artemis.example/projects/22222222-2222-2222-2222-222222222222/discovery/11111111-1111-1111-1111-111111111111",
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
            self.assertEqual(loaded["schemaVersion"], 1)
            self.assertEqual(loaded["perMetricWinners"]["latency_ms"]["raw"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
