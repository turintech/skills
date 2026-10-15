# The official CLI installer

1. Open the **Connect Your Agent** page, `<deployment-base-url>/settings/connect-agent`, for the deployment you are setting up. The Web UI is the source of truth; if the download, credentials, flags, or artifact below differ or fail, use the command currently published there.
2. Confirm the deployment's base URL: `https://artemis.turintech.ai` for hosted Artemis, or the on-prem deployment's own URL.

The installer detects the platform, installs the CLI, and configures service endpoints for the deployment named with `--base-url`. Always pass it: without it, the installer from CLI 1.1.14 on leaves any existing configuration as it is, and a fresh install points nowhere until `artemis login --url <deployment-base-url>`.

Each release has its own folder, `https://files.artemis.turintech.ai/public/artemis-cli/<version>/`, with that version's installer, binaries and `checksums.txt`. The list of versions is `https://files.artemis.turintech.ai/public/artemis-cli/`.

1. From that list, pick `VER`: the newest version below the skills' `artemis-cli-max`. The listing command in `SKILL.md` (*Where to download from*) prints the candidates.
2. Download the installer from `VER`'s folder. Never use `latest/`.
3. Check the installer against that folder's `checksums.txt`.
4. Run it with `--version "$VER"`.
5. Check `artemis --version`. If it is below the skills' minimum, or at or above their `artemis-cli-max`, use the direct download in `SKILL.md` (*Where to download from*), then `artemis login`.

The block below does steps 2 to 4:

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
