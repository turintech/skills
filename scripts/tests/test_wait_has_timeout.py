"""Every `--wait` names a `--timeout` that fits a 10-minute shell call; the CLI's default is 20 minutes."""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def commands(text):
    fenced, current = False, ""
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            current += line.rstrip("\\") + " "
            if not line.rstrip().endswith("\\"):
                yield current
                current = ""
        else:
            yield from (span for span in re.findall(r"`([^`]*)`", line) if span.startswith("artemis "))


class WaitHasTimeout(unittest.TestCase):
    def test_every_wait_names_a_timeout(self):
        found = [
            f"{path.relative_to(SKILLS)}: {command.strip()[:80]}"
            for path in sorted(SKILLS.rglob("*.md"))
            for command in commands(path.read_text())
            if re.search(r"--wait\b", command) and "--timeout" not in command and not command.lstrip().startswith("#")
        ]
        self.assertEqual(found, [], "a --wait without --timeout outlasts the shell call")


if __name__ == "__main__":
    unittest.main()
