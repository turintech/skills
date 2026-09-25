# HTML report kit

For hosts that show an HTML page (Claude Code, GitHub Copilot, the fallback). Write a short page script; the kit draws the figures, the template supplies the look, and the checker catches the faults a screenshot misses.

## Build and check

```bash
python3 "<skill-dir>/scripts/collect_discovery.py" --run-id "<run-id>" --output /tmp/snapshot.json
# or every run in a project: --project "<project-id>"
# write /tmp/page.js (below), then:
python3 "<skill-dir>/scripts/build_report.py" --snapshot /tmp/snapshot.json --page /tmp/page.js \
  --title "<short name>" --output /tmp/report.html
python3 "<skill-dir>/scripts/check_report.py" /tmp/report.html
```

Fix everything `check_report.py` reports before sharing. Without Chrome it runs its static checks only and says so; then open the page and look at it.

## The page script

It runs after the kit, with two globals: `ArtemisReport` and `SNAPSHOT`. Never declare a top-level `top`, `name`, `parent`, `status`, `length` or `origin`.

```js
const R = ArtemisReport, S = SNAPSHOT, F = R.fmt;
const key = S.metrics.find(m => m.kind === 'target' && m.role !== 'reference').key;
const base = S.baseline.metrics[key], win = S.perMetricWinners[key].raw;
const winV = S.versions.find(v => v.version === win.version);

R.header(document.getElementById('header'), {
  eyebrow: 'Artemis Discovery · ' + key,
  title: [winV.label + ' is ', { em: F.times(winV.metrics[key].timesBetter, 1) + ' faster' }, ' than the original'],
  lede: 'What ran, how many versions, how many measurements each.',
  prov: ['run ' + S.run.id.slice(0, 8), 'baseline ' + S.run.baselineVersionSha.slice(0, 7)],
  link: { href: S.run.webUrl },
});

const page = document.getElementById('page');
const fig = R.figure(page, { n: 1, question: 'How much faster is each version?' });
R.rankedBars(fig.chart, S.rankings[key].map(r => ({
  label: r.label, sub: F.short(S.versions.find(v => v.version === r.version).experimentTitle),
  value: r.pctBetter, text: F.pct(r.pctBetter),
  color: r.version === win.version ? 'var(--ar-accent)' : 'var(--ar-neutral)',
})), { aria: key + ' change per version against the original' });
fig.finding(winV.label + ' is the fastest.', 'One or two sentences of evidence, with numbers from the snapshot.');
fig.caption('What a mark is, the baseline commit, and the source command.');
```

## API

| Call | Draws |
|---|---|
| `header(el, {eyebrow, title, lede, prov, link})` | Eyebrow, the finding as the title (`title` may mix strings and `{em}` for the accent), lede, provenance, Open in Artemis |
| `headline(el, {left, mid, right})` | Baseline → change → best: `{k, v, unit, n}` on each side, `{big, small}` in the middle |
| `figure(parent, {n, question})` | A figure card; returns `{chart, key(items), finding(bold, rest), caption(text)}` |
| `rankedBars(el, rows, {base, min, max, refs, tickFormat, note})` | Horizontal bars from `base`; rows `{label, sub, value, text, color, faded, strong, tip}` |
| `strip(el, groups, {band, refs, domains, axisLabel})` | Every measurement as a dot per group; two `domains` break the axis |
| `boxes(el, groups, {refs, axisLabel, valueDecimals})` | Box plots with every measurement overlaid; pair with `fig.key(R.BOX_KEY)` |
| `scatter(el, points, {xLabel, yLabel, ratioLines})` | Points `{x, y, color, faded, shape: 'diamond', label, tip}`; `ratioLines: [{k, label, strong}]` for y = k·x |
| `trajectory(el, points, {zero, annotations, yLabel, yFormat})` | Values in version order; `y: null` is a gap; `annotations: [{after, text}]` marks a steer |
| `table(el, headers, rows, numericColumns)` | A plain table; put it in `<details class="ar-details">` for the full version list |
| `stats(values)` | `{n, min, q1, med, q3, max, mean}` |
| `fmt.num / pct / times / share / short` | Number formats; `short` trims a title with an ellipsis |
| `series(i)` | The i-th categorical colour, for runs or groups |

Colour tokens: `--ar-accent` (the story's hero), `--ar-neutral`, `--ar-base` (the original), `--ar-band`, `--ar-c1` to `--ar-c6` (validated categorical order).

Label gutters are sized from the labels, so long experiment titles do not overflow; still pass `F.short(title)` as `sub`.
