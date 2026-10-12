# The official CLI installer

1. Open the **Connect Your Agent** page, `<deployment-base-url>/settings/connect-agent`, for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm the deployment's base URL: `https://artemis.turintech.ai` for hosted Artemis, or the on-prem deployment's own URL.

The installer detects the platform, installs the CLI, and configures service endpoints for the deployment named with `--base-url`. Always pass it: without it, the installer from CLI 1.1.14 on leaves any existing configuration as it is, and a fresh install points nowhere until `artemis login --url <deployment-base-url>`.

**Check which version it produces before relying on it.** Its built-in download source can lag the published releases. If `artemis --version` is older than the skills' minimum, use the direct download in `SKILL.md` (*Where to download from*), then `artemis login`.

```bash
(
  set -e
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL \
    "https://files.artemis.turintech.ai/public/artemis-cli/latest/artemis-cli-installer.sh" \
    -o "$TMP/installer.sh"
  chmod +x "$TMP/installer.sh"
  "$TMP/installer.sh" --base-url "<deployment-base-url>"
)
```

The installer selects two independent things. **Which build:** the newest stable release by default, or `--version X.Y.Z` to pin one, `--nightly` to include prereleases, `--dev` for the rolling development build. **Which deployment the CLI points at:** `--base-url` with a full URL, which writes the endpoint config and does not change where the binary is downloaded from.
