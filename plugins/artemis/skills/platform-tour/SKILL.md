---
name: platform-tour
description: Show someone how to do a task on the Artemis platform by doing it in their Chrome while they watch, through the Web UI and without the CLI. Use when the user asks how to do something in Artemis, where to find something, or wants to be shown a part of the platform, such as setting up a benchmark, starting a Discovery run, reading results, or finding why a build failed.
compatibility: Requires Artemis Platform 3.1.0+ and a browser-control tool such as Claude in Chrome. Uses no CLI.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Show how it is done in Artemis

## At a glance

- **Problem:** Teaches a task on the platform by doing it in the user's browser, one page at a time, so next time they can do it alone.
- **Must be available:** A connected browser-control tool, the user signed in to their Artemis deployment in that browser, and a project to work in.
- **Use / don't use:** Use for "how do I", "where is", "show me". When the user wants the work done rather than learned, use the CLI skills through `artemis`.
- **Next skill:** None. Offer the CLI route (`quickstart`) at the end if they want it done for them next time.

## Requirements

- The browser, connected as in `ui-walkthrough` section 1. This skill follows `ui-walkthrough` for one tab, bringing it to the front, pointer pacing (*Make it watchable*), and *Clicking*: the rules there apply to every step here.
- The deployment base URL, from the user or the page they have open.
- A project. Tours that change something run on the demo project (a Particle Life project, or **Open a sample project** to make one) unless the user names another.

## 1. Before the tour

1. Connect the browser (`ui-walkthrough` section 1). Without one, say this skill needs it and offer the CLI route instead.
2. Open `<deployment-base-url>/projects` and read the account in the page header. Stop and ask if it is not the user's.
3. Pick the tour from section 3 by the user's question. If none fits, say which tours exist and ask which is closest.
4. Say the plan in at most four lines: the steps, what will change, and on which project.

## 2. Run the tour

**Follow the platform's own path.** Each page has one purple primary button that moves to the next step: follow it. Use what the page already offers before typing anything: example prompt chips, the project's default script, defaults that are already filled in. Change a default only when the tour says to, and say why.

For each step:

1. **Arrive first.** Navigate with the page's own links and tabs, never a typed path from memory. Stand on the page that is about to change before changing it. If a click by element reference does nothing, take a fresh screenshot and click the centre of the control.
2. **Point, then explain.** Move the pointer to the control and say in one sentence what it does and why this step matters.
3. **Ask before anything that changes state:** Create, Save, Run, Start, Delete, or sending a message in a run's chat. Name the project it will change and wait for a yes. Navigation needs no approval.
4. **Show the result.** Stay on the page while the change appears, then point at it.

End with a recap the user can follow alone: the path as a short list of page and button names, and a link to where they finished.

## 3. Tours

Button names are the Web UI's. Steps are goals: find each control on the page you are looking at.

| Tour | Steps | Changes anything |
|---|---|---|
| Read a run's results | Project, **Discover**, the run, the **Metrics** tab for which version won and by how much, then that version and its code change | No |
| Compare two versions | The run's **Versions** tab, open each version, its change and its experiment's conclusion | No |
| Find why a build failed | The branch's **Script runs**, the failed run, the failing command and its log. Hover status badges: some reasons only show as a tooltip | No |
| Connect a machine | **Settings**, then **Runners** by its own link (never Settings on its own), what online looks like; **Connect a machine** shows the setup steps | No, unless they run the steps |
| Import a repository | **Projects**, **New**, **Connect Git Repository**; it needs a Git connection Artemis can read | Yes |
| Try a sample project | **Projects**, **New**, **Open a sample project**: Particle Life or Smoke | Yes |
| Set up a benchmark | The project overview's Getting Started card, **Setup**, **Create branch** (default name `artemis/measure`), the branch's **Script runs**, **Add your commands**, **Run script**, then read the number. A run that measured nothing shows "No metrics recorded yet" | Yes |
| Start a Discovery run | Section 3a | Yes |

### 3a. Start a Discovery run

**Discover** first. If the list already has a run marked **Setup pending**, that is an abandoned setup: offer to continue it (click the row) rather than start another.

| Step | Page heading | What to do | Purple button |
|---|---|---|---|
| 0 | Discover | Click an example prompt under the box to fill it (the first, **Optimise performance**, suits a first run), or type the goal. Pick the model from the picker under the box | the round arrow (send) |
| 1 | Candidate preferences | **Approval mode**: Automatic lets the agent's judges approve experiments. **Number of candidates**: default 10; say that each one costs credits | **Next: Select a runner** |
| 2 | Where should we run your code? | Pick from **Runner**. The list shows every online runner on the deployment, other people's included: pick the user's own. None of theirs online: **Set up a new runner** | **Next: Select a script** |
| 3 | How should we test and measure your code? | The project's default script is already chosen; read its setup and benchmark commands aloud in a line. **Benchmark runs** defaults to 1; 3 gives a spread to compare. Click **Run** and wait for every command to pass | **Next: Configure metrics** |
| 4 | Configure your metrics | The baseline number from that run appears here. Check **Direction** (higher or lower is better) and **Importance**. **Artemis Score** adds AI-judged metrics; leave it off unless asked | **Next: Review setup** |
| 5 | Review Setup | Read the summary back. This is the click that spends credits: ask first | **Start Discovery** |

The page then becomes the run: **Overview**, **Experiments**, **Versions**, **Metrics**, and the **Discovery agent** chat on the right, where the agent explains what it is trying. Stay on Overview while the first experiments arrive.

Say one thing the page does not: mentioning a file with @ (the **+** button) is a hint to the agent about where to look, not a limit on which files change.

## 4. When the page does not match

- **A button is missing or renamed:** read the page's navigation, use the control that does the same job, and say in one line what it is called now. Never click by guesswork or by coordinates from an earlier screenshot.
- **A step needs something that is not there** (no machine online, no Git connection): say what is missing, show where it is set up, and ask whether to continue that tour first.
- **A 500 mentioning `URL.canParse`:** Chrome is older than version 120; ask the user to update it.
- **The user wants it done, not shown:** stop the tour, say what was done so far, and hand over to `quickstart`.

## Checklist

- [ ] Browser connected and the header account checked before the first step
- [ ] The plan said in at most four lines, naming what will change
- [ ] Each step: arrived first, pointer on the control, one sentence of why
- [ ] A yes before every state-changing click, on the project named
- [ ] On the Discovery tour, the purple button followed on every step, the user's own runner picked, and the script run passing before Next
- [ ] Ended with a recap of page and button names and a link to where they finished
