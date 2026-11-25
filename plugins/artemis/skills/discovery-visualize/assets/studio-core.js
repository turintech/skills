/* The studio's pure logic: no DOM, no React, no snapshot globals. build_studio.py inlines this file into chart-studio.html at
   the template's core placeholder, inside the page's own scope, and the tests run these same functions in node. */
/* leader-steps:start */
/* Each new leader, read from the collector's runningBest[metric] (generation order, the best mean so far): a version is a new
   leader where it is its own bestVersion. The first starts the count; n numbers the later ones from 1. No interval is read,
   so no new leader is called clear of, or within noise of, another. Returns [{ version, first, n }]. */
function leaderSteps(series) {
  var out = [];
  (series || []).forEach(function (r) { if (r.mean != null && r.bestVersion === r.version) out.push({ version: r.version, first: !out.length, n: out.length }); });
  return out;
}
/* leader-steps:end */
/* has-intervals:start */
function hasIntervals(D) {
  return D.versions.some(function (v) { return Object.keys(v.metrics || {}).some(function (k) { var x = (v.metrics[k] || {}).vsBaseline; return !!(x && x.ciLowPct != null); }); });
}
/* has-intervals:end */
/* best-corner:start */
// The corner that is better on both metrics, from each one's stored direction (two lower-is-better metrics: down and left).
// Every trade-off view plots a metric its own way round, its values or its % change, so this one rule places the corner.
function bestCorner(mx, my) {
  var x = mx.higherIsBetter === false ? "left" : "right", y = my.higherIsBetter === false ? "bottom" : "top";
  return { x: x, y: y, arrow: y === "top" ? (x === "right" ? "↗" : "↖") : (x === "right" ? "↘" : "↙") };
}
/* best-corner:end */
/* tradeoff-core:start */
// The trade-off's rules, in one place. What a run is comes from the collector (metrics[].role "budget" and its cap, tradeoffMetrics,
// externalReferences); nothing here reads a metric's name.
var SAME_SIZE = 0.001;  // a reference within 0.1% of the cap is "the same size"
// The labels on the Pareto front of metrics kx and ky, as the collector stored it (fronts, by pareto_front on falcon's means, the
// versions that passed the gate); null when the snapshot stores none. The page works out no front itself.
function frontOf(S, kx, ky) { var f = (S && S.fronts) || {}; return ((f[kx] || {})[ky] || (f[ky] || {})[kx]) || null; }
// The front's staircase between two neighbours on it (sorted by x): the corner both of them beat, the worse value on each axis.
function stairCorner(a, b, axes) {
  var worse = function (ax, u, v) { return ax.hib ? Math.min(u, v) : Math.max(u, v); };
  return { x: worse(axes[0], a.x, b.x), y: worse(axes[1], a.y, b.y) };
}
// The Plot views a pair offers, the first the one it opens on: every pair opens on the metrics' own values, the original at its real
// value. A pair with the run's budget metric (a stated size cap) adds the other metric within the cap; every pair has Artemis's % change.
function tradeoffViews(mx, my) { return mx.role === "budget" || my.role === "budget" ? ["values", "quality", "pct"] : ["values", "pct"]; }
// Every reading behind these metrics is one run against one: no interval, so nothing can be called significant.
function measuredOnce(versions, readings, keys) {
  return keys.every(function (k) {
    return (readings[k] == null || readings[k] <= 1) && versions.every(function (v) { var vb = ((v.metrics || {})[k] || {}).vsBaseline; return !vb || (vb.readings || 0) <= 1; });
  });
}
// The collector's --reference models on this pair: a point where it has both readings, a line where it has one; "same size" when
// its reading on the budget metric is the cap. Its failures are the referee's own lines; only the first word is shown.
function tradeoffRefs(refs, kx, ky, budget) {
  return (refs || []).map(function (r) {
    var m = r.metrics || {}, size = budget ? m[budget.key] : null;
    return { name: r.label, x: m[kx] == null ? null : m[kx], y: m[ky] == null ? null : m[ky], file: r.source ? r.source.file : null,
      same: !!(budget && budget.cap && size != null && Math.abs(size - budget.cap) / budget.cap < SAME_SIZE), size: size == null ? null : size,
      gateFailed: !!r.gateFailed, why: r.failures && r.failures[0] ? r.failures[0].split(":")[0].trim() : null };
  }).filter(function (r) { return r.x != null || r.y != null; });
}
/* tradeoff-core:end */
/* rail-views:start */
/* The chart rail's items, in order, from what the page can draw: f = { multi, tradeoff, pareto, steered, boxes, ai }. A project's
   sessions lead; the trade-off (or, where it can't be drawn, the Pareto card) comes before how the search got there; All versions
   comes last, after AI Metrics. Best against the original and Compare all versions always have data. */
function railViews(f) {
  return [].concat(f.multi ? ["sessions"] : [], ["best", "change"], f.tradeoff ? ["tradeoff"] : f.pareto ? ["pareto"] : [], f.steered ? ["time"] : [],
    f.boxes ? ["box"] : [], f.ai ? ["ai"] : [], ["table"]);
}
/* rail-views:end */
/* links:start */
/* The run's own Web UI origin (the collector's run.webOrigin), when it is https and a host: links go there and nowhere else. */
function originOf(run) { var o = String((run || {}).webOrigin || ""); return /^https:\/\/[a-z0-9.-]+(?::\d+)?$/.test(o) ? o : null; }
/* url, a trailing "/" dropped, when it is <origin>/projects/<id> followed by tail (a pattern); else null. */
function underOrigin(run, url, tail) {
  var o = originOf(run), u = String(url || "").replace(/\/$/, ""), at = o ? o + "/projects/" : null;
  return at && u.indexOf(at) === 0 && new RegExp("^[^/?#]+" + tail + "$").test(u.slice(at.length)) ? u : null;
}
function runHref(run) { return underOrigin(run, (run || {}).webUrl, "\\/discover\\/[^/?#]+"); }  // the run's Discover page
function projectHref(run) { return underOrigin(run, (run || {}).projectUrl, ""); }  // the footer's fallback
/* links:end */
/* better-phrase:start */
/* A metric's stored direction in words, and a change against the original as one plain phrase: "40.5% better than the
   original (lower is better)". p is falcon's % better, already turned the metric's way, so its sign says better or worse.
   Every card, tooltip and Conclusion that states a change says it this way, never "40.5% lower, better, lower is better". */
function dirText(m) { return m.higherIsBetter == null ? "no stored direction" : m.higherIsBetter ? "higher is better" : "lower is better"; }
// A change that rounds to 0.0% is no change: it never reads, or colours, as better or worse.
function roundsToZero(p) { return Math.abs(p) < 0.05; }
function betterPhrase(m, p) {
  if (p == null || !isFinite(p)) return null;
  var dir = m && m.higherIsBetter != null ? " (" + dirText(m) + ")" : "";
  return roundsToZero(p) ? "unchanged from the original" + dir : Math.abs(p).toFixed(1) + "% " + (p > 0 ? "better" : "worse") + " than the original" + dir;
}
/* better-phrase:end */
/* here:start */
/* Whatever the page works out itself, rather than reads from Artemis, says so in these same words in a card's ⓘ: here(what).
   Read from Artemis, it gets nothing. The report kit's here() says the same. */
function here(what) { return what + ": worked out on this page from Artemis's numbers"; }
/* here:end */
