---
name: ui-walkthrough
description: Show the user the Artemis Web UI page that matches each step while you work, in one browser tab, navigating only. Use when the user has chosen to follow along in their browser and a browser-control tool such as Claude in Chrome is connected. Do not use it to change settings or start work without the user's explicit approval.
compatibility: Requires Artemis CLI 1.1.5 or newer and a browser-control tool such as Claude in Chrome. Without one, print links instead.
metadata:
  artemis-cli-min: "1.1.5"
---

# Show the Artemis Web UI while working

## At a glance

- **Problem:** Opens the page that matches what was just done, so the user sees and understands each step instead of a black box.
- **Must be available:** A connected browser-control tool, the authenticated deployment base URL, and the IDs of the resource to show.
- **Use / don't use:** Use only after the user chose the browser route. Don't use it to do the work: the CLI and the owning skills make every change.
- **Next skill:** Return to the skill that called it.

## Requirements

- The deployment base URL reported by `artemis status`, for example `https://dev.artemis.turintech.ai`.
- The project, discovery, and version IDs captured by the owning skill.

## 1. Check the browser is usable

1. Confirm a browser-control tool is available and a browser is connected. If not, print the Web UI link and continue without the browser.
2. If more than one browser is connected, ask the user which one to use.
3. Use one tab for the whole session. Create it once, then navigate within it.
4. On the first page load, read the account shown in the page header. If it is not the account the CLI is authenticated as, stop and ask the user.

## 2. Show a page

| Resource | Path |
|---|---|
| Project | `/projects/<project-id>/overview` |
| Discover | `/projects/<project-id>/discovery` |
| Discovery run | `/projects/<project-id>/discovery/<discovery-id>` |
| Discovery version | `/projects/<project-id>/discovery/<discovery-id>/versions/<version-id>` |
| Changesets | `/projects/<project-id>/changesets` |
| API keys | `/settings/api-keys` |
| Git | `/settings/git` |
| Runners | `/settings/runners` |

1. Navigate the tab to `<base-url><path>`, or move there with the page's own tabs and sidebar when already inside the project.
2. Wait for the page to load, then take a screenshot to confirm it shows what you expect.
3. Hover over the element you are describing so the user can see where to look.
4. Say in the chat, in one or two sentences, what is on screen and why it matters.
5. Stay on the page until the next step is ready. Do not close the tab.

Never open `/settings` or `/projects` on their own: on admin accounts `/settings` lists every user's name and email.

## 3. Clicking

- Navigation needs no approval: tabs, sidebar links, and version names.
- Anything that changes state needs the user's explicit yes first: Start, Generate more versions, Save, Create key, Revoke, Delete, Run, Cancel, and sending a message in a run's chat.
- Credentials are the user's. Open the page, point at the control, and wait while they act. Never read, copy, or type a key.
- Click by element reference from a fresh page read, never by coordinates from an earlier screenshot. References change when the page updates, so read the page again before each click.
- While a run is working, the button beside its chat box is Stop and Enter sends a message. Do not send a message while a version is being checked: it cancels that check.

## 4. When the browser cannot help

| Situation | Do |
|---|---|
| No browser tool, or no connected browser | Print the link and continue |
| The page header shows a different account | Stop and ask the user |
| A 500 error mentioning `URL.canParse` | Ask the user to update Chrome to version 120 or newer |
| "Project Not Found" | Check the account and the deployment base URL before retrying |

## Checklist

- [ ] Browser tool detected, or links printed instead
- [ ] One tab, and the header account matches the CLI
- [ ] Each page explained in chat, with the pointer on the relevant element
- [ ] No state-changing click without an explicit yes, and no credential handled
