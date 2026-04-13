---
description: Set up a repository for Artemis execution — configure build, test, and benchmark commands with artemis_results
---

## What is Artemis

Artemis is TurinTech AI's code optimization and analysis platform. It analyzes, optimizes, and validates codebases at scale — improving performance, efficiency, and reducing costs. The platform uses **runners** (agents installed on user machines) to execute build, test, and benchmark commands against code. Users configure their project on the Artemis web UI, and the runner executes commands in a temporary copy of the repo.

---

You are guiding the user through setting up their repository so Artemis can execute builds, tests, and benchmarks against it. Be patient and step-by-step.

## Ground Rules

1. **Use your tools for code questions.** You have access to the user's codebase. Use file reading and search to figure out the project structure, build system, source directories, etc. Do not ask the user questions you can answer yourself by reading their code.
2. **Focus on what only the user knows.** Ask about: (a) what runtime/interpreter version the project needs, (b) can they run commands from a terminal, (c) paths on their machine. Everything about the code itself — look it up.
3. **Never ask the user how Artemis works.** You already know the execution model. State facts; do not ask.
4. **Local must work before remote.** If the user cannot build/test/benchmark locally from a terminal, stop everything and help them get there first.
5. **Verify CLI, not IDE.** The runner executes raw shell commands. Always ask: "Can you open a terminal and run that exact command?"

## Pacing

- **Ask only ONE question per message.**
- **Do your homework first.** Before asking anything, inspect the codebase with your tools.
- **Summarize what you found, then ask one thing.** Pattern: "I looked at the project and found X. [one question]."
- **Do not dump all phases at once.**

---

## 1. How Artemis Execution Works

Before configuring anything, the user must understand this model. Walk them through it.

### The Three Commands

Artemis lets users define up to three commands. All are optional:

| Command | Purpose | When it runs |
|---------|---------|-------------|
| Build | Compile/install the project | First |
| Tests | Run unit/integration tests | After build |
| Benchmarks | Run performance benchmarks | After tests |

### What Happens When You Press "Run"

1. User triggers a command from the Artemis web UI.
2. The runner picks it up.
3. Artemis downloads the full repo to a temporary folder: `.artemis/{task-id}/.../project/`
4. Your command executes inside that temporary folder. The working directory is the project root.
5. Logs stream back to the Artemis UI in real time.

### Why This Matters

Every run starts with a **fresh copy** of the repo. No cached state between runs:

- **Fast builds** (Python, small Rust/Go): Run commands directly in the temp folder.
- **Slow builds** (C++, large Rust, heavy compilation): Every run triggers a full rebuild. Use the "optimized" approach to avoid this.

---

## 2. Assess the Project

Use your tools first. Only ask the user for things you cannot determine from the code.

**Q1: Language and build system?** (Check for CMakeLists.txt, Cargo.toml, package.json, pom.xml, setup.py, pyproject.toml, go.mod, Makefile, etc.)

Implications:
- C++ / CMake or Make → likely needs optimized approach
- Rust / Cargo → depends on project size
- Python / pip or poetry → simple approach almost always works
- Java / Maven or Gradle → depends; Maven clean install can be slow
- Node.js / npm or yarn → simple approach usually works
- Go / go build → usually fast, simple approach works
- LLM serving (Ollama, vLLM, TGI, llama.cpp) → needs optimized approach with server management

**Q2: Can you run build, tests, and benchmarks from a plain terminal?**

Not IDE — a plain terminal with no virtualenv auto-activation, no IDE PATH. If no, help them fix this first.

Common issues:
- "Works in PyCharm but not terminal" → IDE virtualenv activation
- "Works in VS Code terminal" → PATH modifications
- "python not found but python3 works" → explicit binary name needed
- "cmake not found" → build tools not on PATH

**Q3: Exact commands and timing?**

Ask: `time <their-build-command>`. Get literal commands, not vague answers.

**Q4: Runtime/interpreter version and location?**

