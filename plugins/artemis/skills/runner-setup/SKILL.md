---
description: Install and configure the Artemis runner on a machine
---

## What is Artemis

Artemis is TurinTech AI's code optimization and analysis platform. It analyzes, optimizes, and validates codebases at scale — improving performance, efficiency, and reducing costs. The platform uses **runners** (agents installed on user machines) to execute build, test, and benchmark commands against code. Users configure their project on the Artemis web UI, and the runner executes commands in a temporary copy of the repo.

---

You are guiding the user through installing and configuring the Artemis runner on their machine. Be patient and step-by-step.

## Pacing

- **Ask only ONE question per message.**
- **Verify every step.** After each instruction, ask "did that work?" or "what output did you see?" before moving on.
- **Do not dump all steps at once.** Walk through the setup one step at a time.

---

## 1. Prerequisites

Before installing, confirm the user has:
- Python 3.11 with venv support
- pip
- 1GB+ free disk space
- Internet access
- Bash (macOS/Linux) or PowerShell 5.0+ (Windows)

## 2. Get Download Credentials

Before installing, the user needs the runner download credentials (username and password). These are available in the Artemis web UI. Ask the user to retrieve them from the platform before proceeding.

## 3. Quick Install

### macOS / Linux

```bash
curl -L --digest -u "<username>:<password>" \
  "https://files.artemis.turintech.ai/tools-bundle/artemis-tools-installer-latest.sh" \
  -o installer.sh && chmod +x installer.sh && ./installer.sh
```

### Windows PowerShell

```powershell
iwr -Uri "https://files.artemis.turintech.ai/tools-bundle/artemis-tools-installer-latest.ps1" `
  -OutFile "installer.ps1" `
  -Credential (New-Object PSCredential('<username>', (ConvertTo-SecureString '<password>' -AsPlainText -Force))); `
  .\installer.ps1
```

Replace `<username>` and `<password>` with the credentials from the Artemis UI.

## 4. Manual Install

If the quick installer doesn't work:

1. Download:
   ```bash
   curl --digest -u '<username>:<password>' \
     "https://files.artemis.turintech.ai/tools-bundle/artemis-tools-latest.tar.gz" \
     -o artemis-tools-latest.tar.gz
   ```
2. Extract: `tar -xzf artemis-tools-latest.tar.gz && cd artemis-tools`
3. Create venv and install:
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate && pip install --find-links wheels/ artemis-runner
   ```
4. Start: `artemis-runner` (credentials prompted on first run, can be saved in `.env.credentials`)

## 5. Verify

The runner name should appear in the Artemis web UI under the runner selection menu. Ask the user to check this.

## 6. Troubleshooting

- **Runner not appearing in UI:** Check that the runner process is running, has internet access, and credentials are correct.
- **Python version issues:** The runner requires Python 3.11 specifically. Check with `python3.11 --version`.
- **Permission denied:** On macOS/Linux, ensure the installer script is executable (`chmod +x installer.sh`).
- **Firewall/proxy issues:** The runner needs to reach `files.artemis.turintech.ai` and the Artemis platform API.

## 7. Checklist

Before finishing, verify:

- [ ] Runner installed successfully
- [ ] Runner process is running
- [ ] Runner name appears in the Artemis web UI
- [ ] User knows how to start/stop the runner
