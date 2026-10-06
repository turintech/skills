# Discovery report design

A report exists so someone can take a conclusion away from it. Every figure answers one question and says its answer in words beside the chart. Render the snapshot; do not re-join CLI JSON.

## 0. The user's prompt takes precedence

A chart, chart type, colours, versions or layout the user asks for is drawn exactly as asked. "Box plot of all versions, best in green, worst in red, the middling ones in yellow, baseline in bright blue" gets box plots of every version in exactly those colours. Every kit figure takes a per-item `color` for this. The data truth rules still hold: real runs, gaps not zeros, `n` shown. Everything below is the default for what the prompt leaves open.

## 1. Settle the story first

Work out what the reader wants to take away before choosing a chart. Most prompts say it:

| The prompt says | The story | Figures |
|---|---|---|
| only "compare", "show", "chart", "visualise" the run (**the default**) | Best vs baseline: how much better, and is it real? | Title with the % and falcon's verdict, chips, headline, `compareRuns`, `forest`, method note |
| "is it real", "is it noise", "significant", "reliable" | Is the gain bigger than run-to-run noise? | The default, or every run against the baseline's spread (`strip`) for one version |
| "how did it go", "over time", "did steering help" | How did the search unfold? | Generation-order trajectory, annotated |
| "what did it try", "what worked", "why did it fail" | What did the agent try, and what came of it? | Versions grouped by outcome, with the agent's verdicts |
| "AI-assessed", "code quality", "what did the model think" | How did the Orchestrator model score the code? | AI Metrics, in their own figure |
| two metrics, "trade-off", "cost of" | What does one metric cost in the other? | Pareto scatter over the named axes |
| a specific chart ("a bar chart of...", "just the table") | Theirs | Exactly what they asked for (section 0) |

When the prompt names no story, build the default. Do not ask first.

**Before building anything, check what was named exists:** the run, the version number, the metric. If it does not (a "version 12" in a run of ten), say what does exist and ask; never chart the nearest match silently.

### The default: best vs baseline

In this order, with the kit calls from [report-kit.md](report-kit.md):

1. **Title:** the finding with the % and falcon's verdict: "v5 is 10.9% faster than the original, a real gain".
2. **Chips:** falcon's verdict (the strong chip only for `better`), the 95% interval, and the runs per side.
3. **Headline:** baseline mean, then the %, then the best version's mean.
4. **Figure 1, `compareRuns`:** every run of the original and the best version, the gap between the means labelled with the % and p.
5. **Figure 2, `forest`:** every measured version's % change with its 95% interval, best first.
6. **Method note** (quiet bullets): runs per version; verdicts, changes and intervals are Artemis's own (`discovery compare`), as the Web UI shows them; falcon's suggested runs when a verdict is `pending`; and, when the Artemis agent's experiment verdict disagrees with falcon's, one bullet that says so.

With one run per version there is no test: say "measured once" in a chip and skip Figure 2's intervals.

### Custom requests

When the user names the chart, build that chart, in the colours they name, with the same page anatomy and truth rules:

| The user asks for | Draw |
|---|---|
| a distribution, spread, or "how noisy" | every measurement (`strip`) below about ten per group; box plots with the points overlaid (`boxes`) from there, or whenever they ask for box plots |
| two things compared (a version and the baseline, two versions) | a two-row `strip` or `boxes`, the gap between the groups labelled when they do not overlap |
| a change over the run, or since a steer | `trajectory`, annotated at the steer |
| a relationship between two metrics | `scatter`, with ratio lines when one is a reference |
| a ranking, "which is best" | `rankedBars` of the change, best first |
| "all the runs", a project, "all the branches" | `--project`, then section 6 |

If the request fits none of these, draw it with the kit's SVG helpers in the same style, and keep one finding under it.

An unattended run (scheduled, nobody to ask) builds the default too. Three figures at most by default; more only on request.

## 2. Page anatomy

