"""Every SKILL.md front matter parses as YAML, as strict skill loaders parse it, with a non-empty name and description,
and a CLI range whose ceiling is above its floor."""
import pathlib
import re
import sys

import yaml


def version_tuple(text):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(text))
    return tuple(int(n) for n in m.groups()) if m else None

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
    meta = front.get("metadata") if isinstance(front.get("metadata"), dict) else {}
    low, high = version_tuple(meta.get("artemis-cli-min", "")), version_tuple(meta.get("artemis-cli-max", ""))
    # The ceiling is exclusive: the skills work with every CLI from min up to, but not including, max.
    if low and high and high <= low:
        print(f"FAIL {name}: artemis-cli-max {meta['artemis-cli-max']} must be above artemis-cli-min {meta['artemis-cli-min']}")
        fail = True
sys.exit(fail)
