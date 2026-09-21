---
name: ui-walkthrough
description: Show the user the Artemis Web UI page that matches each step while you work, in one browser tab, navigating only. Use when the user has chosen to follow along in their browser and a browser-control tool such as Claude in Chrome is connected. Do not use it to change settings or start work without the user's explicit approval.
compatibility: Requires Artemis CLI 1.1.8+ and Artemis Platform 3.1.0+, plus a browser-control tool such as Claude in Chrome. Without one, print links instead. Page paths differ between deployments, so the skill follows the app's own navigation.
metadata:
  artemis-cli-min: "1.1.8"
  artemis-platform-min: "3.1.0"
---

# Show the Artemis Web UI while working

## At a glance

- **Problem:** Opens the page that matches what was just done, so the user sees and understands each step instead of a black box.
- **Must be available:** A connected browser-control tool, the authenticated deployment base URL, and the IDs of the resource to show.
- **Use / don't use:** Use only after the user chose the browser route. Don't use it to do the work: the CLI and the owning skills make every change.
- **Next skill:** Return to the skill that called it.

## Requirements

- The deployment base URL reported by `artemis status`, for example `https://artemis.turintech.ai`. Use whatever that command reports rather than any URL written here.
- The project, discovery, and version IDs captured by the owning skill.

## 1. Check the browser is usable

1. **Load the browser tools before deciding they are missing.** On hosts where they are deferred, browser tools exist only as names until their schemas are loaded, so a plain look finds nothing even when a browser is connected and the session was started for it. In Claude Code, load them in one call:

   ```text
   ToolSearch: select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp
   ```

   Only if that returns nothing is there genuinely no browser control. Then print the Web UI link and continue without the browser.
2. **Loading the tools is not the same as having a browser.** Probe for a live one with `tabs_context_mcp` before offering the browser route. If it reports no connected browser, work down this ladder, cheapest first, and re-probe after each step. Give the user **one** action at a time, not the whole list.

   1. **Run `/chrome` in Claude Code.** One command, no restart, and it is what usually fixes it. Try this before saying anything about restarting.
   2. **Check Chrome itself:** a window open and **visible**, not minimised, with the extension installed and signed in to the same account. Then `/chrome` again.
   3. **Restart Chrome**, then `/chrome` again.
   4. **Last resort: restart the session with `claude --chrome`.** It costs the user their conversation, so never offer it until the three above have failed.

   Do not announce the restart option up front as the price of the browser route. A session that cannot see a browser usually only needs `/chrome`, and telling someone they must relaunch is how a working route gets abandoned.

3. If more than one browser is connected, ask the user which one to use.
4. Use one tab for the whole session. Create it once, then navigate within it.
5. On the first page load, read the account shown in the page header. If it is not the account the CLI is authenticated as, stop and ask the user.

## 2. Find the page, then show it

Deployments differ. On newer ones a Discovery run sits under `/discover` and has no separate page per version; on older ones it sits under `/discovery` and each version has its own page. **Do not build URLs from memory.**

1. Open `<base-url>/projects/<project-id>` and let it settle.
2. Read the page's own navigation and use those links: the project sections (Discover, Branches, Changesets, Files, Settings) and, inside a run, its tabs (Experiments, Versions, Metrics).
3. Follow the link for what you want to show instead of typing a path.
4. Reuse the paths you resolved for the rest of the session; they do not change while you work.

Only when the user gave you bare IDs and no page to start from, try the newer shape first and fall back to the older one:

| Resource | Newer deployments | Older deployments |
|---|---|---|
| Project | `/projects/<project-id>/overview` | `/projects/<project-id>/overview` |
| Discovery list | `/projects/<project-id>/discover` | `/projects/<project-id>/discovery` |
| Discovery run | `/projects/<project-id>/discover/<run-id>/overview` | `/projects/<project-id>/discovery/<run-id>` |
| Versions of a run | `/projects/<project-id>/discover/<run-id>/versions` | `/projects/<project-id>/discovery/<run-id>/versions/<version-id>` |
| The code of a version | `/projects/<project-id>/branches/<branch-id>/changes` | `/projects/<project-id>/changesets/<changeset-id>` |
| API keys, Git, Runners | `/settings/api-keys`, `/settings/git`, `/settings/runners` | same |

