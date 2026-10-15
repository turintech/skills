#!/usr/bin/env python3
"""Structural and TypeScript checks for visualization recipes."""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "examples" / "components"
COMPOSITIONS = ROOT / "examples" / "compositions"
CATALOG = ROOT / "references" / "component-catalog.md"

EXPECTED_COMPONENTS = {
    "baseline-comparison.tsx",
    "version-ranking.tsx",
    "metric-trajectory.tsx",
    "version-cards.tsx",
    "experiment-lineage.tsx",
    "failure-summary.tsx",
    "pareto-scatter.tsx",
}
EXPECTED_COMPOSITIONS = {
    "discovery-overview.canvas.tsx",
    "version-investigation.canvas.tsx",
    "experiment-story.canvas.tsx",
}
class RecipeStructureTests(unittest.TestCase):
    def test_expected_recipes_exist(self) -> None:
        self.assertEqual(
            {path.name for path in COMPONENTS.glob("*.tsx")},
            EXPECTED_COMPONENTS,
        )
        self.assertEqual(
            {path.name for path in COMPOSITIONS.glob("*.canvas.tsx")},
            EXPECTED_COMPOSITIONS,
        )

    def test_recipes_are_self_contained_and_offline(self) -> None:
        import_pattern = re.compile(r'from\s+["\']([^"\']+)["\']')
        for path in [*COMPONENTS.glob("*.tsx"), *COMPOSITIONS.glob("*.tsx")]:
            source = path.read_text(encoding="utf-8")
            self.assertEqual(
                import_pattern.findall(source),
                ["cursor/canvas"],
                msg=f"{path.name} must import only cursor/canvas",
            )
            self.assertNotIn("fetch(", source, msg=f"{path.name} must stay offline")

    def test_compositions_default_export(self) -> None:
        for path in COMPOSITIONS.glob("*.canvas.tsx"):
            self.assertIn(
                "export default function",
                path.read_text(encoding="utf-8"),
                msg=f"{path.name} must be a complete canvas",
            )

    def test_catalog_links_every_recipe(self) -> None:
        catalog = CATALOG.read_text(encoding="utf-8")
        for filename in EXPECTED_COMPONENTS | EXPECTED_COMPOSITIONS:
            self.assertIn(filename, catalog)

    @unittest.skipUnless(shutil.which("tsc"), "TypeScript compiler unavailable")
    def test_examples_typecheck(self) -> None:
        subprocess.run(
            ["tsc", "-p", str(ROOT / "tests" / "tsconfig.examples.json")],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
