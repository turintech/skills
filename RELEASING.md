# Releasing

Skills are versioned independently of the Artemis CLI and platform. Compatibility is declared in each skill, not in the tag number.

## Version tags

Release from `main` with annotated semver tags such as `v1.2.0`.

- **Patch** — corrections that do not raise CLI or platform requirements.
- **Minor** — new skills or features, including raised minimum requirements.
- **Major** — breaking changes to skill names, routing, structure, or installation.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>[optional scope]: <description>
```

Common types:

- `feat` — a new skill or feature. Minor when released.
- `fix` — a correction that does not raise CLI or platform requirements. Patch when released.
- `docs` — documentation only.
- `chore` — tooling, manifests, or process with no skill behaviour change.

Raise a minimum CLI or platform requirement with `feat` (minor). Mark breaking changes to skill names, routing, structure, or installation with `!` or a `BREAKING CHANGE:` footer (major):

```
feat(discovery-start)!: require a validation script
```

## Branches

- `main` — skills compatible with the version deployed at [artemis.turintech.ai](https://artemis.turintech.ai).
- `develop` — changes intended for the next CLI or platform release.
- `hotfix/*` — production fixes branched from `main`, then merged back into `develop`.

## Release flow

1. Develop upcoming changes on `develop`.
2. Test against the corresponding CLI and platform candidate.
3. Merge compatible skills into `main`.
4. Publish the stable `vX.Y.Z` tag and a GitHub Release.

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
```

Pin a release when installing:

```bash
# Cursor
agent plugin marketplace add https://github.com/turintech/skills.git \
  --git-ref vX.Y.Z

# Codex
codex plugin marketplace add turintech/skills --ref vX.Y.Z

# GitHub Copilot
gh skill install turintech/skills --all --pin vX.Y.Z
```

## Distribution

GitHub is the primary distribution channel. Agents can install and pin a git ref from this repository. Mirroring release archives on the Artemis file server is optional and is not required to publish a release.

The first production snapshot is [v1.0.0](https://github.com/turintech/skills/releases/tag/v1.0.0). Unreleased next-CLI work stays on `develop` until it is compatible with production.
