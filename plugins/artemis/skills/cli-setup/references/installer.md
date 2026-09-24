# The official CLI installer

1. Open `<deployment-base-url>/settings/cli` for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm whether this is hosted Artemis or an on-prem deployment with a custom base URL. It selects which invocation below to use.

The installer detects the platform, installs the CLI, and configures service endpoints.

**Check which version it produces before relying on it.** Its built-in download source can lag the published releases. If `artemis --version` is older than the skills' minimum, use the direct download in `SKILL.md` (*Where to download from*), then `artemis login`.

For hosted (SaaS) Artemis:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh"
)
```

For on-prem Artemis, add the deployment's base URL:

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --anyauth -u "Artemis_User:Artemis_Custom_Runner_2025" \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh" --base-url https://your-custom.artemis.turintech.ai
)
```

The installer selects two independent things. **Which build:** the newest stable release by default, or `--version X.Y.Z` to pin one, `--nightly` to include prereleases, `--dev` for the rolling development build. **Which deployment the CLI points at:** `--base-url` with a full URL, which writes the endpoint config and does not change where the binary is downloaded from.
