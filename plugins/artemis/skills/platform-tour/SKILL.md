---
name: platform-tour
description: Show someone how to do a task on the Artemis platform by doing it in their Chrome while they watch, through the Web UI and without the CLI. Use only when the user asks to be shown in their browser ("show me in my browser", "use computer use", "give me a tour of the platform"), names this skill, or accepts an offer to be shown. A plain how-to question gets a terminal answer from the task skill instead.
compatibility: Requires Artemis Platform 3.1.0+ and a browser-control tool such as Claude in Chrome. Uses no CLI.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Show how it is done in Artemis

## At a glance

- **Problem:** Teaches a task on the platform by doing it in the user's browser, one page at a time, so next time they can do it alone.
- **Must be available:** A connected browser-control tool, the user signed in to their Artemis deployment in that browser, and a project to work in.
- **Use / don't use:** Use when the user asks to be shown in their browser. A plain "how do I" gets a terminal answer from the task skill, and a request for the work ("start a Discovery run") goes to the CLI skills through `artemis`.
- **Next skill:** None. Offer the CLI route (`quickstart`) at the end if they want it done for them next time.

## Requirements

- The browser, connected as in `cli-follow-along` section 1 (load that skill; do not open its file). This skill follows `cli-follow-along` for one tab, bringing it to the front, pointer pacing (*Make it watchable*), and *Clicking* for element references, credentials and the chat box. Its approval rule does not apply here: section 2 step 3 decides when to stop.
- The deployment base URL, found as in section 1 step 2.
- A project. Tours that change something run on the demo project (a Particle Life project, or make one with the *Try a sample project* tour) unless the user names another.

## 1. Before the tour

1. Connect the browser: load the skill and follow `cli-follow-along` section 1. If it does not connect, say in one line that the tour needs the Claude browser extension and answer in the terminal instead.
2. Find the deployment address: the CLI config if there is one, then an address already in the conversation, otherwise `https://artemis.turintech.ai`. Do not install the CLI for this.
3. Open `<deployment-base-url>/projects` and read the account in the page header. Ask for the address only if the page does not show the user signed in, or shows someone else's account.
4. Keep other people's details off screen. In **Platform Settings**, **Users** lists every user on admin accounts and **Runners** has an **Owner** column; the project list's owner filter and a project's owner row show names or emails too. Go around them; when a tour must pass one, say so first.
5. Pick the tour from section 3 by the user's question. If none fits, say which tours exist and ask which is closest.
6. Check what the tour needs before starting. For a Discovery run or a benchmark: one of the user's own runners online (**Project Settings**, **Runner and Scripts**) and a script on the project. If one is missing, the plan starts with setting it up, and say so with one recommendation ("No runner of yours is online. I'd connect one first, about 5 minutes."), not a list of options.
7. Say the plan in at most four lines: the steps, what will change, on which project, and any step you will stop at (none for a read-only tour). Then ask once: "Go ahead?" That yes covers every step in the plan.

## 2. Run the tour

**Follow the platform's own path.** Each page has one purple primary button that moves to the next step: follow it. Use what the page already offers before typing anything: example prompt chips, the project's default script, defaults that are already filled in. Change a default only when the tour says to, and say why.

For each step:

1. **Arrive first.** Navigate with the page's own links and tabs, never a typed path from memory. Stand on the page that is about to change before changing it. If a click by element reference does nothing, take a fresh screenshot and click the centre of the control.
2. **Point, then explain.** Move the pointer to the control and say in one sentence what it does and why this step matters.
3. **Keep going.** The user asked to be shown, and the yes to the plan covers its steps: do not stop to ask before each click. Stop only before a click that spends credits (**Start Discovery**, **Start now**), deletes something, changes a setting that already existed, or is not in the plan. When you stop, say what the click does and recommend an answer.
4. **Show the result.** Stay on the page while the change appears, then point at it. A screenshot straight after a click can show the page before it updates: wait a second and look again before deciding a click failed.
5. **Inside a dialog, close a dropdown by choosing an option, never with Escape:** Escape closes the whole dialog.