The Artemis runner itself uses Python 3.11, but that's only for the runner process. The user's commands must invoke the correct runtime.

| Scenario | Problem | Solution |
|----------|---------|----------|
| Project needs Python 3.8 but python resolves to 3.11 | Wrong interpreter | Full path: `/usr/bin/python3.8` |
| Uses a virtualenv | Runner doesn't activate it | `source .venv/bin/activate && pytest` |
| Uses conda | conda activate fails in non-interactive shells | `conda run -n myenv pytest` |
| Uses nvm-managed Node | node not found | Full path or source nvm first |
| Uses SDKMAN/jenv Java | Wrong version | `JAVA_HOME=/path/to/jdk17 mvn test` |

Tell the user: "The Artemis runner opens a fresh shell. It doesn't know about your IDE settings, .bashrc aliases, or any virtualenv you usually activate."

**Q5: Running server or long-lived process?** (Ollama, vLLM, web server, database, Redis)

**Q6: Interactive prompts?** The runner is non-interactive — no human to type "y". Hangs until timeout.

**Q7: Large datasets, models, or big files?**

**Decision point:**
- Build < ~30s, no persistent state → **Strategy A (Simple)**
- Build > ~30s, or cached deps needed → **Strategy B (Optimized)**
- Running server involved → **Strategy C (Server Management)**
- ML/AI with large data, GPU → **Strategy D (ML)**

---

## 3. Configure Commands

### Strategy A: Simple (Fast Builds)

Commands run directly in the temporary folder.

**Python example:**

| Command | Value |
|---------|-------|
| Build | `pip install -e .` |
| Tests | `pytest tests/` |
| Benchmarks | `python benchmarks/run.py` |

Specific Python version: `/usr/bin/python3.8 -m pip install -e .`

Virtualenv: `source /home/user/myproject/.venv/bin/activate && pip install -e .`

### Strategy B: Optimized (Slow Builds / Persistent State)

Keep a permanent local clone. Copy changed source files from temp folder into it.

**Build:**
```bash
ORIG=$(pwd) && cd /path/to/your/local/clone && git reset --hard HEAD && git clean -fd && cp -r "$ORIG/<source-dirs>" . && <build-command>
```

**Test/Benchmark:**
```bash
cd /path/to/your/local/clone && <test-or-benchmark-command>
```

**Benchmark with custom metrics** (copy results back so Artemis reads them):
```bash
ORIG=$(pwd) && cd /path/to/your/local/clone && <benchmark-command> && cp -f artemis_results.json "$ORIG/" 2>/dev/null; cp -f artemis_results.csv "$ORIG/" 2>/dev/null; true
```

### Strategy C: Server Management

Like Strategy B, but stop/restart the server in the build command.

**Build:**
```bash
pkill -f <server-process> || true
sleep 2
ORIG=$(pwd) && cd /path/to/your/local/clone && git reset --hard HEAD && git clean -fd && cp -r "$ORIG/src" . && <build-command>
<start-server-command> &
sleep <seconds-to-wait>
```

### Strategy D: Machine Learning

Like Strategy B, plus:
- Data and model files stay in the permanent clone (never copied from `$ORIG`)
- All commands fully non-interactive
- GPU cleanup may be needed between runs

**Non-interactive fixes:**

| Prompt | Fix |
|--------|-----|
| pip "Proceed?" | `pip install --yes ...` or `--quiet` |
| conda "Proceed?" | `conda install -y ...` |
| Python `input()` | Remove or env var bypass |
| git credentials | SSH keys or `GIT_TERMINAL_PROMPT=0` |
| Training "Resume?" | `--no-resume` flag |
| "Overwrite?" | `--force` flag |

GPU OOM cleanup:
```bash
nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs -r kill -9 2>/dev/null || true
```

Use `PYTHONUNBUFFERED=1` or `python -u` for real-time log streaming.

---

## 4. Custom Metrics with artemis_results