1. **Eyebrow:** project or repository and the metric key. Small, neutral.
2. **Title: the main finding, as a sentence.** It must be true of the raw measurements on the page, for example "v5 is 10.9% faster than the original, a real gain" or "No version beat the baseline". Numbers are welcome in the title; adjectives need evidence on the page.
3. **Chips** under the title: falcon's verdict, the interval and the runs per side. A one-line lede only when the task needs explaining.
4. **Headline comparison:** baseline mean, then the change (`pctBetter`, with `timesBetter` under it), then the best measured version's mean and name. It sits at the top of Figure 1's card.
5. **Figures**, each as: the **question as its heading**, the chart, then **findings as bullets** directly under it. A caption line only when a mark needs explaining.
6. **Method note:** quiet bullets under the figures.
7. **Every version** table, collapsed, when asked for.
8. **Footer:** run id, runner, baseline commit, source command, and **Open in Artemis**.

### Findings

A finding is what a reader should remember from its figure. Few words, bullets not paragraphs, one idea per bullet.

- **Lead with the answer, in bold:** "**No overlap:** all 3 v5 runs beat every original run".
- Then one fact per bullet, with numbers from the snapshot: "Weakest v5 run 2.96 fps against the original's best 2.72 fps".
- Answer the heading's question, not a description of the chart.
- Name versions by label and change: "v4, merged neighbour cell lists".
- Say when the answer is "no" or "within the noise". A report that finds nothing is still a finding.

### Captions

Optional. One line when a mark needs explaining: what a mark is (mean of `n`, or one run), the baseline commit, the source command.

## 3. The figures

**Best vs baseline (`compareRuns`).** Two rows, the original and the best version. Every run is a large dot, a tick marks the mean, a band spans slowest to fastest run (accent-soft for the best, neutral for the original). Mean labels sit above the original's row and below the best's, so they never meet the bracket between the means, which carries the % and p.

**Every version's change (`forest`).** One row per measured version, best first: the % change as a dot, its 95% interval (`vsBaseline.ciLowPct` to `ciHighPct`) as a bar, a zero line labelled "original". Filled dot: falcon says `better` or `worse`. Hollow: `noise` or `pending`. The best version in the accent; better or worse ones in ink; the rest muted grey. The right column gives the % and falcon's verdict.

**Change per version (ranked bars).** Horizontal bars of `pctBetter` (or `timesBetter`), sorted best first, from a zero line that is the baseline. Value label at each bar's end, version label on the left. The best version in the accent colour, the rest neutral. Versions with no measurement listed at the bottom as text, not as zero-length bars.

**Distributions.** When the user asks to compare distributions, show every individual run until there are about ten per version; a box plot, violin or density curve drawn from three points invents a shape. Smoothed density curves need about ten runs in every group, not just most of them; below that, use box plots with the points overlaid. Mark each group's range and mean, and label the gap between the groups when they do not overlap. With enough runs, or when the user asks for them, draw box plots with every measurement overlaid: box from first to third quartile, a line at the median, whiskers from slowest to fastest run (no outliers at these sample sizes), `n` beside each label, and a small key that says how to read a box. When the run has an in-run reference (cuBLAS beside a Triton kernel), draw the same box plots for the reference: a wide reference box means the machine moved, not the code.

**Every run against the baseline (strip plot).** One row per version, baseline first. Each individual run (`runs`) is a dot; a short tick marks the mean. A shaded band spans the baseline's min to max across the whole plot. This is the honest answer to "is it real": say how many of a version's runs fall inside the baseline band. Skip it when `count` is 1 and say so in the lede.

**Search trajectory.** `pctBetter` by version number (versions are numbered in the order they were made). A zero line for the baseline, a line through consecutive measured versions that breaks at gaps, a ring on the best version, and a value label on the points the finding mentions. Annotate what explains the shape when it is known from this conversation or the run: a steer ("steered toward the solver loops" between v5 and v6), a version set aside. Do not add a running-best line unless the reader is judging how fast the search found things.

Steers: the CLI does not list a run's past steers, and versions do not record which agent made them. Mark a steer only when this conversation sent it (`discovery-steer`) or the user says when it happened, and place it by `createdAt`: after the last version made before the steer. Never guess a steer from the shape of the line.

When the user asks for the Composite score over time, plot each version's `fitness` as its own trajectory, titled "Composite score (the platform's roll-up of the metrics by importance)", never on the same axis as a measured metric and without a zero line.

**Versions by outcome.** Cards or a compact table grouped as measured improvement, no measurable change, slower, and failed or not measured. Each row: label, the experiment title, the measured change, and the agent's verdict, visibly separate from the measurement.

