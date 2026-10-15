"""Wording that picks the newest CLI to install says it must be below artemis-cli-max, so 1.2.0 is never chosen."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"
NEWEST_CLI = re.compile(r"\b(?:newest|latest)\b\W*(?:\w+\W+){0,4}?(?:release|version|stable|build|CLI)\b", re.I)


def prose_lines(path):
    fenced = False
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield n, line


class InstallBelowCeiling(unittest.TestCase):
    def test_newest_cli_wording_names_the_ceiling(self):
        found = []
        for path in sorted(SKILLS.rglob("*.md")):
            for n, line in prose_lines(path):
                if "runner" in line.lower() and "CLI" not in line:
                    continue  # runners have no ceiling
                if NEWEST_CLI.search(line) and "artemis-cli-max" not in line:
                    found.append(f"{path.relative_to(SKILLS)}:{n}: {NEWEST_CLI.search(line).group(0)}")
        self.assertEqual(found, [], "say the newest CLI below the skills' `artemis-cli-max`")

    def test_the_installer_comes_from_a_pinned_release_with_a_version(self):
        # latest/ is frozen at an old installer, and without --version it takes the newest release.
        text = (SKILLS / "cli-setup/references/installer.md").read_text()
        block = text[text.index("```bash"):]
        self.assertNotIn("artemis-cli/latest", text)
        self.assertIn('/public/artemis-cli/$VER"', block)
        self.assertIn(" artemis-cli-installer.sh\\$\" checksums.txt", block)
        self.assertIn('--version "$VER"', block)


if __name__ == "__main__":
    unittest.main()
