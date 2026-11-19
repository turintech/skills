# The chart studio: what the page draws

Read this when you change the studio or answer a question about one of its cards. `SKILL.md` has the commands; this file is what the page does with a snapshot. The page draws the snapshot and decides nothing the collector decides (see [data-contract.md](data-contract.md)): falcon's verdicts and intervals, the collector's Best, gate, size cap, budget metric and drawable trade-off. Leave the template's charts and wording alone: `check_report.py --studio` and the tests hold the page to them.

## Layout

- **Header:** how Best was chosen, in one line ("Best = highest Composite score across all metrics.", or "Best = the best version on <metric>." when the Web UI shows no Best or its Best has no change on the lead metric). Then each metric whose own best is another version: the 3 most important by name (importance, then the lead order), the rest behind "and N more". A hero line gives falcon's × for Best on the lead metric, its 95% CI and verdict, and says plainly when it is not significant.
- **Cards, in order:** Best against the original (each panel's change with its 95% CI); one change card with a Chart toggle (Bar or Forest, one metric pick for both); the trade-off, above the version chart; every version on one chart; the table, collapsed behind one full-width bar, "Table of all N versions". Box plots of every iteration sit under More charts, only when two or more versions have 5 or more iterations (`--only box` still draws them).
- Each Conclusion keeps three bullets at most, so a card puts its most important three first.
- Best (the Composite pick) is marked only on the headline, the Best card and the version chart's Overall score view, never on one metric's chart, where another version can lead.


## Version chart

- Its title answers "did the search keep finding better versions, and when did it stop?", e.g. "3 clear new leaders, the last at v36; none clear in the 4 versions since".
- Two views: Mean (first), each version's measured mean of one metric in its own values, and Overall score. No % change view.
- The original is a line at its mean, with a legend entry that hides it; hidden, the axis fits the versions alone.
- Clear new leaders are numbered #1, #2. A new leader inside the last clear one's 95% interval gets a dashed ring and counts as within noise. Without falcon's intervals the title says "new leader" with no claim, and there are no numbers.
- A version with no settled verdict is a plain dot named "Version": the chart and its Conclusion never say "needs more runs". Steers are not drawn or quoted here.
- The metric's leader is ringed and labelled "Top"; the good direction is printed in the metric's own way ("↓ lower is better"), never a bare "higher is better" beside a lower-is-better metric.
- On a phone (under 560px): no leader numbers or dashed rings (the title and tooltips still say them), the Top ring stays inside the plot, and its label goes on the side that covers no dot, or is left out.

## Trade-off

- The two metrics are the collector's `tradeoffMetrics`; `build_studio.py --tradeoff X,Y` sets the pair it opens on. The Plot views come from the collector's contract, never from a metric's name:
  - **Values**, first for every pair (the original sits at its real values; at 0% on a % view a reader takes it for a size of 0): both metrics in their own units, the front as a staircase, the original as a triangle, references as diamonds or dashed lines, and the cap line on the budget axis. "Better on both" sits in the corner each metric's direction gives (two lower-is-better metrics: down and left).
  - **Within the cap**, second, when one axis is the run's budget metric (`metrics[].role: "budget"`, a stated size cap): size is a budget to spend, not a goal. Each version on the other metric, best first, against the original and each reference; size as budget used (in the budget metric's own unit, and % of the cap) beside each row and in the tooltip; versions over the cap grey.
  - **% change**, last: the one view with falcon's 95% intervals and each version's chance of being on the front; Artemis's % change on both, each axis in its metric's own direction (falcon's % better with the sign turned for a lower-is-better metric, so a model 12.6% larger plots at +12.6%), and each axis tagged "higher is better" or "lower is better". The green shading and "Better on both" sit in the corner the two directions give, as in Values. The original is labelled "no change on either". Front / All (All first). The front's chance for each version and "Behind the front" come from `paretoChances()`, a seeded Monte Carlo over falcon's intervals, said on the page to be computed there; with no interval anywhere there is no ring and no chance.
- One dominance rule (`dominates()`) draws every front: at least as good on both and better on one. The front's staircase turns at the corner both neighbours beat (`stairCorner()`), so it follows each axis's direction too.
- References are only the collector's `externalReferences` (`--reference`): a point where the file has both readings, a dashed line where it has one, "Same size: ..." when its budget reading is the cap, red and "fails the gate (...)" when it fails the run's gate.
- Versions that failed the gate (`--gate-metric`) start hidden in every view; their legend entry shows struck through, and one click brings them back as red crosses, drawn at the edge when a reading is past the axes. They never set an axis on any card.
- "1 run each, so no significance" is said only when every reading behind the view is one run against one.
- Every legend mark is the chart's own shape at legend size, and everything drawn has a legend entry. Best is always labelled ("v40 · Best"). The axis menus (small) and Plot are the card's one row of controls.

## Other cards

- **Measured once** (no 95% interval on any version, decided from the snapshot): no Forest toggle or card, no numbered clear leaders, no ring or chance on the trade-off. With some intervals, the cards draw those.
- **Ranked bars, one run against one:** the bar takes the estimate's direction, green better and red worse, lighter, with no verdict word and no "Significantly"; one line says "1 run each, so no significance" with how many are better and worse on the estimate, and advises no more runs. A Conclusion line that would say nothing is left out, never drawn as an empty bullet.
- **Gate failures elsewhere:** the ranked, forest and box cards leave them out with a "Failed the gate" line; the version chart draws a cross; the table says "failed the gate, values not usable".
- **Table:** verdict signs ✓ ○ ≈ ▼ with a key, "Δ% vs original" with its 95% interval in brackets; versions that failed to run or were not measured sit behind a counted "Show failed versions (N)".
- **Tooltips**, on every card: version and experiment title; the change vs the original with falcon's 95% CI and verdict; its rank on the metric; the measured mean with its unit and iterations; then the experiment's outcome in grey. A card adds only its own lines after these. The tests read tooltips by hovering forest and trade-off points: a bar chart's tooltip follows the pointer's position, which headless Chrome does not synthesise, so the ranked bars' own lines (such as "1 run each") are checked by eye.
- **Links:** each ranked bar and forest row opens that version's Code tab in Artemis (new tab), from `run.webUrl` and the version's `id`; the footer's "Open in Artemis" uses the same URL, else `run.projectUrl`. Links go only under the run's own Web UI origin, `run.webOrigin`: `<origin>/projects/<id>/discover/<run>` (or `/projects/<id>`), and nothing else. A snapshot with no `webOrigin` has no links.

## Look and motion

- Cards fade and rise in as they first scroll into view, under 600ms (bars grow, trend dots pop in order, Best's changes count up, the Bar / Forest switch morphs); never under prefers-reduced-motion or in print.
- Box plots tint every other column faintly, full height; never a continuous scatter.
- "Download PDF" opens the print dialog in the light theme, without the controls. Charts download as PNG, SVG or CSV.
- The page inlines its data but loads its pinned chart libraries from cdnjs and unpkg, so it needs the network to draw.
