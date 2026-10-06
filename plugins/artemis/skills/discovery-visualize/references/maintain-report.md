# Maintain issues report

For "chart", "graph" or "visualise" the issues of a project's Maintain scans. Same kit, template and checker as the Discovery report ([report-kit.md](report-kit.md)); only the data and the figures differ.

## Collect

```bash
artemis --output-format json maintain issues list --project "<project-id>" --status all --all > /tmp/maintain-issues.json
python3 - <<'PY'
import json
issues = json.load(open("/tmp/maintain-issues.json"))["docs"]
json.dump({"projectId": "<project-id>", "projectName": "<project name>",
           "webUrl": "<deployment-base-url>/projects/<project-id>/maintain", "issues": issues},
          open("/tmp/maintain-snapshot.json", "w"))
PY
```

The deployment base URL is the one `artemis status` reports. Each issue has `severity` (critical, high, medium, low, info), `lane` (untriaged, triaged, in_progress, done), `validity` (true_positive, false_positive, not_set) and `status` (open, or closed when archived).

## The default page

Title: how many issues are open and how many are critical or high, naming only the severities present. Two figures:

1. **How severe are the open issues?** `rankedBars`, one bar per severity present, in severity order (not sorted by count), each labelled "N open · M triaged".
2. **Where do they sit on the board?** A `table` of open issues: severity by lane, with a total.

```js
const R = ArtemisReport, S = SNAPSHOT;
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];
const LANES = [['untriaged', 'Untriaged'], ['triaged', 'Triaged'], ['in_progress', 'In progress'], ['done', 'Done']];
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
  title: [open.length + ' open issues, ', { em: urgentText }, untriaged ? ', and ' + untriaged + ' not triaged yet' : ''],
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
}), { base: 0, tickFormat: v => String(Math.round(v)) });
f1.bullets([
  urgent ? '<b>' + urgentText + '</b> open: fix or triage these first' : '<b>Nothing critical or high is open</b>',
  present.map(s => bySeverity(s).length + ' ' + s).join(', '),
]);

const f2 = R.figure(page, { question: 'Where do they sit on the board?' });
R.table(f2.chart, ['Severity', ...LANES.map(l => l[1]), 'Total'],
  present.map(s => [s.charAt(0).toUpperCase() + s.slice(1), ...LANES.map(l => String(bySeverity(s).filter(i => i.lane === l[0]).length)), String(bySeverity(s).length)]),
  [1, 2, 3, 4, 5]);
f2.bullets([
  untriaged ? '<b>' + untriaged + ' untriaged:</b> nobody has said yet whether they are real' : '<b>Every open issue is triaged</b>',
  'Counts are open issues by board lane; archived issues are left out',
]);

R.footer(page, { prov: ['project ' + S.projectId.slice(0, 8), 'source: Maintain issues, every page'], link: { href: S.webUrl } });
```

Build and check it like the Discovery report, with `--snapshot /tmp/maintain-snapshot.json`, then hand it over the same way (*Hand it over* in SKILL.md), with the project's Maintain page as the Artemis link.

## Truth rules

- Counts only. Severity is the scan's own rating; do not re-rank issues or add a health score.
- "Triaged" means the issue left the untriaged lane. A false positive is an issue somebody marked as one, not a guess.
- Archived (`status: closed`) is not fixed: count archived issues separately, and false positives among them.
- An empty severity is left out, not drawn as a zero-length bar.
