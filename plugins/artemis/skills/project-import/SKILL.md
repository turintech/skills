---
name: project-import
description: Import an existing remote Git repository into Artemis as a fresh project, using an explicit branch and reusable Git credential, then capture and verify the project UUID. Use when a repository is ready for a new unit of Artemis work, even if other projects already exist for the same repository.
---

# Import a project into Artemis

## At a glance

- **Problem:** Registers a remote Git repository and explicit branch as a fresh Artemis project and captures its verified project UUID.
- **Must be available:** An authenticated CLI, a reachable remote and branch, a Git credential configured in Artemis that can read the repository, and verified commands unless runner-side verification will follow import.
- **Use / don't use:** Use whenever an importable remote exists and a new unit of work is needed; don't use it to create a fork, derive commands, or silently reuse an earlier project.
- **Next skill:** Return to `repo-command-setup` §5b if runner-side command verification or validation remains; otherwise pass the project UUID to `discovery-start`.

## Requirements

- `artemis status` confirms an authenticated session on the intended deployment.
- The remote URL and explicit branch are known and reachable.
- A Git credential registered in Artemis can read the repository.
- Compile, test, and benchmark commands are either verified locally through `repo-command-setup`, or explicitly deferred until this project can be verified on the runner.
- Optionally `jq`. Snippets below use it to filter `--output-format json`, but it is just one option — any JSON filter works (e.g. `python3 -c`).

## 1. Resolve and verify inputs

Record:

- repository URL for `--git-url`;
- exact branch for `--branch`;
- exact branch-tip commit as the seed;
- meaningful project name for `--name`.

Resolve and record the branch tip before import:

```bash
SEED_SHA="$(git ls-remote --exit-code --heads \
  "<git-url>" "refs/heads/<branch>" | cut -f1)"
test -n "$SEED_SHA"
printf '%s\n' "$SEED_SHA"
```

Always pass `--branch`. Import may accept a typo and fail only when Artemis later attempts checkout. Carry `SEED_SHA` through verification and handoff.

## 2. Name it to avoid ambiguity

```bash
artemis project list --help
artemis --output-format json project list
```

Default to importing a new project even if one already represents this repository and branch — separate projects are how work stays decoupled. Skim the existing list only to pick a project `--name` that won't be confused with another project against the same repository (e.g. suffix it with the task, target, or feature being optimised).

Reuse an existing project's UUID instead of importing again only when the user explicitly asks to continue that same prior work. Project names are labels, not stable identifiers; use UUIDs in every later command regardless.

When reusing prior work, the user may provide its Web UI project URL; extract the UUID from `/projects/<project-id>/`.

## 3. Select a Git credential

```bash
artemis key list --help
artemis --output-format json key list
```

Reuse a credential that can read the repository. Check the provider values returned by the installed CLI rather than assuming they match the values accepted by `key add`.

If no suitable credential exists, present **both** setup routes and let the user choose. For GitHub, the OAuth / GitHub App route is often easier than minting a PAT:

1. **GitHub OAuth (often easier):** ask the user to connect their GitHub account in the Artemis Web UI at [https://artemis.turintech.ai/settings/git](https://artemis.turintech.ai/settings/git) (same path on an on-prem deployment's base URL). Then re-run `artemis key list` — a `github_oauth_token` (or similar) entry should appear. Do not ask them to paste OAuth tokens into chat.
2. **PAT via CLI:** have the user run `artemis key add` interactively in their own terminal (for GitHub, typically `--provider github --token <pat>`) so the secret never enters chat.

Prefer an existing GitHub OAuth credential over adding a new PAT when both would work. For GitLab, Bitbucket, or Azure DevOps, use the provider-specific `artemis key add` flow unless the Web UI offers an equivalent connect path. Record the selected key UUID.

## 4. Import once

Confirm the URL, branch, project name, and key UUID before creating the project:

```bash
artemis project import --help
artemis --output-format json project import \
  --git-url "<git-url>" \
  --key-id "<key-uuid>" \
  --name "<project-name>" \
  --branch "<branch>"
```

Capture the project UUID from the response immediately.

Give the user a clickable link as soon as the UUID is known:

```text
[Open project](<base-url>/projects/<project-uuid>)
```

Use the authenticated deployment base URL, including for on-prem deployments. Repeat the link after import verification so the user can inspect the project in the Web UI.

**Import is asynchronous.** The command returns once the import is queued, while Artemis is still cloning the repository, and the project cannot be used until that finishes. `importedStatus` reports where it is — `importing`, `success`, or `failed` — on both `project import` and `project list`:

```bash
artemis --output-format json project list | jq -r '.docs[]? | select(.id=="<project-uuid>") | .importedStatus'
```

Wait for `success` before running anything against the project.

## 5. Verify and hand off

List or inspect the project using the installed CLI and confirm:

- UUID matches the import response;
- Git URL and branch match the intended remote;
- imported `gitHash` matches `SEED_SHA`;
- selected Git credential is correct;
- project is on the intended Artemis deployment.

If the imported commit differs because the branch moved, stop and record the new state rather than treating the original seed as valid. Use the UUID rather than the project name for validation, command configuration, and discovery.

Follow `repo-command-setup`'s workflow path: verify locally before import, or return to §5b after import for runner verification.

Project command defaults are optional for Web UI validation; discovery receives its commands inline through `discovery-start`.

## Checklist

- [ ] Authenticated deployment confirmed.
- [ ] Remote URL, explicit branch, and seed SHA recorded.
- [ ] Project name is distinct enough to avoid confusion with other projects against the same repository.
- [ ] Existing readable Git credential reused when possible (GitHub OAuth preferred over a new PAT).
- [ ] If no credential existed, both OAuth (Web UI) and `key add` (PAT) routes were offered; any new secret entered by the user outside chat.
- [ ] Import performed once with confirmed inputs.
- [ ] Project UUID captured and imported `gitHash` verified against the seed SHA.
- [ ] Clickable project link returned to the user.
- [ ] UUID and seed handed to `repo-command-setup` §5b or `discovery-start`.
