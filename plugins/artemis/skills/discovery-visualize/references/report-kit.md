# HTML report kit

For hosts that show an HTML page (Claude Code, GitHub Copilot, the fallback). Write a short page script; the kit draws the figures, the template supplies the look, and the checker catches the faults a screenshot misses.

## Build and check

```bash
python3 "<skill-dir>/scripts/collect_discovery.py" --run-id "<run-id>" --output /tmp/discovery-snapshot.json
# or every run in a project: --project "<project-id>"
# write /tmp/page.js (below), then:
python3 "<skill-dir>/scripts/build_report.py" --snapshot /tmp/discovery-snapshot.json --page /tmp/page.js \
  --title "<short name>" --output /tmp/report.html
python3 "<skill-dir>/scripts/check_report.py" /tmp/report.html
```

Fix everything `check_report.py` reports before sharing. Without Chrome it runs its static checks only and says so; then open the page and look at it.

## The page script

It runs after the kit, with two globals: `ArtemisReport` and `SNAPSHOT`. Never declare a top-level `top`, `name`, `parent`, `status`, `length` or `origin`.

This is the default report, best vs baseline ([report-design.md](report-design.md) section 1). Significance comes from the collector's `vsBaseline`; the page never computes it. For a chart the user names, keep the header and footer and swap the figures, passing their colours as each item's `color`.

```js
const R = ArtemisReport, S = SNAPSHOT, F = R.fmt;
const key = S.metrics.find(m => m.kind === 'target' && m.role !== 'reference').key;
const def = S.metrics.find(m => m.key === key), unit = def.unit || '', up = def.higherIsBetter;
const word = up ? 'faster' : 'lower';  // the metric's own word: faster, smaller, more accurate
const base = S.baseline.metrics[key], win = S.perMetricWinners[key].raw;
const winV = S.versions.find(v => v.version === win.version), winM = winV.metrics[key], t = winM.vsBaseline;
const sha = S.run.baselineVersionSha.slice(0, 7);

R.header(document.getElementById('header'), {
  eyebrow: 'Artemis Discovery · ' + key,
  title: [winV.label + ' is ', { em: F.pct(win.pctBetter).replace('+', '') + ' ' + word }, ' than the original',
    t ? (t.significant ? ', and the gain is statistically significant' : ', but the gain is not statistically significant') : ''],
  chips: t ? [
    { text: (t.significant ? 'Statistically significant · ' : 'Not significant · ') + F.p(t.p), strong: t.significant },
    { text: '95% interval ' + F.pct(t.ciLowPct) + ' to ' + F.pct(t.ciHighPct) },
    { text: (t.n === t.nBaseline ? t.n + ' runs each' : t.n + ' runs vs ' + t.nBaseline) + ' · Welch’s t-test' },
  ] : [{ text: 'Measured once, so no significance test' }],
});

const page = document.getElementById('page');

// Figure 1: every run, the original against the best version.
const f1 = R.figure(page, { question: 'Every benchmark run: the original against the best version' });
R.headline(f1.top, {
  left: { k: 'Original', v: F.num(base.mean, 2), unit },
  mid: { big: F.pct(win.pctBetter), small: F.times(win.timesBetter) + ' the original' },
  right: { k: 'Best version · ' + winV.label, v: F.num(winM.mean, 2), unit },
});
R.compareRuns(f1.chart,
  { label: 'Original', sub: 'baseline ' + sha, runs: base.runs, mean: base.mean },
  { label: winV.label, sub: 'best version', runs: winM.runs, mean: winM.mean },
  { pctText: F.pct(win.pctBetter) + (t ? '  (' + F.p(t.p) + ')' : ''), axisLabel: key + ' (' + unit + ', ' + (up ? 'higher' : 'lower') + ' is better)',
    aria: key + ', every run: original mean ' + F.num(base.mean, 2) + ' against ' + winV.label + ' mean ' + F.num(winM.mean, 2) });
const worstWin = up ? Math.min(...winM.runs) : Math.max(...winM.runs), bestBase = up ? Math.max(...base.runs) : Math.min(...base.runs);
const clear = up ? worstWin > bestBase : worstWin < bestBase;
f1.bullets([
  clear ? '<b>No overlap:</b> all ' + winM.runs.length + ' ' + winV.label + ' runs beat every original run'
        : '<b>Overlap:</b> some ' + winV.label + ' runs sit inside the original’s range',
  'Weakest ' + winV.label + ' run ' + F.num(worstWin, 2) + ' ' + unit + ' against the original’s best ' + F.num(bestBase, 2) + ' ' + unit,
  'What changed: ' + winV.experimentTitle.charAt(0).toLowerCase() + winV.experimentTitle.slice(1),
]);

// Figure 2: every version's change with its 95% interval.
const measured = S.versions.filter(v => v.metrics[key] && v.metrics[key].pctBetter != null)
  .sort((a, b) => b.metrics[key].pctBetter - a.metrics[key].pctBetter);
const f2 = R.figure(page, { question: 'Which changes made a real difference?' });
R.forest(f2.chart, measured.map(v => {
  const m = v.metrics[key], vb = m.vsBaseline;
  return { label: v.label, sub: F.short(v.experimentTitle, 52), pct: m.pctBetter, lo: vb && vb.ciLowPct, hi: vb && vb.ciHighPct,
    p: vb && vb.p, significant: !!(vb && vb.significant), hero: v.version === win.version, note: vb ? null : 'n = ' + m.count + ', no interval' };
}), { aria: 'Change in ' + key + ' per version against the original, with 95% intervals' });
const sig = measured.filter(v => (v.metrics[key].vsBaseline || {}).significant).map(v => v.label).sort();
const not = measured.filter(v => !(v.metrics[key].vsBaseline || {}).significant).map(v => v.label).sort();
f2.bullets([
  sig.length ? '<b>Significantly ' + word + ':</b> ' + sig.join(', ') : '<b>No version is significantly ' + word + '</b>',
  not.length ? '<b>Not significant:</b> ' + not.join(', ') + ', their intervals cross 0%' : '',
  'Filled dot: significant at 95% · bar: 95% interval',
].filter(Boolean));

// Method note.
const verdict = winV.experimentStatus;
R.bullets(page, [
  (t ? t.n : base.count) + ' benchmark runs per version and for the original, on the same runner',
  'Welch’s two-sample t-test, two-sided; interval = 95% interval of the difference in means, as % of the original',
  t && t.n <= 3 ? 'With ' + t.n + ' runs each, intervals are wide' : '',
  t && verdict && (verdict === 'validated') !== t.significant ? 'Artemis’s agent labelled ' + winV.label + ' “' + verdict + '”; this test uses only the measured runs' : '',
].filter(Boolean), { quiet: true });

R.footer(page, {
  prov: ['run ' + S.run.id.slice(0, 8), S.run.runnerName ? 'runner ' + S.run.runnerName : '', 'baseline ' + sha, 'source: artemis discovery metrics ' + S.run.id.slice(0, 8)].filter(Boolean),
  link: { href: S.run.webUrl },
});
```

