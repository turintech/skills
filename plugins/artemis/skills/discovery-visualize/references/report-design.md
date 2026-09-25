# Discovery report design

A report exists so someone can take a conclusion away from it. Every figure answers one question and says its answer in words beside the chart. Render the snapshot; do not re-join CLI JSON.

## 1. Settle the story first

Work out what the reader wants to take away before choosing a chart. Most prompts say it:

| The prompt says | The story | Figures |
|---|---|---|
| "how much faster", "what did we gain", "chart this run" | How much better did it get? | Headline, then change per version (ranked bars) |
| "is it real", "is it noise", "significant", "reliable" | Is the gain bigger than run-to-run noise? | Every run against the baseline's spread (strip plot) |
| "how did it go", "over time", "did steering help" | How did the search unfold? | Generation-order trajectory, annotated |
| "what did it try", "what worked", "why did it fail" | What did the agent try, and what came of it? | Versions grouped by outcome, with the agent's verdicts |
| two metrics, "trade-off", "cost of" | What does one metric cost in the other? | Pareto scatter over the named axes |
| a specific chart ("a bar chart of...", "just the table") | Theirs | Exactly what they asked for, under the same truth rules |

When the prompt names no story, and only then, ask one question before building, with a recommendation:

> What should this report help you (or the person you send it to) take away?
> 1. How much better the best version is (recommended for a first look)
> 2. Whether the gains are real or run-to-run noise
> 3. How the search went, version by version
> 4. What the agent tried and what worked

**Before building anything, check what was named exists:** the run, the version number, the metric. If it does not (a "version 12" in a run of ten), say what does exist and ask; never chart the nearest match silently.

### Custom requests

When the user names the chart, build that chart, with the same page anatomy and truth rules:

| The user asks for | Draw |
|---|---|
| a distribution, spread, or "how noisy" | every measurement (`strip`) below about ten per group; box plots with the points overlaid (`boxes`) from there, or whenever they ask for box plots |
| two things compared (a version and the baseline, two versions) | a two-row `strip` or `boxes`, the gap between the groups labelled when they do not overlap |
| a change over the run, or since a steer | `trajectory`, annotated at the steer |
| a relationship between two metrics | `scatter`, with ratio lines when one is a reference |
| a ranking, "which is best" | `rankedBars` of the change, best first |
| "all the runs", a project, "all the branches" | `--project`, then section 6 |

If the request fits none of these, draw it with the kit's SVG helpers in the same style, and keep one finding under it.

If the user cannot be asked (a scheduled or unattended run), build the default: **how much better** plus **is it real** (when there is more than one measurement per version) plus **what worked**, in that order. Three figures at most by default; more only on request.

## 2. Page anatomy

1. **Eyebrow:** project or repository, the metric key, the target files. Small, neutral.
2. **Title: the main finding, as a sentence.** It must be true of the raw measurements on the page, for example "v1 runs the simulation 3.9x faster than the original" or "No version beat the baseline". Numbers are welcome in the title; adjectives need evidence on the page.
3. **Lede:** one or two sentences on what was run: the task in plain words, how many versions, how many measurements each.
4. **Provenance line** (small, mono): run id, runner, baseline commit, collected time, and a prominent **Open in Artemis** link.
5. **Headline comparison:** baseline mean, then the change (`timesBetter` as "3.9x" when it reads naturally, otherwise `pctBetter`), then the best measured version's mean and name. Units and `n` under each number.
6. **Figures**, each as: a small "Figure N" label, the **question as its heading**, the chart, a **finding** directly under it, then a one-line caption.
7. **Every version** table, collapsed.
8. **Footer:** the task text, the CLI commands, collected time.

### Findings

A finding is what a reader should remember from its figure.

- **Lead with the answer, in bold,** then one or two sentences of evidence with numbers from the snapshot: "**Yes: every v1 run beat every baseline run.** Its slowest run, 125.3 fps, is 3.9x the fastest baseline run."
- Answer the heading's question. "How much faster is each version?" is answered by a comparison, not by a description of the chart.
- Name versions by label and change: "v4, merged neighbour cell lists".
- Say when the answer is "no" or "can't tell". A report that finds nothing is still a finding.

### Captions

One line per figure: what a mark is (mean of `n`, or one run), the baseline commit, the source command, and that percentages are mean vs baseline mean.

