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

This is the default report, best vs baseline ([report-design.md](report-design.md) section 1). The verdict, the % change and its interval are falcon's, carried in the collector's `vsBaseline`; the page never computes them. The best version and its % are falcon's change, which uses the metric's own aggregator, so the badge in figure 1 and the bracket between the two means in figure 2 are labelled as Artemis's change, not the gap between means. If there is no best version (no stored direction, or no change from Artemis yet), the script stops with the reason: tell the user instead. For a chart the user names, keep the header and footer and swap the figures, passing their colours as each item's `color`.

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
  title: [winV.label + ' is ', gain, verdict],  // one line; the project is in the eyebrow
  chips: t ? [
    { text: 'Verdict: ' + t.verdict, strong: t.verdict === 'better' },
    t.ciLowPct != null ? { text: '95% interval ' + F.pct(t.ciLowPct) + ' to ' + F.pct(t.ciHighPct) } : null,
    (n => ({ text: n + (n === 1 ? ' run' : ' runs') + ' vs ' + (S.baseline.readings[key] || base.count) + ' for the baseline' }))(t.readings != null ? t.readings : winM.count),
  ].filter(Boolean) : [{ text: 'No verdict from Artemis for this metric' }],
});

const page = document.getElementById('page');

// Figure 1: per metric, two bars: the baseline and the version Artemis ranks best for that metric (falcon's winner).
const changed = 'What changed: ' + winV.experimentTitle.charAt(0).toLowerCase() + winV.experimentTitle.slice(1);
// With one run per side there is no verdict: every version against the baseline, labelled as unconfirmed.
const singleRun = base.count === 1 && counts.every(c => c === 1);
const panels = S.metrics.filter(m => m.role !== 'reference').map(m => {
  const pw = (S.perMetricWinners[m.key] || {}).raw, b = S.baseline.metrics[m.key];
  if (singleRun) {
    const all = S.versions.filter(x => x.metrics[m.key] && x.metrics[m.key].mean != null)
      .sort((p, q) => (q.metrics[m.key].pctBetter ?? -1e9) - (p.metrics[m.key].pctBetter ?? -1e9));  // no value: last
    const vs = all.slice(0, 8);  // more bars than this stop being readable in one panel
    if (!b || b.mean == null || !vs.length) return null;
    return { title: m.key, unit: m.unit || '', note: '1 run each, not confirmed' + (all.length > vs.length ? ', the best ' + vs.length + ' of ' + all.length : ''),
      bars: [{ label: 'Baseline', value: b.mean }].concat(vs.map(x => ({ label: 'Artemis ' + x.label, value: x.metrics[m.key].mean }))) };
  }
  const v = pw && S.versions.find(x => x.version === pw.version), vm = v && v.metrics[m.key];
  if (!b || !vm || b.mean == null || vm.mean == null) return null;
  const vb = vm.vsBaseline, real = vb && (vb.verdict === 'better' || vb.verdict === 'worse');
  const why = !vb ? '' : vb.verdict === 'noise' ? ', within the noise' : vb.verdict === 'pending' ? ', too few runs to tell' : '';
  // No timesBetter (no direction, or a fall of 100% or more) means no badge, never "no change".
  const same = pw.timesBetter != null && F.times(pw.timesBetter) === '1.00×';
  const badge = pw.timesBetter == null ? null : same ? { text: 'no change', tone: 'flat' } : {
    text: (pw.pctBetter >= 0 ? F.times(pw.timesBetter) + ' better' : F.times(1 / pw.timesBetter) + ' worse') + why,
    dir: vm.mean > b.mean ? 'up' : 'down',  // the raw change; colour alone carries the verdict (ART-2549)
    tone: real ? (vb.verdict === 'better' ? 'good' : 'bad') : 'flat' };
  return { title: m.key, unit: m.unit || '', base: { label: 'Baseline', value: b.mean }, best: { label: 'Artemis ' + v.label, value: vm.mean }, badge };
}).filter(Boolean);
const f1 = R.figure(page, { question: singleRun ? 'The baseline against each version, 1 run each' : panels.length > 1 ? 'The baseline against the best version, per metric' : 'The baseline against the best version' });
R.headline(f1.top, {
  left: { k: 'Baseline', v: F.num(base.mean, 2), unit },
  mid: { big: F.pct(up ? win.pctBetter : -win.pctBetter), small: F.times(win.timesBetter) + ' better than the baseline, as Artemis measures it' },
  right: { k: 'Best version · ' + winV.label, v: F.num(winM.mean, 2), unit },
});
R.baselineBest(f1.chart, panels);
f1.bullets([changed]);
f1.caption(singleRun ? 'One run of each, so no version is confirmed better or worse: rerun the baseline and the versions you like to find out.'
  : 'Each panel is one metric: the baseline and the version Artemis ranks best for it, as means. The badge is Artemis’s change, on the metric’s own aggregator, as in the Web UI.');

