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

This is the default report, best vs baseline ([report-design.md](report-design.md) section 1). The verdict, the % change and its interval are falcon's, carried in the collector's `vsBaseline`; the page never computes them. The best version and its % are falcon's change, which uses the metric's own aggregator, so the bracket between the two means in figure 1 is labelled as Artemis's change, not the gap between means. If there is no best version (no stored direction, or no change from Artemis yet), the script stops with the reason: tell the user instead. For a chart the user names, keep the header and footer and swap the figures, passing their colours as each item's `color`.

```js
const R = ArtemisReport, S = SNAPSHOT, F = R.fmt;
const key = S.metrics.find(m => m.kind === 'target' && m.role !== 'reference').key;
const def = S.metrics.find(m => m.key === key), unit = def.unit || '', up = def.higherIsBetter;
const word = up ? 'faster' : 'lower';  // the metric's own word: faster, smaller, more accurate
const base = S.baseline.metrics[key], win = S.perMetricWinners[key].raw;
if (!win) throw new Error('No best version for ' + key + ': ' + S.perMetricWinners[key].reason + '. Say so to the user instead of drawing this page.');
const winV = S.versions.find(v => v.version === win.version), winM = winV.metrics[key], t = winM.vsBaseline;
const sha = S.run.baselineVersionSha.slice(0, 7), project = S.run.projectName;
const gain = { em: F.pct(win.pctBetter).replace('+', '') + ' ' + word };
const verdict = !t ? '' : t.verdict === 'better' ? ', a real gain' : t.verdict === 'worse' ? ', a real loss' : t.verdict === 'noise' ? ', within the noise' : t.verdict === 'pending' ? ', too few runs to tell yet' : '';
const counts = S.versions.filter(v => v.metrics[key]).map(v => v.metrics[key].count);
const perVersion = Math.min(...counts) === Math.max(...counts) ? String(counts[0]) : Math.min(...counts) + ' to ' + Math.max(...counts);

R.header(document.getElementById('header'), {
  eyebrow: 'Artemis Discovery · ' + (project ? project + ' · ' : '') + key,
  title: project ? ['Artemis made ' + project + ' ', gain, verdict] : [winV.label + ' is ', gain, ' than the baseline', verdict],
  chips: t ? [
    { text: 'Verdict: ' + t.verdict, strong: t.verdict === 'better' },
    t.ciLowPct != null ? { text: '95% interval ' + F.pct(t.ciLowPct) + ' to ' + F.pct(t.ciHighPct) } : null,
    { text: (t.readings != null ? t.readings : winM.count) + ' runs vs ' + (S.baseline.readings[key] || base.count) + ' for the baseline' },
  ].filter(Boolean) : [{ text: 'No verdict from Artemis for this metric' }],
});

const page = document.getElementById('page');

// Figure 1: every run, the baseline against the best version.
const f1 = R.figure(page, { question: 'Every benchmark run: the baseline against the best version' });
R.headline(f1.top, {
  left: { k: 'Baseline', v: F.num(base.mean, 2), unit },
  mid: { big: F.pct(win.pctBetter), small: F.times(win.timesBetter) + ' the baseline, as Artemis measures it' },
  right: { k: 'Best version · ' + winV.label, v: F.num(winM.mean, 2), unit },
});
R.compareRuns(f1.chart,
  { label: 'Baseline', sub: sha, runs: base.runs, mean: base.mean },
  { label: winV.label, sub: 'best version', runs: winM.runs, mean: winM.mean },
  { pctText: 'Artemis: ' + F.pct(win.pctBetter) + (t ? '  (' + t.verdict + ')' : ''), axisLabel: key + ' (' + unit + ', ' + (up ? 'higher' : 'lower') + ' is better)',
    aria: key + ', every run: baseline mean ' + F.num(base.mean, 2) + ' against ' + winV.label + ' mean ' + F.num(winM.mean, 2) });
f1.caption('The % is Artemis’s change, on the metric’s own aggregator, as in the Web UI. The values either side are means.');
const worstWin = up ? Math.min(...winM.runs) : Math.max(...winM.runs), bestBase = up ? Math.max(...base.runs) : Math.min(...base.runs);
const clear = up ? worstWin > bestBase : worstWin < bestBase;
f1.bullets([
  clear ? '<b>No overlap:</b> all ' + winM.runs.length + ' ' + winV.label + ' runs beat every baseline run'
        : '<b>Overlap:</b> some ' + winV.label + ' runs sit inside the baseline’s range',
  'Weakest ' + winV.label + ' run ' + F.num(worstWin, 2) + ' ' + unit + ' against the baseline’s best ' + F.num(bestBase, 2) + ' ' + unit,
  'What changed: ' + winV.experimentTitle.charAt(0).toLowerCase() + winV.experimentTitle.slice(1),
]);

// Figure 2: every version's change with its 95% interval.
const measured = S.versions.filter(v => v.metrics[key] && v.metrics[key].pctBetter != null)
  .sort((a, b) => b.metrics[key].pctBetter - a.metrics[key].pctBetter);
const f2 = R.figure(page, { question: 'Which changes made a real difference?' });
R.forest(f2.chart, measured.map(v => {
  const m = v.metrics[key], vb = m.vsBaseline;
  return { label: v.label, sub: F.short(v.experimentTitle, 52), pct: m.pctBetter, lo: vb && vb.ciLowPct, hi: vb && vb.ciHighPct,
    verdict: vb && vb.verdict, n: vb ? vb.readings : m.count, hero: v.version === win.version, note: vb ? null : 'no verdict' };
}), { aria: 'Change in ' + key + ' per version against the baseline, with 95% intervals' });
const byVerdict = w => measured.filter(v => (v.metrics[key].vsBaseline || {}).verdict === w).map(v => v.label).sort();
const better = byVerdict('better'), worse = byVerdict('worse'), pending = byVerdict('pending');
f2.bullets([
  better.length ? '<b>Really ' + word + ':</b> ' + better.join(', ') : '<b>No version is clearly ' + word + '</b>',
  worse.length ? '<b>Really worse:</b> ' + worse.join(', ') : '',
  byVerdict('noise').length ? '<b>Within the noise:</b> ' + byVerdict('noise').join(', ') + ', their intervals cross 0%' : '',
  pending.length ? '<b>Too few runs to tell:</b> ' + pending.join(', ') : '',
  'Filled dot: better or worse · bar: 95% interval · verdicts from Artemis',
].filter(Boolean));

// Method note.
const agent = winV.experimentStatus;
R.bullets(page, [
  perVersion + ' benchmark runs per version, ' + base.count + ' for the baseline, on the same runner',
  'Verdicts, % changes and 95% intervals are Artemis’s own (artemis discovery compare), as the Web UI shows them',
  t && t.recommendedReadings ? 'Artemis suggests ' + t.recommendedReadings + ' runs per side to settle ' + winV.label : '',
  t && agent && (agent === 'validated') !== (t.verdict === 'better') ? 'The Experiment behind ' + winV.label + ' concluded “' + agent + '”; the verdict uses only the measured runs' : '',
].filter(Boolean), { quiet: true });

R.footer(page, {
  prov: ['run ' + S.run.id.slice(0, 8), S.run.runner ? 'runner ' + S.run.runner : '', 'baseline ' + sha, 'source: artemis discovery compare ' + S.run.id.slice(0, 8)].filter(Boolean),
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
| `compareRuns(el, base, best, {pctText, axisLabel, aria, colors})` | Every run of the baseline and the best version, means, ranges and the bracket between the means; `base`/`best` are `{label, sub, runs, mean, color}` |
| `forest(el, rows, {aria, header})` | Each version's % change and 95% interval; rows `{label, sub, pct, lo, hi, verdict, n, hero, color, note}`, all from the snapshot; `n` prints beside the verdict |
| `rankedBars(el, rows, {base, min, max, refs, tickFormat, note})` | Horizontal bars from `base`; rows `{label, sub, value, text, color, faded, strong, tip}` |
| `strip(el, groups, {band, refs, domains, axisLabel})` | Every measurement as a dot per group; two `domains` break the axis |
| `boxes(el, groups, {refs, axisLabel, valueDecimals})` | Box plots with every measurement overlaid; pair with `fig.key(R.BOX_KEY)` |
| `scatter(el, points, {xLabel, yLabel, ratioLines})` | Points `{x, y, color, faded, shape: 'diamond', label, tip}`; `ratioLines: [{k, label, strong}]` for y = k·x |
| `trajectory(el, points, {zero, annotations, yLabel, yFormat})` | Values in version order; `y: null` is a gap; `annotations: [{after, text}]` marks a steer |
| `table(el, headers, rows, numericColumns)` | A plain table; put it in `<details class="ar-details">` for the full version list |
| `stats(values)` | `{n, min, q1, med, q3, max, mean}` |
| `fmt.num / pct / times / share / short` | Number formats; `short` trims a title with an ellipsis |
| `series(i)` | The i-th categorical colour, for runs or groups |

Colour tokens: `--ar-accent` (the story's hero), `--ar-mark` (the baseline, versions falcon calls better or worse), `--ar-quiet` (noise or pending), `--ar-neutral`, `--ar-band`, `--ar-c1` to `--ar-c6` (validated categorical order).

Every figure takes a per-item `color` (`rows[].color`, `groups[].color`, `points[].color`, `base.color` / `best.color`) that overrides the default, so a user's colours are drawn exactly. Any CSS colour works: `'#16a34a'` or `'var(--ar-c3)'`.

Label gutters are sized from the labels, so long experiment titles do not overflow; still pass `F.short(title)` as `sub`.
