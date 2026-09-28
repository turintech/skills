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

- The browser, connected as in `cli-follow-along` section 1. This skill follows `cli-follow-along` for one tab, bringing it to the front, pointer pacing (*Make it watchable*), and *Clicking*: the rules there apply to every step here.
- The deployment base URL, from the user or the page they have open.
- A project. Tours that change something run on the demo project (a Particle Life project, or **Open a sample project** to make one) unless the user names another.

## 1. Before the tour

1. Connect the browser (`cli-follow-along` section 1). If it does not connect, say in one line that the tour needs the Claude browser extension and answer in the terminal instead.
2. Find the deployment address: the CLI config if there is one, then an address already in the conversation, otherwise `https://artemis.turintech.ai`. Do not install the CLI for this.
3. Open `<deployment-base-url>/projects` and read the account in the page header. Ask for the address only if the page does not show the user signed in, or shows someone else's account.
4. Keep other people's details off screen. **Platform Settings** opens on a page that lists every user on admin accounts, and **Users**, the **Runners** owner column, the project list's owner filter and a project's owner row show names or emails. Go around them; when a tour must pass one, say so first.
5. Pick the tour from section 3 by the user's question. If none fits, say which tours exist and ask which is closest.
6. Check what the tour needs before starting. For a Discovery run or a benchmark: one of the user's own runners online (**Runner and Scripts**) and a script on the project. If one is missing, the plan starts with setting it up, and say so with one recommendation ("No runner of yours is online. I'd connect one first, about 5 minutes."), not a list of options.
7. Say the plan in at most four lines: the steps, what will change, on which project, and the one step you will stop at. Then ask once: "Go ahead?" That yes covers every step in the plan.

## 2. Run the tour

**Follow the platform's own path.** Each page has one purple primary button that moves to the next step: follow it. Use what the page already offers before typing anything: example prompt chips, the project's default script, defaults that are already filled in. Change a default only when the tour says to, and say why.

For each step:

1. **Arrive first.** Navigate with the page's own links and tabs, never a typed path from memory. Stand on the page that is about to change before changing it. If a click by element reference does nothing, take a fresh screenshot and click the centre of the control.
2. **Point, then explain.** Move the pointer to the control and say in one sentence what it does and why this step matters.
3. **Keep going.** The user asked to be shown, and the yes to the plan covers its steps: do not stop to ask before each click. Stop only before a click that spends credits (**Start Discovery**), deletes something, changes a setting that already existed, or is not in the plan. When you stop, say what the click does and recommend an answer.
4. **Show the result.** Stay on the page while the change appears, then point at it.

End with a recap the user can follow alone: the path as a short list of page and button names, and a link to where they finished.

## 3. Tours

Button names are the Web UI's. Steps are goals: find each control on the page you are looking at.

**Where things are.** A project's left bar has **Overview** and **AI Agents**, then *Workflows* (**Plan**, **Maintain**, **Discover**), *Code* (**Branches**, **Files**) and *Project settings* (**General**, **Runner and Scripts**, **Metrics**). A dot on a settings link means "Setup incomplete". The **Get Started** card at the bottom of the bar lists what setup is left. Every page has a chat panel on the right with example prompts for that page.

| Tour | Steps | Changes anything |
|---|---|---|
| Read a run's results | Section 3b | No |
| Compare two versions | Section 3b, then a version's **Compare** control above its diff, or the Versions **Graphs** | No |
| Find why a build failed | **Branches**, the branch, its **Validations** tab. The **Script runs** list is on the left: open the failed run, then the failing command under **Commands** to read its log. Hover status icons: some reasons only show as a tooltip | No |
| Connect a machine | **Runner and Scripts**, then **Set up a new runner**: choose the operating system and architecture and follow the steps. Never reach it through **Platform Settings**: that opens a page listing every user on admin accounts | No, unless they run the steps |
| Import a repository | **Projects**, **Import Project**, **Import Git Repository**, pick the repository, then **Create Project**. It needs a Git connection Artemis can read; the page offers one if there is none | Yes |
| Try a sample project | **Projects**, **Import Project**, **Try a sample project**. Featured: Particle Life (C++), Julia Set (Java) and Smoke (Python), each with **Import project** | Yes |
| Set up a benchmark | Overview, the **Run and measure your code** card, **Setup**, **Create branch** (default name `artemis/measure`). That opens the branch's **Validations**: **Add your commands** (or **Run script** once the project has a script), pick the runner, **Run**, then open the run and read **Measurements**. Commands live in **Runner and Scripts** under **Scripts** | Yes |
| Start a Discovery run | Section 3a | Yes |

### 3a. Start a Discovery run

**Discover** first. If the list already has a run marked **Setup pending**, that is an abandoned setup: continue it (click the row) rather than start another, and say so.

| Step | Page heading | What to do | Purple button |
|---|---|---|---|
| 0 | Discover | Click an example prompt under the box to fill it (the first, **Optimise performance**, suits a first run), or type the goal. Pick the model from the picker under the box | the round arrow (send) |
| 1 | Candidate preferences | **Approval mode**: Automatic lets the agent's judges approve experiments. **Number of candidates**: default 10; say that each one costs credits | **Next: Select a runner** |
| 2 | Where should we run your code? | Pick from **Runner**. The list shows every online runner on the deployment, other people's included: pick the user's own. None of theirs online: **Set up a new runner** | **Next: Select a script** |
| 3 | How should we test and measure your code? | The project's default script is already chosen; read its setup and benchmark commands aloud in a line. **Benchmark runs** defaults to 1; 3 gives a spread to compare. Click **Run** and wait for every command to pass; Next stays greyed until it finishes | **Next: Configure metrics** |
| 4 | Configure your metrics | The baseline number from that run appears here. Check **Direction** (higher or lower is better) and **Importance**. **Artemis Score** adds AI-judged metrics; leave it off unless asked | **Next: Review setup** |
| 5 | Review Setup | Read the summary back. This is the click that spends credits: ask first | **Start Discovery** |

The page then becomes the run: **Overview**, **Experiments**, **Versions**, **Metrics**, **Setup**, and the **Discovery agent** chat on the right, where the agent explains what it is trying. Stay on Overview while the first experiments arrive.

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
| Why is my runner not in the list? | It is offline. **Runner and Scripts** shows the project's runner and an offline alert with **Configure Runner** |
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
- [ ] On the Discovery tour, the purple button followed on every step, the user's own runner picked, and the script run passing before Next
- [ ] Ended with a recap of page and button names and a link to where they finished