// Figure 2: every run of the target metric, the baseline against the best version, only when the collector had each reading.
const runsKnown = !singleRun && Array.isArray(base.runs) && Array.isArray(winM.runs);
if (runsKnown) {
  const fr = R.figure(page, { question: 'Every benchmark run: the baseline against the best version' });
  R.compareRuns(fr.chart,
    { label: 'Baseline', sub: sha, runs: base.runs, mean: base.mean, color: 'var(--ar-baseline)' },
    { label: winV.label, sub: 'best version', runs: winM.runs, mean: winM.mean },
    { pctText: 'Artemis: ' + F.pct(win.pctBetter) + (t ? '  (' + t.verdict + ')' : ''), axisLabel: key + ' (' + unit + ', ' + (up ? 'higher' : 'lower') + ' is better)',
      aria: key + ', every run: baseline mean ' + F.num(base.mean, 2) + ' against ' + winV.label + ' mean ' + F.num(winM.mean, 2) });
  const worstWin = up ? Math.min(...winM.runs) : Math.max(...winM.runs), bestBase = up ? Math.max(...base.runs) : Math.min(...base.runs);
  const clear = up ? worstWin > bestBase : worstWin < bestBase;
  fr.bullets([
    clear ? '<b>No overlap:</b> all ' + winM.runs.length + ' ' + winV.label + ' runs beat every baseline run'
          : '<b>Overlap:</b> some ' + winV.label + ' runs sit inside the baseline’s range',
    'Weakest ' + winV.label + ' run ' + F.num(worstWin, 2) + ' ' + unit + ' against the baseline’s best ' + F.num(bestBase, 2) + ' ' + unit,
  ]);
}

// Next figure: every version's change with its 95% interval, which one run per side can't support.
if (!singleRun) {
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
}

// The Composite score per version, in the order they were made: its own axis, no zero line, never the verdict.
const fits = S.versions.filter(v => v.fitness != null).map(v => v.fitness);
if (fits.length >= 3 && new Set(fits).size > 1) {  // a flat line says nothing a sentence can't: the method note says it
  const fc = R.figure(page, { question: 'Composite score per version (the platform’s roll-up of the metrics by importance)' });
  R.trajectory(fc.chart, S.versions.map(v => ({ label: v.label, y: v.fitness, gapText: 'no score', mark: v.version === win.version,
    tip: [v.label + ': Composite score ' + (v.fitness == null ? 'none' : F.num(v.fitness, 2))] })),
    { yLabel: 'Composite score', aria: 'Composite score per version, in the order the versions were made' });
  const scored = S.versions.filter(v => v.fitness != null), most = Math.max(...scored.map(v => v.fitness));
  const tops = scored.filter(v => v.fitness === most).map(v => v.label);  // the score tops out, so several versions can share it
  fc.bullets([
    '<b>Highest Composite score, ' + F.num(most, 2) + ':</b> ' + tops.join(', ') + (tops.length > 1 ? ' share it' : ''),
    scored.length < S.versions.length ? (S.versions.length - scored.length) + ' of ' + S.versions.length + ' versions have no score' : '',
  ].filter(Boolean));
  fc.caption('Each version’s Composite score, as the Web UI lists it. It is not a verdict: the figures above decide which version is better. The ring marks ' + winV.label + '.');
}

// Method note.
const agent = winV.experimentStatus;
R.bullets(page, [
  perVersion + ' benchmark runs per version, ' + base.count + ' for the baseline, on the same runner',
  'Verdicts, % changes and 95% intervals are Artemis’s own (artemis discovery compare), as the Web UI shows them',
  fits.length >= 3 && new Set(fits).size === 1 ? 'Every scored version has the same Composite score, ' + F.num(fits[0], 2) : '',
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
| `baselineBest(el, panels, {decimals})` | One panel per metric: baseline and best as two bars, values on the bars, no grid; panels `{title, unit, base: {label, value}, best: {label, value}, badge: {text, tone}, note}`, or `bars: [{label, value}]` (baseline first) for every version; `tone` is `good`, `bad` or `flat` |
| `stackedBars(el, rows, {aria, note})` | One horizontal bar per row split into segments, total at the end; rows `{label, sub, segments: [{name, value, color}]}`; pair with `fig.key` |
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