**AI Metrics.** Metrics with `kind: quality` are scored by the Orchestrator model from the code, not measured. Give them their own figure, after the measured ones: `rankedBars` of each version's score per metric, with the baseline as the reference line when it has a score. Caption it "Scored by the Orchestrator model from the code; a judgement, not a measurement." Never put them in the title, the headline, `forest` or a verdict, and never average them with measured metrics. When the user asks for "all metrics", show measured metrics and AI Metrics as two separate figures.

**Pareto scatter.** Only for two named axes. Label the non-dominated points; caption it as an analytical view, not an Artemis verdict.

## 4. Visual standard

A professional data designer should be happy to put their name to it.

- **Three colours by default:** ink, a muted grey for noise, pending and supporting marks, and one accent for the best version (or everything after a steer). A second hue only for a real category the reader needs (before and after a steer). Colour by better and worse only when the user asks for it, and then exactly as they ask.
- **Validate the palette** when the dataviz skill's validator is available, in both themes.
- **Recessive structure:** faint grid lines, no chart borders, no drop shadows on marks. Axis labels name the metric and unit.
- **Label directly:** value labels on the marks the finding talks about; no legend for a single series; a legend when colour carries a category.
- **Type:** one family (IBM Plex Sans, with a system fallback) and tabular figures everywhere. No monospace anywhere in the report. Headings at least one step above body text; the title is the largest thing on the page. No `ch` width limits on report text: findings run the full width.
- **Figures sized to read:** at least 520px of drawing width, horizontal scroll on phones rather than squashing.
- **Hover** shows the exact values (mean, runs, % vs baseline, the agent's verdict). Nothing on the page depends on hover.
- Light and dark themes both designed, and a background set on the page.

## 5. What the data can and cannot say

- The best version is the raw per-metric winner (`perMetricWinners[metric].raw`). If it fails the eligibility gate, it stays the measured headline, and a note names the gate and the best eligible version.
- A version with a strong measurement and a **refuted** verdict usually means it did not beat an earlier version. Say so in the finding, from `experimentConclusion`, so the table does not read as a failure.
- Missing measurements are gaps with a reason (`executionStatus`, `lifecycle`), never zeros.
- "Real" means falcon's verdict in `vsBaseline` is `better` (or `worse` for a real loss). Never compute a p-value, interval or verdict in the page or by hand.
- Always show the runs beside a verdict. Say "within the noise" for `noise`, never "worse", and "too few runs to tell" for `pending`.
- Say what the runs show too: "all 3 v1 runs beat all 3 baseline runs", or "two of v2's runs sit inside the baseline band".
- One direction per metric, from the snapshot (`higherIsBetter`, the platform's). When it is `null`, ask which way is better before naming a winner.
- No single overall winner across several objectives unless the user gives the rule.

## 6. Comparing several runs

When the user asks about a project, several runs, or "all the branches", collect every run (`artemis discovery list --project <id> --all`, then the collector per run) and compare versions across them.

- **Each run has its own baseline measurement,** and the same code can measure differently on different days. Never rank raw values across runs. Compare each version against its own run's baseline (`pctBetter`, `timesBetter`).
- **Look for a built-in control first.** A reference measured in the same benchmark process (cuBLAS next to a Triton kernel, a reference implementation next to the candidate) cancels machine drift: rank by candidate ÷ reference. The collector finds these pairs (`references`) and gives each version `vsReference`. Check it works: the baseline's ratio should agree across runs. Say that the ratio is the report's analysis, not an Artemis score.
- **Colour follows the run,** in date order, one categorical hue each, labelled in a legend and in the figures.
- **Account for every run,** including the ones that produced nothing: all versions failed to run, still in setup, cancelled. A table of runs with what happened is usually a figure in its own right.
- Flag versions measured once, and versions that failed their correctness check, in the ranking itself (faded bars, a label), not only in the table.

## 7. Sparse states

- **Baseline only:** provenance, progress, the baseline number, and "No version has been measured yet". No arrow, no figures.
- **Nothing beat the baseline:** the title says so. Keep the forest (it shows how close each came) and lead the findings with why, from the experiment conclusions.
- **One measurement per version:** no test, no intervals, no strip plot; a chip says each number is a single run, and the change per version is `rankedBars`.
- **Several target metrics:** one headline and one ranked figure per metric, no combined winner.

## Fallback HTML

If the host has no native surface, write one self-contained `.html` file (inline CSS and JS, no npm) outside the repository unless the user asks to keep it, with the same anatomy.
