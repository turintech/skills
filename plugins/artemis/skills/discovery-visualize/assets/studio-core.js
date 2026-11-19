/* The studio's pure logic: no DOM, no React, no snapshot globals. build_studio.py inlines this file into chart-studio.html at
   the template's core placeholder, inside the page's own scope, and the tests run these same functions in node. */
/* leader-steps:start */
/* Each new leader, version by version: a version that beats every earlier one on the chart's reading (higher, or lower for a
   lower-is-better mean). The first leader starts the count. A later one is clear when its 95% interval (falcon's, % better than
   the original) sits wholly above the last clear leader's, as the trade-off card reads Artemis's intervals; otherwise it is
   within noise of that leader. Without an interval on either side, clear is null: counted as a new leader, with no claim.
   points: [{ y, lo, hi }] in version order; returns [{ i, first, clear, n, ref }], n numbering the counted leaders from 1. */
function leaderSteps(points, lowWins) {
  var out = [], best = null, ref = null, n = 0;
  points.forEach(function (p, i) {
    if (p == null || p.y == null || (best != null && !(lowWins ? p.y < best : p.y > best))) return;
    best = p.y;
    var first = !out.length, clear = first ? true : ref.hi != null && p.lo != null ? p.lo > ref.hi : null;
    out.push({ i: i, first: first, clear: clear, n: first || clear === false ? 0 : ++n, ref: first ? null : ref.i });
    if (clear !== false) ref = { i: i, lo: p.lo, hi: p.hi };
  });
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
var PCT_AXES = [{ key: "x", hib: true }, { key: "y", hib: true }];  // Artemis's % better is direction-adjusted: higher is better on both
var SAME_SIZE = 0.001;  // a reference within 0.1% of the cap is "the same size"
// a is at least as good as b on every axis and better on one: the Pareto rule, the collector's pareto_front too.
function dominates(a, b, axes) {
  var ge = true, gt = false;
  axes.forEach(function (ax) { var x = a[ax.key], y = b[ax.key]; if (ax.hib ? x < y : x > y) ge = false; if (ax.hib ? x > y : x < y) gt = true; });
  return ge && gt;
}
// The front's staircase between two neighbours on it (sorted by x): the corner both of them beat, the worse value on each axis.
function stairCorner(a, b, axes) {
  var worse = function (ax, u, v) { return ax.hib ? Math.min(u, v) : Math.max(u, v); };
  return { x: worse(axes[0], a.x, b.x), y: worse(axes[1], a.y, b.y) };
}
function onFront(pts, axes) { return pts.map(function (p) { return !pts.some(function (o) { return o !== p && dominates(o, p, axes); }); }); }
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
/* pareto-mc:start */
/* Each version's chance of being on the Pareto front, COMPUTED HERE from Artemis's intervals, not a falcon verdict.
   It moves to falcon when falcon reports it (data-contract.md says so).
   pts: [{ x, y, xlo, xhi, ylo, yhi }], each Artemis's % change with its 95% interval; axes says which way is better on each
   (PCT_AXES, the default, for a direction-adjusted % better).
   Each draw samples every version's two changes from normals: mean = Artemis's estimate, sd = the interval's half-width / 1.96
   (0 with no interval). A version is on the front in a draw when no other is at least as good on both and better on one.
   Seeded (mulberry32), so the page and the tests get the same numbers. Returns { p: [share of draws on the front],
   dominated: [[i, j], ...] where version i is ahead of version j in at least 95% of draws }. */
var MC_DRAWS = 2000, MC_SEED = 20261117;  // the draws behind each chance, and the seed that makes them the same on every load
function paretoChances(pts, draws, seed, axes) {
  var dir = axes || PCT_AXES, n = pts.length, N = draws || MC_DRAWS, a = (seed == null ? MC_SEED : seed) >>> 0;
  var rnd = function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  var normal = function () { var u = 0; while (u === 0) u = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rnd()); };
  var sd = function (lo, hi) { return lo != null && hi != null && hi > lo ? (hi - lo) / 2 / 1.96 : 0; };
  var sx = pts.map(function (q) { return sd(q.xlo, q.xhi); }), sy = pts.map(function (q) { return sd(q.ylo, q.yhi); });
  var wins = pts.map(function () { return 0; }), ahead = pts.map(function () { return pts.map(function () { return 0; }); }), xs = [], ys = [];
  for (var d = 0; d < N; d++) {
    for (var i = 0; i < n; i++) { xs[i] = pts[i].x + sx[i] * normal(); ys[i] = pts[i].y + sy[i] * normal(); }
    for (i = 0; i < n; i++) {
      var front = true;
      for (var j = 0; j < n; j++) if (j !== i && dominates({ x: xs[j], y: ys[j] }, { x: xs[i], y: ys[i] }, dir)) { ahead[j][i]++; front = false; }
      if (front) wins[i]++;
    }
  }
  var dominated = [];
  for (i = 0; i < n; i++) for (j = 0; j < n; j++) if (i !== j && ahead[i][j] >= 0.95 * N) dominated.push([i, j]);
  return { p: wins.map(function (w) { return w / N; }), dominated: dominated };
}
/* pareto-mc:end */
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