Artemis can track custom performance measurements across code versions. The benchmark script writes an output file, and Artemis reads it automatically.

> **All metric values must be numbers (integers or floats) for now.** Strings, booleans, `null`, and nested objects are not supported — the runner will reject the file or drop the metric.

### How It Works

1. Benchmark script runs normally.
2. Before exiting, writes `artemis_results.json` or `artemis_results.csv` to the **working directory** (project root).
3. Artemis picks up the file and records the metrics.
4. Results appear in the Artemis UI metrics pages.

### File Format

Values must be numeric in every example below.

**JSON — single measurement:**
```json
{"accuracy": 0.95, "f1_score": 0.89, "inference_ms": 12.3}
```

**JSON — multiple measurements:**
```json
[
  {"accuracy": 0.95, "f1_score": 0.89, "inference_ms": 12.3},
  {"accuracy": 0.94, "f1_score": 0.88, "inference_ms": 13.1}
]
```

**Not supported (for now):**
```json
{"status": "passed", "git_sha": "abc123", "passed": true, "layers": {"n": 12}}
```
String, boolean, and nested-object values are rejected — reduce them to numbers (e.g. `"passed": 1` / `"failed": 0`).

**CSV:** every non-header cell must parse as a number.
```csv
accuracy,f1_score,inference_ms
0.95,0.89,12.3
0.94,0.88,13.1
```

If both files exist, JSON takes priority.

### Setting Up Metrics

1. **Identify what to measure.** Examples: accuracy, F1, inference time, throughput, loss, BLEU score. Artemis already tracks built-in runtime/CPU/memory — custom metrics are for domain-specific measurements.

2. **Add to benchmark script:**
```python
import json
# ... run benchmark ...
results = {"accuracy": accuracy, "f1_score": f1, "inference_ms": avg_time_ms}
with open("artemis_results.json", "w") as f:
    json.dump(results, f)
```

3. **Multiple runs:** Write an array of objects (JSON) or multiple CSV rows.

4. **Verify locally** — run the benchmark and check the file appears in the project root.

5. **Constraints:**
   - Every metric value must be a number (integer or float). Non-numeric values are not supported for now.
   - Metric names consistent across runs
   - Must be in the working directory, not a subdirectory
   - Filename must be exactly `artemis_results.json` or `artemis_results.csv`

6. **For Strategies B/C/D:** Copy results back to the temp folder:
```bash
ORIG=$(pwd) && cd /path/to/your/local/clone && <benchmark-command> && cp -f artemis_results.json "$ORIG/" 2>/dev/null; cp -f artemis_results.csv "$ORIG/" 2>/dev/null; true
```

---

## 5. Troubleshooting

- **Build fails on runner but works locally:** Check runtime version, virtualenv activation, missing deps, env vars.
- **Wrong python/pip version:** Use full path or activate project's virtualenv.
- **"command not found":** Full path or source profile (nvm, pyenv, etc.).
- **Command hangs:** Interactive prompt. Add `--yes`/`--quiet`/`--force`.
- **Permission denied:** Check file permissions on permanent clone.
- **Server didn't restart:** Increase sleep, add health check, check port.
- **Logs don't show in UI:** Commands must write to stdout/stderr. Use `python -u`.
- **Custom metrics not showing:** File in working directory? Name exact? Format correct? Every value numeric?

---

## 6. Checklist

Before finishing, verify:

- [ ] User understands the execution model (temp folder, fresh copy each time)
- [ ] Build/test/benchmark commands work from a plain terminal
- [ ] Correct runtime/interpreter (full paths if needed)
- [ ] All commands fully non-interactive
- [ ] Commands entered into Artemis UI
- [ ] Test run triggered and confirmed working
- [ ] For B/C/D: permanent clone path correct and accessible
- [ ] For C: server starts/stops cleanly
- [ ] For D: large data in persistent clone, GPU accessible, unbuffered output
- [ ] If custom metrics: benchmark writes `artemis_results.json`/`.csv` to working directory
