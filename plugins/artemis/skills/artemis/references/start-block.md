# The Artemis start block

Post it right after a command starts work in Artemis, and before waiting on it; when the command runs with `--wait`, post it just before. One block per start, nothing around it: no banners or ASCII art.

Title `Artemis · <kind> started`, or `Artemis · Discovery continued` after `discovery continue`. Pad the labels to one column. Rows by kind:

| Kind | Rows |
|---|---|
| Discovery, Fix in Discovery | Project, Goal (`taskDescription`), Versions (count · model · reviewers, as passed) |
| Discovery continued | Project, Versions (`+<n>`, budget now `numVersions`) |
| Scan | Project, Rules (names), Target (`<n>` issues, or `no limit`), Model |
| Fix | Project, Issues (display ids), Model |
| Validation | Project, Version (`original`, `latest` or the SHA), Script (name), Runner, Benchmark runs (only when set). A series of validations (pairs, turns) gets one block at its start |

Take values from the command's response and from what you passed: names, not ids, and model codes, not catalogue UUIDs. Get a missing project name from `artemis --output-format json project get <project-id>` (`.name`). Leave out a row you don't know; never guess.

`Open` is last and a bare full URL, since links don't render inside a code block: the base URL `artemis status` reports plus the path in `cli-follow-along` §2's table. When the deployment's path shape isn't known, use the project link.
