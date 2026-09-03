---
name: execution-log-inspect
description: Retrieve and interpret Artemis runner task logs through the platform when compile, test, benchmark, validation, or Discovery execution fails and the runner host is unavailable.
---

# Inspect Artemis execution logs

## At a glance

- **Problem:** Finds the task identifier, retrieves its log without runner-host access, and identifies the first concrete failure.
- **Must be available:** An authenticated Artemis CLI and a Discovery version ID, changeset validation ID, or runner `processId`.
- **Use / don't use:** Use only for work dispatched to a runner. A `generation_failed` Discovery version has no task log; inspect its agent narration instead.
- **Next skill:** Return the evidence and diagnosis to `repo-command-setup`, `discovery-start`, or `discovery-inspect`.

Platform task logs contain compile, test, benchmark, resource, and result-ingestion output. They are distinct from the runner daemon's host-local connection and polling log.

## 1. Find the task identifier

For a Discovery candidate:

```bash
artemis --output-format json discovery versions get "<version-id>"
```

Record `processId`. If it is absent, confirm the version lifecycle. `generation_failed` means no runner task was created; use `artemis chat messages <agentRunId>` from `discovery-inspect`.

The current version record exposes `processId`. Prefer the version-native shortcut:

```bash
artemis discovery versions logs "<version-id>"
```

For changeset validation, capture the validation `id` and `processId` from the `changeset validate` response. Do not substitute a per-command `logId`.

If a runner-executed failure has neither identifier, report that logs are unavailable instead of claiming they were checked.

## 2. Retrieve the log

Prefer the resource-native command when a validation ID is available:

```bash
artemis changeset validation logs "<validation-id>" --project "<project-uuid>"
```

Otherwise retrieve by process:

```bash
artemis process logs --help
artemis process logs "<process-id>"
```

If these CLI commands cannot retrieve the log, use the authenticated request below with the same config file the active CLI uses:

```bash
(
set -a; . ~/.config/artemis/.env; set +a

python3 - "<process-id>" <<'PY'
import json
import os
import sys
import urllib.request

identifier = sys.argv[1]
path = f"/turintech-falcon/api/utils/process/{identifier}/logs"

request = urllib.request.Request(
    os.environ["ARTEMIS_BASE_URL"].rstrip("/") + path,
    headers={"Authorization": f'Bearer {os.environ["ARTEMIS_API_KEY"]}'},
)
with urllib.request.urlopen(request) as response:
    entries = json.load(response).get("logs", [])

for entry in sorted(entries, key=lambda item: item.get("timestamp", "")):
    print(entry.get("timestamp", ""), entry.get("level", ""), entry.get("message", ""))
PY
)
```

Never print the environment file, API key, request headers, or debug output. If the deployment rejects these routes, stop and direct the user to the execution log in the Web UI; do not guess API paths.

## 3. Diagnose the failure

Order entries by timestamp. Follow the task through repository download, preparation, compile, test, benchmark, results-file parsing, and upload. Identify the last phase that started and the first concrete failure.

Prefer direct evidence: the failed command and exit code, compiler or test output, `Traceback`, timeout, `Killed` or OOM, lost-runner messages, or a successful benchmark followed by missing or rejected metrics. Do not infer that later phases succeeded because an earlier command passed.

If the task log ends without a task failure, use host-local daemon output only when available to investigate connection, polling, or process-lifecycle problems.

## Report

Return the resource and process or log ID, the last phase reached, the first concrete failure, the minimum supporting log lines, the likely cause, and the next owning skill or action. State any log-access limitation and redact credential-like values.
