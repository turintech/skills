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

- The deployment base URL reported by `artemis status`. Use whatever that command reports rather than any URL written here.
- The project, discovery, and version IDs captured by the owning skill.

## 1. Check the browser is usable

1. **Load the browser tools before deciding they are missing.** Where they are deferred, a plain look finds nothing even when a browser is connected. In Claude Code, load them in one call:

   ```text
   ToolSearch: select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,mcp__claude-in-chrome__switch_browser
   ```

   Only if that returns nothing is there no browser control: print the Web UI link and continue.
2. **Ask once, plainly.** Only the user can type `/chrome`, and every new session needs it, even when their extension works elsewhere; it is not a fault. Probe with `tabs_context_mcp`, and if nothing is connected, send the request as its own message, boxed and alone, the way `cli-setup` sends the login step:

   ````text
   ```
   ┌──────────────────────────────────────────────────────────┐
   │  RUN THIS IN CLAUDE CODE                                 │
   └──────────────────────────────────────────────────────────┘
   ```

   ```text
   /chrome
   ```

   Then tell me when it's done and I'll check again.
   ````

   Nothing else in that message. Re-probe when they answer.

   **When the calling skill says the browser is optional, stop here:** if that one request does not connect it, hand back so the caller continues in the terminal. For a user who wants to keep trying, ask one question: **is the Claude extension installed in Chrome at all?**

   - **No.** It is a one-off install from `https://claude.ai/chrome`, signed in to the same account as this session. Then `/chrome` again.
   - **Yes.** Make sure a Chrome window is open and **visible**, not minimised, then `/chrome` again. If it still fails, restart Chrome and try once more.

   Relaunching the session as `claude --chrome` comes last and only if they still want it: it costs them the conversation.

3. **Check it is still there before the moments that matter.** The extension can drop during a long run. Re-probe with `tabs_context_mcp` before each showpiece, above all before the result, and if it has gone say so then, offer `/chrome`, and wait. When the browser is optional, offer it once, then carry on with links.
4. **If it lands in the wrong Chrome, ask which one.** Several browsers can be paired with one account (profiles, other computers). `list_connected_browsers` names them, `select_browser` switches to the one the user picks, and `switch_browser` puts a Connect prompt in every one. Never choose for them. A new, signed-out window usually means another profile answered.
5. Use one tab for the whole session. Create it once, then navigate within it.
6. On the first page load, read the account shown in the page header. If it is not the account the CLI is authenticated as, stop and ask the user.

## 2. Find the page, then show it

Deployments differ. On newer ones a Discovery run sits under `/discover` and has no separate page per version; on older ones it sits under `/discovery` and each version has its own page. **Do not build URLs from memory.**

1. Open `<deployment-base-url>/projects/<project-id>` and let it settle.
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

**Be on the page that is about to change, then run the command,** so the user watches the result appear instead of reading about it. For every step that creates or changes something:

| About to run | Be here first | What the user sees |
|---|---|---|
| `project import` | Projects | The new project appears in the list |
| `changeset create` | The project's Branches | The branch appears |
| `changeset validate` | The branch's Script runs | The run appears, then passes with its number |
| `discovery create` | The project's Discover list | The run appears in the list |
| Anything else that adds a version | The tab that lists them | The row arrives while they watch |

Then move the pointer to the thing that appeared and click into it. Do not narrate the change before it is visible, or describe a screenshot of it afterwards.

### Show it

1. Navigate the tab to the link you found, or move there with the page's own tabs and sidebar when already inside the project.
2. **Bring the tab to the front, every time,** when you create it and before each navigation. A background tab means nobody is watching; if the user cannot see what you describe, check this first.
3. Wait for the page to load, then take a screenshot to confirm it shows what you expect.
4. Hover over the element you are describing so the user can see where to look.
5. Say in the chat, in one or two sentences, what is on screen and why it matters.
6. Stay on the page until the next step is ready. Do not close the tab.

Never open `/settings` on its own: on admin accounts it lists every user's name and email. The Projects list is fine, and is where you stand before an import so the user watches the project appear.

### Make it watchable, first-run demo only

On a first-run demo the pointer is the explanation. Use this pacing only when the calling skill says so; once the user has seen it, or asks for speed, navigate plainly.

1. **Make the pointer's journey visible:** four or five small moves in a straight line toward the target, not one jump.
2. **Land, pause, then click,** so the eye catches up before the page changes.
3. Scroll the target into view rather than jumping straight to it, and let the page settle.
4. Keep the pointer on the element while you explain it, so the words and the pointer agree.
5. One idea per step. Do not queue several actions between explanations.
6. **Hold still while work is being generated.** When a page fills by itself, stay on it and say what is arriving; read status from the CLI, not other tabs.

Each of these is a separate tool call: worth it during a demo, waste afterwards.

## 3. Clicking

- Navigation needs no approval: tabs, sidebar links, and version names.
- Anything that changes state needs the user's explicit yes first: Start, Generate more versions, Save, Create key, Revoke, Delete, Run, Cancel, and sending a message in a run's chat.
- Credentials are the user's. Open the page, point at the control, and wait while they act. Never read, copy, or type a key.
- Click by element reference from a fresh page read, never by coordinates from an earlier screenshot. References change when the page updates, so read the page again before each click.
- While a run is working, the button beside its chat box is Stop and Enter sends a message. Do not send a message while a version is being checked: it cancels that check.

## 4. When the browser cannot help

| Situation | Do |
|---|---|
| No browser tool after loading | Print the link and continue |
| No connected browser | Section 1: one request when the browser is optional, otherwise its fixes before falling back to links |
| The page header shows a different account | Stop and ask the user |
| A 500 error mentioning `URL.canParse` | Ask the user to update Chrome to version 120 or newer |
| "Project Not Found" | Check the account and the deployment base URL before retrying |
| A path gives 404 or "This page doesn't exist" | The deployment uses a different shape. Go back to the project page and follow its navigation |

## Checklist

- [ ] Browser tools loaded, a live browser probed, and the section 1 fixes offered before any fallback to links, or one request only when the caller said the browser is optional
- [ ] One tab, and the header account matches the CLI
- [ ] Each page explained in chat, with the pointer on the relevant element
- [ ] No state-changing click without an explicit yes, and no credential handled
