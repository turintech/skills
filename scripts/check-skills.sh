#!/usr/bin/env bash
# Check Artemis skill compatibility metadata and router targets.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="$ROOT/plugins/artemis/skills"
fail=0

for dir in "$SKILLS"/*/; do
  name="$(basename "$dir")"
  frontmatter="$(awk '/^---$/{n++; next} n==1' "$dir/SKILL.md")"
  if ! echo "$frontmatter" \
      | grep -qE '^  artemis-cli-min: "[0-9]+\.[0-9]+\.[0-9]+"$'; then
    echo "FAIL $name: missing metadata.artemis-cli-min"
    fail=1
  fi
  if ! echo "$frontmatter" \
      | grep -qE '^  artemis-platform-min: "[0-9]+\.[0-9]+\.[0-9]+"$'; then
    echo "FAIL $name: missing metadata.artemis-platform-min"
    fail=1
  fi
done

for ref in $(sed -n '/^## 6\. Route to the owning skill/,$p' "$SKILLS/artemis/SKILL.md" \
    | grep -oE '`[a-z][a-z0-9-]+`' | tr -d '`' | sort -u); do
  if [ ! -d "$SKILLS/$ref" ]; then
    echo "FAIL router routes to a missing skill: $ref"
    fail=1
  fi
done

[ "$fail" = 0 ] && echo "OK: all skills valid"
exit "$fail"
