"""Skills ask the next step as a question, and link what they report."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parents[2] / "plugins/artemis/skills"


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text()


class ReportRules(unittest.TestCase):
    def test_the_next_step_is_asked_with_the_question_tool(self):
        # After "just set me up" a sweep agent listed the next steps as bullets instead of asking.
        text = skill("quickstart")
        close = text[text.index("## 11. Close"):text.index("## Checklist")]
        for rule in ("ask the next step with the host's question tool", "never as a bulleted list"):
            self.assertIn(rule, close, "quickstart close: missing the question-tool rule")

    def test_inspect_answers_link_the_run_the_version_and_the_versions_page(self):
        # Sweep answers carried one link where the run, the version and the Versions page were all known.
        text = skill("discovery-inspect")
        self.assertIn("Every answer about a run or version ends with clickable Web UI links", text)
        run = "](<deployment-base-url>/projects/<project-id>/discover/<run-id>"
        for link in (run + ")", run + "/versions)", run + "/versions/<version-id>)"):
            self.assertIn(link, text, "discovery-inspect: a link template is missing")

if __name__ == "__main__":
    unittest.main()