End with a recap the user can follow alone: the path as a short list of page and button names, and a link to where they finished.

## 3. Tours

Button names are the Web UI's. Steps are goals: find each control on the page you are looking at.

**Where things are.** A project's left bar has **Overview** and **Agents**, then *Workflows* (**Maintain**, **Discover**, **Plan**), *Code* (**Branches**, **Files**) and **Project Settings**, which opens its own sections: **General**, **Runner and Scripts**, **Metrics**. A dot on a settings link means "Setup incomplete". The **Get Started** card at the bottom of the bar lists what setup is left. Every page has a chat panel on the right with example prompts for that page.

| Tour | Steps | Changes anything |
|---|---|---|
| Read a run's results | Section 3b | No |
| Compare two versions | Section 3b, then a version's **Compare** control above its diff, or the Versions **Graphs** | No |
| Find why a build failed | **Branches**, the branch, its **Scripts** tab. The **Script runs** list is on the left: open the failed run, then the failing command under **Commands** to read its log. Hover status icons: some reasons only show as a tooltip | No |
| Connect a machine | Go to `<deployment-base-url>/settings/runners/new` in the same tab (the Runner dropdown's **Add new Artemis runner** opens a new tab): choose the operating system and architecture and follow the steps. Don't browse the **Runners** list on the way: its **Owner** column shows people's names | No, unless they run the steps |
| Import a repository | **Projects**, **New**, **Connect Git Repository**, pick the repository, then **Create Project**. It needs a Git connection Artemis can read; the page offers one if there is none | Yes |
| Try a sample project | **Projects**, **New**, **Open a sample Project**. Featured: Particle Life (C++), Julia Set (Java) and Smoke (Python), each with **Import project**; the project opens when the import finishes | Yes |
| Set up a benchmark | Overview, the **Run and measure your code** card, **Setup**, **Create branch** (default name `artemis/measure`). That opens the branch's **Scripts** tab: **Ask agent** has the in-app agent write the script (it spends credits, a few dollars; say so first), **Add manually** is free. Then **Run script**: pick the runner (the first run makes it the project's default), set **Benchmark runs**, **Run**, and read **Measurements**. A passing run becomes the branch's baseline and offers **Optimise in Discover**. Commands live in **Project Settings**, **Runner and Scripts**, under **Scripts** | Yes |
| Start a Discovery run | Section 3a | Yes |

### 3a. Start a Discovery run

**Discover** first. If the list already has a run marked **Setup pending**, that is an abandoned setup: continue it (click the row) rather than start another, and say so.