## 3. The figures

**Change per version (ranked bars).** Horizontal bars of `pctBetter` (or `timesBetter`), sorted best first, from a zero line that is the baseline. Value label at each bar's end, version label on the left. The best version in the accent colour, the rest neutral. Versions with no measurement listed at the bottom as text, not as zero-length bars.

**Distributions.** When the user asks to compare distributions, show every individual run until there are about ten per version; a box plot, violin or density curve drawn from three points invents a shape. Smoothed density curves need about ten runs in every group, not just most of them; below that, use box plots with the points overlaid. Mark each group's range and mean, and label the gap between the groups when they do not overlap. With enough runs, or when the user asks for them, draw box plots with every measurement overlaid: box from first to third quartile, a line at the median, whiskers from slowest to fastest run (no outliers at these sample sizes), `n` beside each label, and a small key that says how to read a box. When the run has an in-run reference (cuBLAS beside a Triton kernel), draw the same box plots for the reference: a wide reference box means the machine moved, not the code.

**Every run against the baseline (strip plot).** One row per version, baseline first. Each individual run (`runs`) is a dot; a short tick marks the mean. A shaded band spans the baseline's min to max across the whole plot. This is the honest answer to "is it real": say how many of a version's runs fall inside the baseline band. Skip it when `count` is 1 and say so in the lede.

**Search trajectory.** `pctBetter` by version number (versions are numbered in the order they were made). A zero line for the baseline, a line through consecutive measured versions that breaks at gaps, a ring on the best version, and a value label on the points the finding mentions. Annotate what explains the shape when it is known from this conversation or the run: a steer ("steered toward the solver loops" between v5 and v6), a version set aside. Do not add a running-best line unless the reader is judging how fast the search found things.

**Versions by outcome.** Cards or a compact table grouped as measured improvement, no measurable change, slower, and failed or not measured. Each row: label, the experiment title, the measured change, and the agent's verdict, visibly separate from the measurement.

**Pareto scatter.** Only for two named axes. Label the non-dominated points; caption it as an analytical view, not an Artemis verdict.

## 4. Visual standard

A professional data designer should be happy to put their name to it.

- **One accent carries the story:** the best version, or everything after a steer. Everything else is a calm neutral. A second hue only for a real category the reader needs (before and after a steer). Never colour by better and worse.
- **Validate the palette** when the dataviz skill's validator is available, in both themes.
- **Recessive structure:** faint grid lines, no chart borders, no drop shadows on marks. Axis labels name the metric and unit.
- **Label directly:** value labels on the marks the finding talks about; no legend for a single series; a legend when colour carries a category.
- **Type:** a sans for prose and headings, a mono with tabular figures for numbers and ids. Headings at least one step above body text; the title is the largest thing on the page.
- **Figures sized to read:** at least 520px of drawing width, horizontal scroll on phones rather than squashing.
- **Hover** shows the exact values (mean, runs, % vs baseline, the agent's verdict). Nothing on the page depends on hover.
- Light and dark themes both designed, and a background set on the page.

## 5. What the data can and cannot say

- The best version is the raw per-metric winner (`perMetricWinners[metric].raw`). If it fails the eligibility gate, it stays the measured headline, and a note names the gate and the best eligible version.
- A version with a strong measurement and a **refuted** verdict usually means it did not beat an earlier version. Say so in the finding, from `experimentConclusion`, so the table does not read as a failure.
- Missing measurements are gaps with a reason (`executionStatus`, `lifecycle`), never zeros.
- "Real" or "clear" needs the runs: say "all 3 v1 runs beat all 3 baseline runs", or "two of v2's runs sit inside the baseline band". Do not compute p-values or confidence intervals.
- One direction per metric, from the snapshot (`higherIsBetter`). When `higherIsBetterInferred` is true, confirm it from the run's task or ask before naming a winner.
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
- **Nothing beat the baseline:** the title says so. Keep the ranked bars (they show how close each came) and the strip plot, and lead the findings with why, from the experiment conclusions.
- **One measurement per version:** no strip plot; say in the lede that each number is a single run.
- **Several target metrics:** one headline and one ranked figure per metric, no combined winner.

## Fallback HTML

If the host has no native surface, write one self-contained `.html` file (inline CSS and JS, no npm) outside the repository unless the user asks to keep it, with the same anatomy.