## API

| Call | Draws |
|---|---|
| `header(el, {eyebrow, title, chips, lede, prov, link})` | Eyebrow, the finding as the title (`title` may mix strings and `{em}` for the accent), chips, lede, and provenance when there is no footer |
| `footer(parent, {prov, link})` | Provenance and Open in Artemis at the foot of the page |
| `chips(el, items)` | A pill row; items `{text, strong, color}`, `strong` is the accent pill with a dot |
| `headline(el, {left, mid, right})` | Baseline, change, best: `{k, v, unit, n}` on each side, `{big, small}` in the middle |
| `figure(parent, {n, question})` | A figure card; returns `{top, chart, key(items), finding(bold, rest), bullets(items), caption(text)}`; `top` holds a headline inside the card |
| `bullets(el, items, {quiet})` | A full-width list; items may contain `<b>`, everything else is escaped; `quiet` for the method note |
| `compareRuns(el, base, best, {pctText, axisLabel, aria, colors})` | Every run of the original and the best version, means, ranges and the bracket between the means; `base`/`best` are `{label, sub, runs, mean, color}` |
| `forest(el, rows, {aria, header})` | Each version's % change and 95% interval; rows `{label, sub, pct, lo, hi, p, significant, hero, color, note}` |
| `rankedBars(el, rows, {base, min, max, refs, tickFormat, note})` | Horizontal bars from `base`; rows `{label, sub, value, text, color, faded, strong, tip}` |
| `strip(el, groups, {band, refs, domains, axisLabel})` | Every measurement as a dot per group; two `domains` break the axis |
| `boxes(el, groups, {refs, axisLabel, valueDecimals})` | Box plots with every measurement overlaid; pair with `fig.key(R.BOX_KEY)` |
| `scatter(el, points, {xLabel, yLabel, ratioLines})` | Points `{x, y, color, faded, shape: 'diamond', label, tip}`; `ratioLines: [{k, label, strong}]` for y = k·x |
| `trajectory(el, points, {zero, annotations, yLabel, yFormat})` | Values in version order; `y: null` is a gap; `annotations: [{after, text}]` marks a steer |
| `table(el, headers, rows, numericColumns)` | A plain table; put it in `<details class="ar-details">` for the full version list |
| `stats(values)` | `{n, min, q1, med, q3, max, mean}` |
| `fmt.num / pct / times / share / short / p` | Number formats; `short` trims a title with an ellipsis; `p` writes "p = 0.005" or "p < 0.001" |
| `series(i)` | The i-th categorical colour, for runs or groups |

Colour tokens: `--ar-accent` (the story's hero), `--ar-mark` (the original, significant versions), `--ar-quiet` (not significant), `--ar-neutral`, `--ar-band`, `--ar-c1` to `--ar-c6` (validated categorical order).

Every figure takes a per-item `color` (`rows[].color`, `groups[].color`, `points[].color`, `base.color` / `best.color`) that overrides the default, so a user's colours are drawn exactly. Any CSS colour works: `'#16a34a'` or `'var(--ar-c3)'`.

Label gutters are sized from the labels, so long experiment titles do not overflow; still pass `F.short(title)` as `sub`.