### Arrive before the change, never after

**Be on the page that is about to change, then run the command.** This is the difference between showing someone the platform and reporting to them about it. If the CLI creates a project while the user is looking at a terminal, they see a line of output. If they are already on Projects when it runs, they watch the project appear, and the link between the command and the platform becomes obvious without being explained.

Apply it to every step that creates or changes something:

| About to run | Be here first | What the user sees |
|---|---|---|
| `project import` | Projects | The new project appears in the list |
| `discovery create` | The project overview | The run appears on the overview |
| Anything that adds a version, branch or changeset | The tab that lists them | The row arrives while they watch |

Then move the pointer to the thing that just appeared and click into it, so the next page is somewhere they saw you go rather than somewhere you jumped to.

Do not narrate the change before it is visible, and do not take a screenshot of the result and describe it afterwards. Stand still on the right page and let the platform do the talking.

### Show it

1. Navigate the tab to the link you found, or move there with the page's own tabs and sidebar when already inside the project.
2. **Bring the tab to the front, every time.** Creating a tab in the background leaves the user looking at whatever they had open, so the walkthrough happens where nobody is watching. Activate the tab when you create it, and make sure it is the frontmost tab before each navigation. If the user says they cannot see what you are describing, this is the first thing to check.
3. Wait for the page to load, then take a screenshot to confirm it shows what you expect.
4. Hover over the element you are describing so the user can see where to look.
5. Say in the chat, in one or two sentences, what is on screen and why it matters.
6. Stay on the page until the next step is ready. Do not close the tab.

Never open `/settings` on its own: on admin accounts it lists every user's name and email. The Projects list is fine, and is where you stand before an import so the user watches the project appear.

### Make it watchable, first-run demo only

The first time someone sees Artemis, the pointer is the explanation: they follow it around the page. Use this pacing only for that first tour, when the calling skill says this is a first-run demo. Once the user has seen it, or asks for speed, navigate plainly.

1. **Make the pointer's journey visible.** Move it across the page in four or five small steps along a straight line toward the target, not one teleport. The user should be able to see where it is heading before it arrives, so the click is the end of a movement rather than a surprise.
2. **Land, pause, then click.** Rest on the target for a beat once you arrive, so the eye catches up with the pointer before the page changes.
3. Scroll the target into view rather than jumping straight to it, and let the page settle.
4. Keep the pointer on the element while you explain it, so the words and the pointer agree.
5. One idea per step. Do not queue several actions between explanations.
6. **Hold still while work is being generated.** When a page is filling by itself, such as experiments appearing in a run, stay on it and say what is arriving. Do not wander to other tabs for status: read that from the CLI and leave the screen where the user is looking.
7. Read the page again before each click. References go stale as the page updates, and this pacing gives the page more chances to change under you.

Each of these is a separate tool call, so it is slower and costs more. That is the point during a demo and waste afterwards.

## 3. Clicking

- Navigation needs no approval: tabs, sidebar links, and version names.
- Anything that changes state needs the user's explicit yes first: Start, Generate more versions, Save, Create key, Revoke, Delete, Run, Cancel, and sending a message in a run's chat.
- Credentials are the user's. Open the page, point at the control, and wait while they act. Never read, copy, or type a key.
- Click by element reference from a fresh page read, never by coordinates from an earlier screenshot. References change when the page updates, so read the page again before each click.
- While a run is working, the button beside its chat box is Stop and Enter sends a message. Do not send a message while a version is being checked: it cancels that check.

## 4. When the browser cannot help

| Situation | Do |
|---|---|
| No browser tool after loading, or no connected browser | Offer the section 1 fixes and wait. Print the link and continue only once those have failed |
| The page header shows a different account | Stop and ask the user |
| A 500 error mentioning `URL.canParse` | Ask the user to update Chrome to version 120 or newer |
| "Project Not Found" | Check the account and the deployment base URL before retrying |
| A path gives 404 or "This page doesn't exist" | The deployment uses a different shape. Go back to the project page and follow its navigation |

## Checklist

- [ ] Browser tools loaded, a live browser probed, and the section 1 fixes offered before any fallback to links
- [ ] One tab, and the header account matches the CLI
- [ ] Each page explained in chat, with the pointer on the relevant element
- [ ] No state-changing click without an explicit yes, and no credential handled
