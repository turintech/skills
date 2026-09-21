#!/usr/bin/env bash
# Validate every Artemis skill against the Agent Skills spec and house rules.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="$ROOT/plugins/artemis/skills"
REF="${SKILLS_REF:-skills-ref}"
REQUIRE_TAG="${REQUIRE_CLI_TAG:-1}"
fail=0

for dir in "$SKILLS"/*/; do
  name="$(basename "$dir")"
  if ! "$REF" validate "$dir" >/dev/null 2>&1; then
    echo "FAIL $name: skills-ref validate"
    "$REF" validate "$dir" || true
    fail=1
  fi
  lines=$(wc -l < "$dir/SKILL.md")
  if [ "$lines" -ge 500 ]; then
    echo "FAIL $name: SKILL.md has $lines lines (limit 500)"
    fail=1
  fi
  frontmatter="$(awk '/^---$/{n++; next} n==1' "$dir/SKILL.md")"
  if [ "$REQUIRE_TAG" = "1" ] && ! echo "$frontmatter" \
      | grep -qE '^  artemis-cli-min: "[0-9]+\.[0-9]+\.[0-9]+"$'; then
    echo "FAIL $name: missing metadata.artemis-cli-min"
    fail=1
  fi
  if [ "$REQUIRE_TAG" = "1" ] && ! echo "$frontmatter" \
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
