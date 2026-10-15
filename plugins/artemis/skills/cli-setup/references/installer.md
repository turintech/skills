# The official CLI installer

1. Open the **Connect Your Agent** page, `<deployment-base-url>/settings/connect-agent`, for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm the deployment's base URL: `https://artemis.turintech.ai` for hosted Artemis, or the on-prem deployment's own URL.

The installer detects the platform, installs the CLI, and configures service endpoints for the deployment named with `--base-url`. Always pass it: without it, the installer from CLI 1.1.14 on leaves any existing configuration as it is, and a fresh install points nowhere until `artemis login --url <deployment-base-url>`.

**Check which version it produces before relying on it.** Its built-in download source can lag the published releases. If `artemis --version` is older than the skills' minimum, or at or above their `artemis-cli-max`, use the direct download in `SKILL.md` (*Where to download from*), then `artemis login`.

Take the installer from a pinned release folder, never `latest/`, and always pass `--version`. `VER` is the newest release below the skills' `artemis-cli-max`, from the listing in `SKILL.md` (*Where to download from*); 1.1.18 on 15 Oct 2026.

```bash
(
  set -e
  VER="<the newest release below artemis-cli-max, from the listing>"
  BASE="https://files.artemis.turintech.ai/public/artemis-cli/$VER"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  cd "$TMP"
  curl -fLO "$BASE/artemis-cli-installer.sh" && curl -fLO "$BASE/checksums.txt"
  grep " artemis-cli-installer.sh\$" checksums.txt | { sha256sum -c - 2>/dev/null || shasum -a 256 -c -; }
  chmod +x artemis-cli-installer.sh
  ./artemis-cli-installer.sh --version "$VER" --base-url "<deployment-base-url>"
)
```

The installer selects two independent things. **Which build:** `--version X.Y.Z`, always passed here, because without it the installer takes the newest stable release, which can be at or above the skills' `artemis-cli-max`. It also has `--nightly` for prereleases and `--dev` for the rolling development build. **Which deployment the CLI points at:** `--base-url` with a full URL, which writes the endpoint config and does not change where the binary is downloaded from.