| Step | Page heading | What to do | Purple button |
|---|---|---|---|
| 0 | Discover | Arriving from **Optimise in Discover**, the goal and the measured branch are already filled in: keep them. Otherwise click an example prompt under the box (**Make it faster** suits a first run) or type the goal. Pick the model from the picker under the box | the round arrow (send) |
| 1 Evaluation | How should versions be scored? | Keep **Measure and assess** (Recommended); **Assess only** measures nothing. **Runner**: pick the user's own (the list shows other people's too). None online: go to `/settings/runners/new` in the same tab, not the dropdown's new-tab **Add new Artemis runner**. **Script**: the project's default is chosen; read its commands aloud in a line. **Benchmark runs**: 3 gives a spread to compare. Under **Validate baseline**, click **Run** and wait for it to pass; Next stays greyed until it does | **Next: Success criteria** |
| 2 Success criteria | What counts as an improvement? | The baseline's numbers appear under **Measured metrics**. Check each metric's direction (higher or lower is better) and importance. Leave **AI-assessed metrics** as drafted unless asked | **Next: Preferences** |
| 3 Preferences | How should Artemis explore this? | **Orchestrator model**, **Approval mode** (Automatic lets the agent's judges approve experiments) and **Number of versions**: say that each version costs credits | **Next: Summary** |
| 4 Summary | Ready to start? | Read the summary back. This is the click that spends credits: ask first | **Start Discovery** |

Steps 1 to 3 also offer an outline **Start now**, which starts the run at once with the current choices and spends credits. On a tour, follow Next instead.

The page then becomes the run: **Overview**, **Experiments**, **Versions**, **Metrics**, **Setup**, and the **Discovery agent** chat, where the agent explains what it is trying. It may start collapsed: open it with **Expand panel** at the top right. Stay on Overview while the first experiments arrive.

Say one thing the page does not: mentioning a file with @ (the **+** button) is a hint to the agent about where to look, not a limit on which files change.

### 3b. Read a run's results

**Discover**, then the run. Its tabs:

| Tab | What it shows |
|---|---|
| Overview | **Agent notes**, the **Best version**, and **What next?** (continue, explore a direction, generate more versions). **Decide what's next** at the top scrolls here |
| Experiments | What the agent tried, as a canvas, list or board |
| Versions | The results. **Table**: one row per version with each metric. **Graphs**: every version against the baseline, ranked by the metric picked in its dropdown |
| Metrics | How the score is weighted, not the results. **Save & recompute** changes it: ask first |
| Setup | The runner, script and metrics the run uses |

Then click a version. **Code** is its diff, **Details** has the approach, the commit, its metrics against the baseline with the change in percent, and the experiment's conclusion. **Logs** has the runs. The arrows beside the version step to the previous and next one.

Three things to say while on Versions:

- **Read the measured metric, not the AI score.** The **Best** badge follows the AI score, which often ties across versions; the measured column (fps, runtime) is what changed. In Graphs, switch the dropdown to that metric.
- **"Needs more runs"** means too few measurements to form an interval, so the platform gives no verdict yet. Hovering a value shows how many samples it is a mean of; a baseline measured once is the usual cause.
- **Each version is also a branch.** **Branches** lists it as "Discovery <run> - v<N>", unpublished; open it and use **Create PR** to take it out of Artemis.

### 3c. Common questions

| Question | Answer on the page |
|---|---|
| How many credits do I have? | The number under the user's name at the bottom of the left bar |
| Why is my runner not in the list? | It is offline. The project's **Overview** shows an offline alert with **Configure Runner**; **Runner and Scripts** shows which runner the project uses |
| How do I get the code out? | The version's branch, **Create PR**; or on Versions, a row's menu: **Create PR**, **Download zip**, **Download Git patch** |
| Can I rerun a version or the baseline? | Versions, a row's menu, **Run this version**; or **Run baseline** |
| The run stopped; can it continue? | The run's header: **Continue** after a cancel, **Retry** after a failure, **Generate more versions** after it completes |
| Where do I change what "better" means? | Project **Metrics** for direction; the run's **Metrics** tab for importance |

## 4. When the page does not match

- **A button is greyed out:** hover it. The tooltip says what is missing, such as "Pick a runner first." or "Wait for the run to finish."
- **A button is missing or renamed:** read the page's navigation, use the control that does the same job, and say in one line what it is called now. Never click by guesswork or by coordinates from an earlier screenshot.
- **A step needs something that is not there** (no machine online, no Git connection): say what is missing and recommend the one next step, usually setting it up through its own tour. Never pick another person's runner.
- **A 500 mentioning `URL.canParse`:** Chrome is older than version 120; ask the user to update it.
- **The user wants it done, not shown:** stop the tour, say what was done so far, and hand over to `quickstart`.

## Checklist

- [ ] Browser connected and the header account checked before the first step
- [ ] The plan said in at most four lines, naming what will change
- [ ] Each step: arrived first, pointer on the control, one sentence of why
- [ ] One yes to the plan, then no stops except before credits, deletes, changed settings or anything outside the plan, each with a recommendation
- [ ] On the Discovery tour, the purple button followed on every step (never **Start now**), the user's own runner picked, and the baseline validated before Next
- [ ] Ended with a recap of page and button names and a link to where they finished
