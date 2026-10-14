"""Every SKILL.md front matter parses as YAML, as strict skill loaders parse it, with a non-empty name and description."""
import pathlib
import sys

import yaml

SKILLS = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1] / "plugins/artemis/skills"

fail = False
for path in sorted(SKILLS.glob("*/SKILL.md")):
    name = path.parent.name
    parts = path.read_text().split("---\n", 2)
    try:
        front = yaml.safe_load(parts[1]) if len(parts) == 3 and parts[0] == "" else None
    except yaml.YAMLError as err:
        print(f"FAIL {name}: front matter is not valid YAML: {err}".replace("\n", " "))
        fail = True
        continue
    if not isinstance(front, dict) or not all(isinstance(front.get(k), str) for k in ("name", "description")):
        print(f"FAIL {name}: front matter needs a name and a description string")
        fail = True
        continue
    for key in ("name", "description"):
        if not front[key].strip():
            print(f"FAIL {name}: front matter {key} is empty")
            fail = True
sys.exit(fail)
