---
name: repo-prepare-fork
description: Prepare an importable fork or private mirror of an upstream repository the user does not control, pinned to a known commit. Use when Artemis cannot import the upstream repository directly and the user needs a repository under their own account or organization. Always obtain explicit permission before creating or pushing any fork or mirror.
---

# Prepare a repository fork for Artemis

## At a glance

- **Problem:** Creates an importable fork or private mirror of third-party source, pinned to a known commit, so Artemis can work on it.
- **Must be available:** Explicit user permission, GitHub and Git access under an approved owner, and a reachable upstream repository.
- **Use / don't use:** Use when Artemis cannot directly import source the user does not control; skip it when an importable repository, fork, or mirror already exists.
- **Next skill:** Use `repo-command-setup`, and then `project-import`.

## Requirements

- Explicit user permission before creating or pushing any fork or mirror — see Permission gate below.
- `gh`/git access sufficient to create a repository under the approved owner (account or org).
- The upstream repository must be reachable (public, or already accessible to the user) to clone it.

This procedure is GitHub-specific. For another Git host, apply the same permission, seed-pinning, push, and verification rules using that host's tools.

## Permission gate

**Never create or push a fork or mirror without explicit permission from the user.**

Before any `gh repo create`, `gh repo fork`, or `git push`, ask one focused question that establishes:

1. whether the user already has a suitable fork or mirror;
2. whether they want a public fork or private mirror, and whether they want to create it themselves;
3. if the agent should create it, the approved owner and target branch, plus the name and visibility for a private mirror.

Creating a repository is an outward-facing action under the user's or organization's identity. A GitHub public fork normally inherits the upstream repository name; do not promise an arbitrary name for that path. Do not change an existing repository's visibility, repoint its remote, or overwrite it without separate approval.

## 1. Pin the upstream source

Resolve the intended branch, tag, or commit to a concrete SHA before copying anything. A moving reference is not a reproducible baseline.

```bash
UPSTREAM="https://github.com/<owner>/<repo>"
UPSTREAM_REF="<branch-tag-or-sha>"
SEED_SHA="$(gh api "repos/<owner>/<repo>/commits/$UPSTREAM_REF" -q .sha)"
printf '%s\n' "$SEED_SHA"
```

Record the upstream URL, reference, resolved SHA, and date.

## 2. Choose fork or private mirror

Make the choice with the user:

| | Public fork | Private mirror |
|---|---|---|
| Upstream relationship | Preserved by GitHub | Recorded manually |
| Visibility | A fork of a public repository is public | Can be private |
| Synchronization | `gh repo sync` | Fetch and merge from an `upstream` remote |
| Best fit | Contributing back or tracking upstream | Isolating generated branches or private experimentation |

## 3. Create the approved copy

Run one of these only after the permission gate is satisfied.

### Public fork

```bash
gh repo fork --help
# Personal account:
gh repo fork "$UPSTREAM" --clone=false
# Approved organization:
gh repo fork "$UPSTREAM" --clone=false --org "<approved-org>"
```

Run only the form matching the approved owner.

Confirm the created owner and repository URL from command output. Use that exact URL as `TARGET_URL` below.

### Private mirror

```bash
gh repo create --help
TARGET_OWNER="<approved owner>"
TARGET_NAME="<approved name>"
gh repo create "$TARGET_OWNER/$TARGET_NAME" --private
TARGET_URL="https://github.com/$TARGET_OWNER/$TARGET_NAME"
```

### Create the pinned branch

Use this for either approved copy:

```bash
set -euo pipefail
TARGET_URL="<confirmed fork-or-mirror URL>"
TARGET_BRANCH="<approved branch>"
WORKTREE="$(mktemp -d)"
trap 'rm -rf "$WORKTREE"' EXIT

git clone "$UPSTREAM" "$WORKTREE"
git -C "$WORKTREE" switch --detach "$SEED_SHA"
git -C "$WORKTREE" switch -c "$TARGET_BRANCH"
git -C "$WORKTREE" remote add target "$TARGET_URL"

EXISTING_BRANCH="$(git ls-remote --heads \
  "$TARGET_URL" "refs/heads/$TARGET_BRANCH")"
if test -n "$EXISTING_BRANCH"; then
  echo "target branch already exists; inspect it before changing anything" >&2
  exit 1
fi

git -C "$WORKTREE" push -u target "$TARGET_BRANCH"
```

Do not force-push. If the target repository or branch already exists, stop and inspect it with the user before changing anything.

Verify that the target branch tip is exactly the recorded seed:

```bash
ACTUAL_SHA="$(git ls-remote "$TARGET_URL" "refs/heads/$TARGET_BRANCH" | cut -f1)"
test -n "$ACTUAL_SHA"
test "$ACTUAL_SHA" = "$SEED_SHA"
```

Record `TARGET_URL`, `TARGET_BRANCH`, and `SEED_SHA` for downstream skills. They must use the approved copy, not the upstream repository.

## Checklist

- [ ] Upstream reference resolved to a concrete seed SHA.
- [ ] Existing user-controlled fork or mirror checked first.
- [ ] User explicitly approved any repository creation and push.
- [ ] Owner and target branch confirmed; private-mirror name and visibility confirmed when applicable.
- [ ] Fork or mirror created without force-pushing or altering an unknown repository.
- [ ] Target branch tip verified equal to the recorded seed SHA.
- [ ] Temporary clone removed after verification.
- [ ] Target URL, branch, and seed handed to `repo-command-setup` and `project-import`.
