# Maintain issues report

For a summary of a project's Maintain board, and for "chart", "graph" or "visualise" its issues: draw this page by default when you summarise the board (§4 in SKILL.md). It uses the Discovery report's kit, template and checker by path, from `discovery-visualize` installed beside this skill ([report-kit.md](../../discovery-visualize/references/report-kit.md)); only the data and the figures differ. Here `<maintain-dir>` is the folder that holds maintain's SKILL.md. If `<maintain-dir>/../discovery-visualize/scripts/build_report.py` does not exist, answer in text and say the chart needs `discovery-visualize` installed too.

## Collect

```bash
artemis --output-format json maintain issues list --project "<project-id>" --status all --all > /tmp/maintain-issues.json
python3 - <<'PY'
import json
issues = json.load(open("/tmp/maintain-issues.json")).get("docs") or []
json.dump({"projectId": "<project-id>", "projectName": "<project name>",
           "webUrl": "<deployment-base-url>/projects/<project-id>/maintain/issues", "issues": issues},
          open("/tmp/maintain-snapshot.json", "w"))
PY
```

The deployment base URL is the one `artemis status` reports, and the project name is the one `artemis project get <project-id>` shows. Each issue has `severity` (critical, high, medium, low, info), `lane` (untriaged, triaged, in_progress, done), `validity` (true_positive, false_positive, not_set) and `status` (open, or closed when archived).

## The default page

Title: how many issues are open and how many are critical or high, naming only the severities present. Two figures:

1. **How severe are the open issues?** `rankedBars`, one bar per severity present, in severity order (not sorted by count), each labelled "N open · M triaged".
2. **Where do they sit on the board?** `stackedBars`, one bar per severity present, split by lane, with a lane key; the full severity-by-lane table folds out under it.

```js
const R = ArtemisReport, S = SNAPSHOT;
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];
const LANES = [['untriaged', 'Untriaged'], ['triaged', 'Triaged'], ['in_progress', 'In Progress'], ['done', 'Done']];
const open = S.issues.filter(i => i.status === 'open');
const archived = S.issues.filter(i => i.status === 'closed');
const falsePositives = archived.filter(i => i.validity === 'false_positive').length;
const bySeverity = s => open.filter(i => i.severity === s);
const present = SEVERITIES.filter(s => bySeverity(s).length);
const urgent = bySeverity('critical').length + bySeverity('high').length;
const untriaged = open.filter(i => i.lane === 'untriaged').length;
const urgentText = ['critical', 'high'].filter(s => bySeverity(s).length).map(s => bySeverity(s).length + ' ' + s).join(' and ') || 'none critical or high';

R.header(document.getElementById('header'), {
  eyebrow: 'Artemis Maintain · ' + S.projectName,
  title: [open.length + (open.length === 1 ? ' open issue, ' : ' open issues, '), { em: urgentText }, untriaged ? ', and ' + untriaged + ' not triaged yet' : ''],
  chips: [
    { text: urgentText, strong: urgent > 0 },
    { text: untriaged + ' of ' + open.length + ' untriaged' },
    { text: archived.length + ' archived' + (falsePositives ? ', ' + falsePositives + ' as false positives' : '') },
  ],
});

const page = document.getElementById('page');
const f1 = R.figure(page, { question: 'How severe are the open issues?' });
R.rankedBars(f1.chart, present.map(s => {
  const n = bySeverity(s).length, t = bySeverity(s).filter(i => i.lane !== 'untriaged').length;
  return { label: s.charAt(0).toUpperCase() + s.slice(1), value: n, text: n + ' open · ' + t + ' triaged', strong: s === 'critical' || s === 'high' };
}), { base: 0, tickFormat: v => (Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : '') });
f1.bullets([
  urgent ? '<b>' + urgentText + '</b> open: fix or triage these first' : '<b>Nothing critical or high is open</b>',
  // The full count only when it adds a severity the first line doesn't already name.
  present.some(s => s !== 'critical' && s !== 'high') ? present.map(s => bySeverity(s).length + ' ' + s).join(', ') : '',
].filter(Boolean));

const f2 = R.figure(page, { question: 'Where do they sit on the board?' });
f2.key(LANES.map((l, i) => ({ swatch: R.series(i), text: l[1] })));
R.stackedBars(f2.chart, present.map(s => ({ label: s.charAt(0).toUpperCase() + s.slice(1),
  segments: LANES.map((l, i) => ({ name: l[1], value: bySeverity(s).filter(x => x.lane === l[0]).length, color: R.series(i) })) })),
  { aria: 'Open issues by severity, split by board lane' });
const fold = R.h('details', 'ar-details'); fold.append(R.h('summary', '', 'Severity by lane, as a table')); f2.chart.append(fold);
R.table(fold, ['Severity', ...LANES.map(l => l[1]), 'Total'],
  present.map(s => [s.charAt(0).toUpperCase() + s.slice(1), ...LANES.map(l => String(bySeverity(s).filter(i => i.lane === l[0]).length)), String(bySeverity(s).length)]),
  [1, 2, 3, 4, 5]);
f2.bullets([
  untriaged ? '<b>' + untriaged + ' untriaged:</b> nobody has said yet whether they are real' : '<b>Every open issue is triaged</b>',
  'Counts are open issues by board lane; archived issues are left out',
]);

R.footer(page, { prov: ['project ' + S.projectId.slice(0, 8), 'source: Maintain issues, every page'], link: { href: S.webUrl } });
```

Save it as `/tmp/maintain-page.js`, then build and check it:

```bash
KIT="<maintain-dir>/../discovery-visualize/scripts"
python3 "$KIT/build_report.py" --snapshot /tmp/maintain-snapshot.json --page /tmp/maintain-page.js \
  --title "<project name> Maintain" --output /tmp/maintain-report.html
python3 "$KIT/check_report.py" /tmp/maintain-report.html
```

Fix everything the checker reports. Publish or open the page as `discovery-visualize`'s workflow step 6 says for your host (Claude Code: [claude-code.md](../../discovery-visualize/references/claude-code.md)). Then hand it over in the shape of its [Hand it over](../../discovery-visualize/SKILL.md#8-hand-it-over): at most four lines (open issues, critical and high, untriaged), then the link in the box, with the board, `<deployment-base-url>/projects/<project-id>/maintain/issues`, as the Artemis link.

## Truth rules

- Counts only. Severity is the scan's own rating; do not re-rank issues or add a health score.
- "Triaged" means the issue left the untriaged lane. A false positive is an issue somebody marked as one, not a guess.
- Archived (`status: closed`) is not fixed: count archived issues separately, and false positives among them.
- An empty severity is left out, not drawn as a zero-length bar.
