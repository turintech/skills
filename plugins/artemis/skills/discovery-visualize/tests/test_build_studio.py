#!/usr/bin/env python3
"""Checks for the chart studio page and its builder, drawn in headless Chrome."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_studio  # noqa: E402
import check_report  # noqa: E402
import collect_discovery  # noqa: E402
from studio_fixtures import (  # noqa: E402
    CHROME, VISIBLE, embedded, failed_run, late, low_then_high, probed, project_snapshot, redrawable, run_snapshot, unsteered, with_intervals,
)


class BuildTests(unittest.TestCase):
    def test_a_run_snapshot_is_one_dataset(self) -> None:
        html = build_studio.build([run_snapshot()])
        for key in ("__TITLE__", "__STUDIO_DATA__"):
            self.assertNotIn(key, html)
        data = embedded(html)["datasets"]
        self.assertEqual(len(data), 1)
        self.assertIn("snapshot", data[0])
        self.assertTrue(data[0]["id"].startswith("r-"))

    def test_tradeoff_presets_the_trade_off_axes_and_refuses_a_metric_it_cannot_draw(self) -> None:
        snap = two_targets()
        self.assertEqual(embedded(build_studio.build([snap], tradeoff="compile_runtime,latency_ms"))["tradeoff"], {"x": "compile_runtime", "y": "latency_ms"})
        self.assertNotIn("tradeoff", embedded(build_studio.build([snap])))
        for bad in ("latency_ms", "latency_ms,latency_ms", "latency_ms,no_such_metric"):
            with self.subTest(spec=bad), self.assertRaises(ValueError):
                build_studio.build([snap], tradeoff=bad)
        undirected = two_targets()
        next(m for m in undirected["metrics"] if m["key"] == "compile_runtime")["higherIsBetter"] = None
        with self.assertRaises(ValueError):  # no stored direction: no trade-off on it
            build_studio.build([redrawable(undirected)], tradeoff="compile_runtime,latency_ms")

    def test_a_snapshot_from_before_tradeoff_metrics_is_told_to_collect_again(self) -> None:
        old = two_targets()
        del old["tradeoffMetrics"]  # a good two-metric run, collected before the collector wrote the list
        ds = embedded(build_studio.build([old]))["datasets"][0]
        self.assertIn("collect it again", build_studio.drawable("tradeoff", ds))
        self.assertIn("needs two measured metrics", build_studio.drawable("tradeoff", embedded(build_studio.build([dict(old, tradeoffMetrics=[])]))["datasets"][0]))

    def test_gate_failures_never_make_a_trade_off_drawable(self) -> None:
        # The builder once counted gate failures that the page leaves out: --only tradeoff built, and the page drew nothing.
        snap = two_targets()
        compared = [v for v in snap["versions"] if (v["metrics"].get("compile_runtime") or {}).get("vsBaseline")]
        for v in compared[1:]:
            v["gateFailed"] = True
        redrawable(snap)
        ds = embedded(build_studio.build([snap]))["datasets"][0]
        self.assertIsNotNone(build_studio.drawable("tradeoff", ds))
        with self.assertRaises(ValueError):
            build_studio.build([snap], tradeoff="compile_runtime,latency_ms")

    def test_chart_ones_artemis_bar_is_the_accent_and_no_verdict_colour(self) -> None:
        # Chart 1's Artemis bar is always Artemis purple, better or worse, and the word carries the sign;
        # falcon's verdict green, amber and red start at chart 2.
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        start = page.index("function BestCard(")
        card = page[start:page.index("\nfunction ", start + 1)]
        self.assertRegex(card, r"var headCol = T\.accent;", "one colour whatever the sign: a worse Best is purple too")
        self.assertRegex(card, r'key: "head", label: [^\n]*color: T\.accent \}', "the legend draws what the bar draws")
        for verdict in ("T.better", "T.worse", "T.noise", "T.pending", "T[\"better", "T[\"worse", "--better", "--worse", "gain-soft", "loss-soft"):
            self.assertNotIn(verdict, card)
        self.assertNotRegex(card, r"(?i)green if|solid green|red if worse|red when worse")
        self.assertIn("directionOf(vb && vb.improvementPct)", card, "one sign rule, shared with the ranked bars")
        self.assertEqual(page.count("improvementPct; return p == null"), 0, "no second copy of the sign rule")

    @staticmethod
    def studio_function(name: str) -> str:
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        start = page.index("function " + name + "(")
        return page[start:page.index("\nfunction ", start + 1)]

    def test_the_trade_off_washes_its_better_and_worse_corners_softly(self) -> None:
        # The trade-off gets the HF model cards' soft corner washes, green toward better on both, red toward worse on
        # both, fading out with no hard edge, in the theme's own colours.
        wash = self.studio_function("cornerWash")
        self.assertIn('grad(uid + "-good", T.better, gx, gy), grad(uid + "-bad", T.worse, 1 - gx, 1 - gy)', wash, "green at the better corner, red opposite")
        self.assertIn('gx = corner.x === "left" ? 0 : 1, gy = corner.y === "top" ? 0 : 1', wash, "the corner follows each axis's direction")
        self.assertRegex(wash, r'h\("stop", \{ offset: 1, stopColor: color, stopOpacity: 0 \}\)', "it fades to nothing: no hard edge")
        self.assertIn('pointerEvents: "none"', wash, "it takes no pointer, so tooltips still work")
        self.assertNotRegex(wash, r"#[0-9a-fA-F]{3,8}\b", "theme tokens only, no new hex")
        for view in ("TradeOffValues", "TradeOffCard"):
            body = self.studio_function(view)
            self.assertRegex(body, r"\$\{cornerWash\(T, [^)]*\)\}\s*<\$\{RC\.CartesianGrid\}", f"{view} draws the wash first, under every mark")
        self.assertNotIn("both-area", self.studio_function("TradeOffCard"), "the hard-edged green quadrant is gone")

    def test_per_version_bars_take_the_verdict_colour_else_green_or_red_by_direction(self) -> None:
        # No neutral dashed "1 run each, so no significance" bars. A bar with falcon's verdict keeps its colour (no
        # significant difference stays amber); one with no verdict (one run, pending) is green when better, red when worse.
        if not NODE:
            self.skipTest("no node")
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        fns = build_studio.CORE.read_text(encoding="utf-8") + "\n" + "\n".join(self.studio_function(n) for n in ("vFill", "directionOf", "rankedKey", "rankedInk", "rankedSeries", "rankedWord"))
        start = page.index("var GLYPH = "); fns = page[start:page.index("\n", start)] + "\n" + page[page.index("var VERDICT = "):page.index("\n", page.index("var VERDICT = "))] + "\n" + fns
        fns += "\n" + page[page.index("var DIRECTION = "):page.index("\n", page.index("var DIRECTION_SAY = "))] + "\n"
        T = '{better: "GREEN", worse: "RED", noise: "AMBER", neutral: "GREY", pending: "PEND"}'
        call = ("var T = " + T + ", ink = function (v, p) { return rankedInk(T, rankedKey(v, directionOf(p))); };"
                "console.log(JSON.stringify({ noise_up: ink('noise', 4), noise_down: ink('noise', -4), better: ink('better', 9), worse: ink('worse', -9),"
                " pending_up: ink('pending', 3), pending_down: ink('pending', -3), none_down: ink(null, -2), zero: ink('pending', 0),"
                " rounded: [0.04, -0.04].map(function (p) { var d = directionOf(p); return [d, rankedKey('pending', d), rankedInk(T, rankedKey('pending', d)), rankedWord({ dir: d })]; }),"
                " legend: rankedSeries(T, ['noise', 'dir-better', 'same'], true).map(function (s) { return [s.key, s.color, s.label]; }) }));")
        got = json.loads(subprocess.run([NODE, "-e", fns + call], capture_output=True, text=True, timeout=60, check=True).stdout)
        self.assertEqual((got["noise_up"], got["noise_down"]), ("AMBER", "AMBER"), "no significant difference stays amber")
        self.assertEqual((got["better"], got["worse"]), ("GREEN", "RED"))
        self.assertEqual((got["pending_up"], got["pending_down"], got["none_down"]), ("GREEN", "RED", "RED"), "no verdict: green or red by direction")
        self.assertEqual(got["zero"], "GREY", "exactly 0 has no direction")
        self.assertEqual(got["rounded"], [["same", "same", "GREY", "= no change"]] * 2, "a change that rounds to 0.0% is no change: no green or red bar, no better or worse word")
        self.assertEqual(got["legend"], [["noise", "AMBER", "≈ No significant difference"], ["dir-better", "GREEN", "▲ Better than the original (1 run each)"],
                                         ["same", "GREY", "= No change (1 run each)"]],
                         "the legend lists only what is drawn")
        card = self.studio_function("RankedCard")
        self.assertIn("shape=${hbarShape(T, colorOf, true)}", card, "every bar solid")
        self.assertIn("var colorOf = function (p) { return rankedInk(T, p.key); };", card)
        self.assertIn("series = rankedSeries(T, all.map(function (r) { return r.key; }), once)", card)
        for gone in ("so no significance", "pendInk", "verdictSeries(", "strokeDasharray: pend"):
            self.assertNotIn(gone, card)
        self.assertIn("pend = !solid && ", self.studio_function("hbarShape"))
        label = self.studio_function("barLabel")
        self.assertIn('word = r.word || (r.verdict ? vWord(r.verdict) : null)', label, "a bar with no verdict still says its direction in words")
        studio = (ROOT / "references" / "studio.md").read_text(encoding="utf-8")
        ranked = next(line for line in studio.splitlines() if line.startswith("- **Ranked bars: verdict colour, else direction**"))
        self.assertIn("amber no significant difference", ranked)
        self.assertIn("No dashed or neutral outline bars", ranked)
        self.assertNotIn("so no significance", ranked)

    def test_the_sessions_card_colours_bars_as_the_per_version_chart_does(self) -> None:
        # One rule for both bar charts: falcon's verdict colour (amber included), else green or red by direction, 0 neutral.
        card = self.studio_function("SessionsCard")
        self.assertIn("key: rankedKey(verdict, dir)", card)
        self.assertIn("var colorOf = function (p) { return rankedInk(T, p.key); };", card)
        self.assertIn("rankedSeries(T, rows.map(function (r) { return r.key; })", card)
        self.assertIn("shape=${hbarShape(T, colorOf, true, true)}", card, "every bar solid, none dashed or outlined, and drawn plain (no Pick)")
        self.assertNotIn("verdictSeries(", card)

    def test_the_top_conclusion_names_three_bests_and_folds_the_rest(self) -> None:
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn(".sort(function (a, b) { return tierOf(a) - tierOf(b) || gainOf(b) - gainOf(a) || rankOf(a) - rankOf(b); })", page,
                      "top 3 by importance, then the size of the gain, then the lead order")
        self.assertIn('others.slice(0, 3).join(", ")', page)
        self.assertIn('<details class="more-best"><summary>and ${rest.length} more</summary>', page, "the rest folded, closed even in screenshots")

    def test_the_top_line_says_no_more_about_one_run_each(self) -> None:
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertNotIn("not confirmed", page)
        self.assertIn('mlabel(pm) + (one ? "" : ", " + VERDICT_SAY[verdictOf(vb)])', page)

    def test_better_on_both_never_sits_on_a_marker(self) -> None:
        if not NODE:
            self.skipTest("no node")
        fn = self.studio_function("overlaps") + "\n" + self.studio_function("cornerSpot")
        call = ("var textW = function (s) { return String(s).length * 8; }, L0 = 0, R0 = 300, T0 = 0, B0 = 200, t = 'Better on both';"
                "console.log(JSON.stringify({ free: cornerSpot({ x: 'left', y: 'bottom' }, t, [[200, 10, 216, 26]], L0, R0, T0, B0),"
                " bottom: cornerSpot({ x: 'left', y: 'bottom' }, t, [[20, 180, 36, 196]], L0, R0, T0, B0),"
                " top: cornerSpot({ x: 'right', y: 'top' }, t, [[280, 4, 296, 20]], L0, R0, T0, B0) }));")
        got = json.loads(subprocess.run([NODE, "-e", fn + "\n" + call], capture_output=True, text=True, timeout=60, check=True).stdout)
        self.assertEqual((got["free"]["inside"], got["free"]["y"]), (True, 194), "a free corner keeps the text inside it")
        self.assertIsNone(got["bottom"], "a bottom corner with a marker in it drops the text")
        self.assertEqual((got["top"]["inside"], got["top"]["y"]), (False, -8), "a top corner with a marker moves it above the plot")
        for view in ("TradeOffValues", "TradeOffCard"):
            body = self.studio_function(view)
            self.assertIn("cornerSpot(", body, view)
            self.assertIn("if (!narrow) toLabel = toLabel.concat(", body, f"{view}: on a phone only the front and Best are named")

    def test_conclusion_boxes_are_artemis_purple(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn(".means { border: 1.5px solid var(--accent);", page)
        self.assertIn(".means h3 { margin: 0 0 4px; font-size: 13px; font-weight: 600; color: var(--accent-text); }", page)
        self.assertNotRegex(page, r"\.means[^{]*\{[^}]*var\(--better")

    def test_conclusions_say_a_change_once_coloured_by_direction(self) -> None:
        if not NODE:
            self.skipTest("no node")
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        fns = build_studio.CORE.read_text(encoding="utf-8") + "\n" + "\n".join(self.studio_function(n) for n in ("directionOf", "outcome", "rankedWord"))
        consts = "\n".join(page[page.index("var " + v + " = "):page.index("\n", page.index("var " + v + " = "))] for v in ("GLYPH", "VERDICT", "DIRECTION_SAY"))
        call = ("var html = function (s) { var a = [].slice.call(arguments, 1); return s.reduce(function (o, x, i) { return o + x + (i < a.length ? a[i] : ''); }, ''); };"
                "var vw = function (v, w) { return '[' + v + ':' + (w || VERDICT_SAY[v]) + ']'; }, VERDICT_SAY = { better: 'significantly improved', worse: 'significantly regressed', noise: 'no significant difference' };"
                "console.log(JSON.stringify([outcome({ verdict: 'noise' }, true), outcome({ verdict: 'pending' }, true), outcome(null, false), outcome(null, true),"
                " rankedWord({ dir: 'better' }), rankedWord({ dir: 'same' })]));")
        got = json.loads(subprocess.run([NODE, "-e", consts + "\n" + fns + "\n" + call], capture_output=True, text=True, timeout=60, check=True).stdout)
        self.assertEqual(got, ["[noise:no significant difference]", "[none:1 run each]", "[none:no verdict]", "[none:1 run each]", "\u25b2 better", "= no change"])
        self.assertIn('class=${"num" + (d === "better" || d === "worse" ? " v-" + d : "")}', self.studio_function("chgSpan"), "the number takes the direction's colour")
        self.assertEqual(page.count('r.word = GLYPH[r.dir]'), 0, "one rankedWord, used by the ranked and sessions bars")
        self.assertEqual(page.count("r.word = rankedWord(r);"), 2)
        for card in ("RankedCard", "TimeCard", "SessionsCard"):
            self.assertIn("outcome(", self.studio_function(card), card)
            self.assertIn("chgSpan(m, ", self.studio_function(card), card)
        self.assertNotIn("numSpan(chg(", page, "every change in a Conclusion is coloured")

    def test_a_change_reads_as_one_plain_phrase(self) -> None:
        # "40.5% better than the original (lower is better)", never "40.5% lower, better, lower is better": one builder,
        # betterPhrase in studio-core, behind chart 1's subtitle and tooltip and every Conclusion's change (chgSpan).
        if not NODE:
            self.skipTest("no node")
        core = build_studio.CORE.read_text(encoding="utf-8")
        call = ("var out = []; [true, false].forEach(function (hib) { var m = { higherIsBetter: hib }; [40.5, -12, 0, 0.04].forEach(function (p) { out.push(betterPhrase(m, p)); }); });"
                "out.push(betterPhrase({ higherIsBetter: null }, 3), betterPhrase({ higherIsBetter: false }, null)); console.log(JSON.stringify(out));")
        got = json.loads(subprocess.run([NODE, "-e", core + "\n" + call], capture_output=True, text=True, timeout=60, check=True).stdout)
        self.assertEqual(got, ["40.5% better than the original (higher is better)", "12.0% worse than the original (higher is better)",
                               "unchanged from the original (higher is better)", "unchanged from the original (higher is better)",
                               "40.5% better than the original (lower is better)", "12.0% worse than the original (lower is better)",
                               "unchanged from the original (lower is better)", "unchanged from the original (lower is better)",
                               "3.0% better than the original", None], "a change that rounds to 0.0% is unchanged, never better or worse")
        stacked = re.compile(r"\d%[^,]*, (better|worse), (lower|higher) is better")
        self.assertFalse([x for x in got if x and stacked.search(x)])
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        # Its colour follows the same rule: a rounded 0 takes no green or red, in a Conclusion (chgSpan) or chart 1's subtitle (signOf).
        span = ("var NO_PCT = 'n/a', html = function (s) { var a = [].slice.call(arguments, 1); return s.reduce(function (o, x, i) { return o + x + (i < a.length ? a[i] : ''); }, ''); };"
                + self.studio_function("directionOf") + "\n" + self.studio_function("chgSpan") + "\n"
                + "var m = { higherIsBetter: false }; console.log(JSON.stringify([chgSpan(m, 0.04), chgSpan(m, -0.04), chgSpan(m, 5), chgSpan(m, -5)]));")
        spans = json.loads(subprocess.run([NODE, "-e", core + "\n" + span], capture_output=True, text=True, timeout=60, check=True).stdout)
        self.assertEqual([re.search(r"class=([^>]*)>", x).group(1) for x in spans], ["num", "num", "num v-better", "num v-worse"])
        best = self.studio_function("BestCard")
        self.assertIn('var signOf = function (vb) { var d = directionOf(vb && vb.improvementPct); return d === "same" ? null : d; };', best, "chart 1's subtitle colour: directionOf's rule, no special case")
        self.assertEqual(page.count("roundsToZero("), 1, "the rounded-zero rule lives in directionOf alone on the page")
        self.assertIn("text=${betterPhrase(p.m, identical(p.vb) ? 0 : p.vb.improvementPct) || NO_PCT}", best, "chart 1's subtitle is the one phrase")
        self.assertIn("betterPhrase(m, vb.improvementPct)", best, "and its tooltip")
        self.assertNotIn('", " + dirText(p.m)', best)
        self.assertIn("${text != null ? text : betterPhrase(m, p) || NO_PCT}", self.studio_function("chgSpan"))
        self.assertNotIn("function dirText", page, "one dirText, in studio-core")
        self.assertNotIn('" than the original" + (signOf', page)
        for src in (page, (ROOT / "assets" / "report-kit.js").read_text(encoding="utf-8")):
            self.assertFalse(re.search(r"', (better|worse), (lower|higher) is better|\", (better|worse), (lower|higher) is better", src))

    def test_a_box_hides_nothing_under_per_run_dots(self) -> None:
        # A box draws quartiles, median and whiskers only; per-run dots stay for a group with no box (too few runs, a machine).
        box = self.studio_function("boxShape")
        self.assertIn("function boxShape(T) {", box)
        self.assertIn("if (p.n < BOX_MIN || !quart) p.runs.forEach(", box, "runs drawn only where there is no box")
        self.assertNotIn("showPoints", box)
        card = self.studio_function("BoxCard")
        self.assertIn("var shape = boxShape(T);", card)
        self.assertNotIn("hd.points", card)
        self.assertIn("the whiskers reach the lowest and highest run", card, "the ⓘ says what the box and whiskers are")
        kit = (ROOT / "assets" / "report-kit.js").read_text(encoding="utf-8")
        start = kit.index("function boxes(")
        self.assertNotIn("'circle'", kit[start:kit.index("\n  function ", start + 1)], "the report kit's box plot draws no dots either")

    def test_the_leaders_over_time_card_is_only_for_a_steered_run(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn("var steered = ((D.s.steering || {}).points || []).length > 0;", page)
        self.assertIn('f.steered ? ["time"] : []', build_studio.CORE.read_text(encoding="utf-8"), "a rail item only for a steered run, a project's session too")
        self.assertIn("steered: steered", page)
        self.assertIsNone(build_studio.drawable("time", embedded(build_studio.build([run_snapshot()]))["datasets"][0]))
        bare = embedded(build_studio.build([unsteered(run_snapshot())]))["datasets"][0]
        self.assertIn("no steers", build_studio.drawable("time", bare))

    @staticmethod
    def token_blocks(page: str) -> list[str]:
        """The page's theme blocks: light, dark by preference, dark by toggle, and print."""
        return re.findall(r"(?m)^(:root \{[\s\S]*?^\}|@media \(prefers-color-scheme: dark\) \{ :root:not\(\[data-theme=\"light\"\]\) \{[\s\S]*?\} \}|:root\[data-theme=\"dark\"\] \{[\s\S]*?\}|  :root, :root\[data-theme=\"dark\"\] \{[^}]*\})", page)

    def test_verdict_colours_are_artemis_uis_tokens(self) -> None:
        # The platform's tokens on artemis-ui develop f6d00737 src/styles.css: success, destructive and warning (:425-436), dark as they
        # are (:715-720), light one step deeper where a mark or text floor fails. Every verdict token in each theme is one of them.
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        light = {"#0d9488", "#0f766e", "#fb4a38", "#de2512", "#d97706", "#b45309"}
        dark = {"#5eead4", "#fb6151", "#fbbf24"}
        verdict = ("better", "worse", "better-text", "worse-text", "gain-text", "loss-text", "noise-text", "noise", "up", "down", "eq")
        blocks = self.token_blocks(page)
        self.assertEqual(len(blocks), 4, "light, dark by preference, dark by toggle, print")
        for block in blocks:
            allowed = dark if block.startswith(("@media (prefers-color-scheme", ":root[data-theme")) else light
            found = dict(re.findall(r"--([a-z-]+): (#[0-9a-f]{6})\b", block))
            for name in verdict:
                self.assertIn(found.get(name), allowed, (name, block[:40]))

    def test_box_plots_carry_no_verdict_colours_and_the_best_stands_out(self) -> None:
        box, shape = self.studio_function("BoxCard"), self.studio_function("boxShape")
        self.assertIn('return role === "baseline" ? T.orig : role === "best" ? T["accent-text"] : T.accent;', box, "original grey, versions purple, Best darker purple")
        for gone in ("vFill(", "pendInk(", "verdictSeries(", "verdictOf("):
            self.assertNotIn(gone, box, "verdict colours are the forest's")
        self.assertIn('fillOpacity: p.best ? 1 : 0.25', shape, "the Best's box is solid")
        self.assertIn("var sw = p.best ? 3 : 2", shape, "with a thicker outline")
        self.assertIn('className: "box-best"', shape, "and its Best label")
        self.assertIn('return h("g", { "data-group": p.name }, parts);', shape, "drawn in its own box's group")
        self.assertIn("p.bestWord", shape)
        self.assertIn("fill=${T.subtle}", self.studio_function("columnBands"), "zebra bands from the theme's subtle token")
        self.assertNotIn("matchMedia", self.studio_function("columnBands"))
        self.assertIn("if (p.n < BOX_MIN || !quart) p.runs.forEach(", shape, "runs drawn only where there is no box")

    def test_every_written_change_is_coloured_by_its_direction(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn("chgSpan(m, r.pct, chg(m, r.pct))", self.studio_function("verdictLines"))
        self.assertIn("Surest gain: ${numSpan(floor.label)}, at least ${chgSpan(m, floor.ciLo,", page)
        self.assertEqual(page.count("${chgSpan(pm, vb.improvementPct, changePhrase(pm, vb.improvementPct))}"), 2, "both headline forms")
        self.assertEqual(page.count("chgSpan(pm, w.raw.pctBetter, chg(pm, w.raw.pctBetter))"), 2, "the headline and the one-card lede")
        self.assertIn("chgSpan(pm, w.eligible.pctBetter, chg(pm, w.eligible.pctBetter))", page, "the eligibility line")
        self.assertNotRegex(page, r'" alone \(" \+ chg\(|" at " \+ chg\(', "no change left as plain text in a written line")
        self.assertIn('d === "better" || d === "worse" ? " v-" + d : ""', self.studio_function("chgSpan"), "one rule, directionOf's, so a 0.0% change stays plain")
        self.assertIn(".v-better { color: var(--better-text); } .v-worse { color: var(--worse-text); }", page, "the verdict text tokens")

    def test_chart_one_has_no_line_under_its_panels(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertNotIn("palone", page)
        self.assertNotIn("Best on this metric alone:", page)

    def test_metric_names_on_chart_axes_are_14px(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn("var AXIS_NAME_PX = 14;", page)
        self.assertGreaterEqual(page.count("fontSize: AXIS_NAME_PX"), 9)
        self.assertNotRegex(page, r"value: (?:\(narrow \? \"\" : )?(?:mlabel|axisName|yLabel)[^}]*fontSize: 13", "no metric-name axis title left at 13px")

    def test_a_first_visit_opens_dark_and_a_stored_choice_wins(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_THEME = "dark"', page)
        self.assertIn('load("theme", DEFAULT_THEME)', page, "the stored theme (load/store) first, then dark")
        self.assertNotIn('load("theme", "auto")', page)
        self.assertIn('options=${[["auto", "Auto"], ["light", "Light"], ["dark", "Dark"]]}', page, "the switch still offers all three")
        self.assertIn('if (theme === "auto") r.removeAttribute("data-theme"); else r.setAttribute("data-theme", theme); store("theme", theme);', page)

    @staticmethod
    def rail(**f) -> list:
        flags = dict({"multi": False, "tradeoff": False, "pareto": False, "steered": False, "boxes": False, "ai": False}, **f)
        call = f"console.log(JSON.stringify(railViews({json.dumps(flags)})));"
        return json.loads(subprocess.run([shutil.which("node"), "-e", build_studio.CORE.read_text(encoding="utf-8") + call], capture_output=True, text=True, timeout=60, check=True).stdout)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_the_rail_lists_each_view_with_data_in_order_all_versions_last(self) -> None:
        self.assertEqual(self.rail(), ["best", "change", "table"], "a bare run: chart 1, every version, the table")
        self.assertEqual(self.rail(multi=True, tradeoff=True, pareto=True, steered=True, boxes=True, ai=True),
                         ["sessions", "best", "change", "tradeoff", "time", "box", "ai", "table"], "All versions last, after AI Metrics")
        self.assertEqual(self.rail(pareto=True), ["best", "change", "pareto", "table"], "the Pareto card only where the trade-off can't draw")
        self.assertEqual(self.rail(boxes=True), ["best", "change", "box", "table"])

    def test_the_rail_opens_on_best_with_icons_names_and_a_collapse_button(self) -> None:
        app, page = self.studio_function("App"), (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn('var vw0 = useState("best")', app, "the page opens on Best against the original, never a remembered view")
        self.assertIn('var active = views.some(function (x) { return x[0] === viewOn; }) ? viewOn : "best";', app)
        self.assertIn('table: [SummaryCard, "All versions"]', app)
        self.assertIn('aria-current=${on ? "true" : null} aria-label=${x[2]} title=${x[2]}', app, "the open view is marked, and an icon-only item keeps its name")
        self.assertIn("${railIcon(x[0])}<span class=\"rail-lab\">${x[2]}</span>", app)
        for k in ("best", "change", "tradeoff", "time", "box", "ai", "table", "sessions"):
            self.assertIn("  " + k + ": [[", page, f"an inline icon for {k}")
        self.assertIn("RAIL_ICONS.pareto = RAIL_ICONS.tradeoff;", page)
        self.assertNotRegex(self.studio_function("railIcon"), r"#[0-9a-fA-F]{3,8}\b|https?:", "icons in currentColor, nothing fetched")
        self.assertIn('class="rail-toggle" aria-expanded=${railMini ? "false" : "true"}', app, "a real collapse button")
        self.assertIn('load("railCollapsed", false)', app, "opens expanded")
        self.assertIn('store("railCollapsed", !railMini)', app, "remembers only the reader's own choice")
        self.assertIn("railMini ? RAIL_MINI : RAIL_W", app, "cards get the width the rail leaves")
        self.assertIn(".rail.mini .rail-lab { display: none; }", page)
        self.assertIn("justify-self: end;", page[page.index(".rail { position: sticky"):][:200], "flush to the content's right edge")
        self.assertIn('cls = "view" + (on ? "" : " view-off")', app, "every view is drawn, the others hidden, so selection and picks carry across")
        self.assertNotIn("More charts", app, "no folded More section")
        self.assertIn(".rail button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }", page, "a clear keyboard focus")
        self.assertIn("@media (max-width: 759px) { .studio { grid-template-columns: minmax(0, 1fr); } .rail, .rail.mini { position: static; order: -1;", page, "on a phone the rail sits above the chart")
        self.assertIn(".studio { display: block; } .view-off { display: block !important; }", page, "print shows every view in order")
        self.assertIn('document.documentElement.classList.add("print-all"); declutter();', app, "laid out before it prints")

    def test_a_view_switch_fades_out_eases_in_and_holds_the_stage(self) -> None:
        app, page = self.studio_function("App"), (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn(".view.leaving { opacity: 0; transform: translateY(-4px); transition: opacity var(--t-hover) var(--ease-enter)", page)
        self.assertIn(".view.entering { animation: view-in var(--t-highlight) var(--ease-enter) both; }", page, "200ms in on the spec's easing")
        self.assertIn("--ease-enter: cubic-bezier(.2,.8,.2,1);", page)
        self.assertIn("@media (prefers-reduced-motion: reduce) { .view.leaving, .view.entering { animation: none; transition: none;", page)
        self.assertIn("if (!MOTION) { setViewOn(k);", app, "reduced motion switches at once")
        self.assertIn('st.style.minHeight = st.offsetHeight + "px"', app, "no layout jump while it swaps")
        self.assertIn('(swap.shown[x[0]] ? ":" + swap.shown[x[0]] : "")', app, "a revealed view is drawn afresh, so its bars grow and points fade in")
        self.assertIn("shown: bump(x, k)", app, "only the entering view's count moves, so the view it leaves is not redrawn")
        self.assertNotIn("swap.n", app)
        self.assertIn("setTimeout(scheduleDeclutter, ms(\"--t-highlight\") + 40)", app, "laid out again once it has settled")
        printed = page[page.index("@media print"):]
        self.assertIn("animation: none !important; transition: none !important;", printed, "print has no animation")

    def test_the_table_reads_like_the_web_uis_versions_table(self) -> None:
        card, page = self.studio_function("SummaryCard"), (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn("table.sum th:first-child, table.sum td:first-child { position: sticky; left: 0;", page, "a sticky Version column")
        # The table sits directly in the card's .plot, which scrolls it, so the checker's sideways-scroll test measures it.
        self.assertIn('</details>', card)
        self.assertIn('</summary>\n    <table class="sum">', card, "the table directly in the card's plot, no inner scroller")
        self.assertNotIn("tbl-scroll", page)
        self.assertIn(".plot { overflow-x: auto;", page, "the plot scrolls it")
        # The Best badge is the studio's purple, with the accent text token for contrast in both themes.
        self.assertIn("border: 1px solid var(--accent); border-radius: 999px; color: var(--accent-text);", page[page.index("table.sum .badge-best"):][:300])
        self.assertIn('${r.label === bestL ? html`<span class="badge-best" title="Best version by composite score">Best</span>` : null}', card)
        self.assertIn("var bestL = isArtemisBest(D) && D.best ? D.best.label : null;", card, "only Artemis's own Best")
        # Numbers in the page's face with tabular figures, no monospace (the checker's one-family rule stands).
        self.assertIn("table.sum td.n { font-variant-numeric: tabular-nums; }", page, "tabular figures")
        self.assertNotRegex(page, r"(?i)monospace|ui-monospace", "no monospace anywhere on the page")
        self.assertIn("table.sum td.n, table.sum th.n { text-align: right; }", page, "right-aligned")
        self.assertIn("chgSpan(m, r.pct, chg(m, r.pct))", card, "the change in its direction's colour")
        self.assertIn('<span class="vword">${r.verdict === "pending" ? pendWord(true) : VERDICT[r.verdict]}</span>', card, "with the verdict word beside its sign")
        self.assertNotIn("changeInk(", card)
        self.assertIn("table.sum tbody tr:nth-child(even) td { background: var(--subtle); }", page, "zebra rows from tokens")
        # An opaque hover over the card or zebra surface, so the sticky Version cell stays solid when the table scrolls.
        self.assertIn("table.sum tbody tr:hover td { background: linear-gradient(var(--halo), var(--halo)), var(--card); }", page)
        self.assertIn("table.sum tbody tr:nth-child(even):hover td { background: linear-gradient(var(--halo), var(--halo)), var(--subtle); }", page)
        self.assertIn("table-layout: fixed;", page[page.index("table.sum { "):][:200], "fixed column widths")
        self.assertIn('var TABLE_COLS = { version: "150px", change: "190px", verdict: "190px", runs: "84px", commit: "92px" };', page)
        self.assertIn("table.sum td.what { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }", page, "a long title is cut")
        self.assertIn('<td class="wide what" title=${r.what || "no title"}>', card, "with its full text on hover")
        self.assertIn("var openTable = c.open != null ? !!c.open : true;", card, "its own view, so open")

    def test_nothing_comes_before_the_first_chart_but_the_title(self) -> None:
        app = self.studio_function("App")
        body = app[app.index('return html`<div class="page" ref=${wrap}>\n    <header>'):]
        top = body[:body.index('<div class=${"studio"')]
        for gone in ("${hero}", "headline", "${topMeans", "Means", "${leftOut}", "${summary}"):
            self.assertNotIn(gone, top, "only the title and the page's controls come before the chart")
        at = app.index('var summary = html`<div class="lede-after">')
        summary = app[at:app.index('return html`<div class="page"', at)]
        for fact in ("${hero}", '<h2 class="headline">${title}</h2>', "${leftOut}${nonFinite}${clamped}", "<${Means} text=${topMeans && topMeans.text}/>"):
            self.assertIn(fact, summary, "every lede fact, in the summary")
        self.assertIn('render(x)}${x[0] === "best" ? summary : null}</section>', app, "under its own chart, Best against the original")

    def test_one_h1_the_run_title_in_the_header_before_the_charts(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        app = self.studio_function("App")
        self.assertEqual(app.count("<h1"), 1, "one h1 on the page")
        body = app[app.index('return html`<div class="page" ref=${wrap}>'):]
        self.assertLess(body.index("<header>"), body.index('<h1 class="run-title">'))
        self.assertLess(body.index('<h1 class="run-title">'), body.index("</header>"))
        self.assertLess(body.index("</header>"), body.index('<div class=${"studio"'))
        self.assertIn("s.run.projectName || \"Discovery run \" + shortSha(s.run.id)}</h1>", app, "the run or project title")
        self.assertNotRegex(page, r"(?m)^h1 \{", "the headline's old h1 style is the .headline's now")
        checker = (ROOT / "scripts" / "check_report.py").read_text(encoding="utf-8")
        self.assertIn("if (!window.STUDIO_ONLY && (!headline || !headline.textContent.trim())) say('EMPTY HEADLINE');", checker, "a blank headline fails, not only a blank title")

    def test_the_first_paint_is_in_the_stored_or_default_theme(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        head = '<script>var PREFIX = "dv-studio:v1:", DEFAULT_THEME = "dark"; (function () { var t = DEFAULT_THEME; try { var s = localStorage.getItem(PREFIX + "theme"); if (s) t = JSON.parse(s); } catch (e) {} if (t !== "auto") document.documentElement.setAttribute("data-theme", t); })();</script>'
        self.assertIn(head, page)
        self.assertLess(page.index(head), page.index("<style>"), "set before the first paint, before the styles")
        self.assertLess(page.index(head), page.index('<link rel="stylesheet"'), "and before the font stylesheet, which an inline script would wait for")
        self.assertEqual(page.count('"dv-studio:v1:"'), 1, "the storage prefix is written once")
        self.assertEqual(page.count('DEFAULT_THEME = "dark"'), 1, "and the default theme once")
        self.assertNotIn("var PREFIX = \"", page[page.index("<style>"):], "the main script reads the head's PREFIX")

    def test_a_view_opened_from_the_rail_is_laid_out_and_the_checker_walks_the_rail(self) -> None:
        app = self.studio_function("App")
        self.assertIn("useEffect(function () { scheduleDeclutter(); var t = setTimeout(scheduleDeclutter,", app, "a revealed view gets its label layout")
        self.assertIn("onClick=${function () { openView(x[0], active); }}", app)
        self.assertIn("    setShowAll(false);\n    if (k === from) return;", app, "a rail click shows that one view, for the checker too")
        self.assertIn("railBeside() && !ONLY ? (railMini ? RAIL_MINI : RAIL_W) + 16 : 0", app, "card width and the CSS decide the rail's place by one media query")
        self.assertIn('window.matchMedia("(min-width: " + RAIL_AT + "px)")', (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8"))
        self.assertNotIn("STUDIO_RAIL", (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8"))
        checker = (ROOT / "scripts" / "check_report.py").read_text(encoding="utf-8")
        self.assertIn("steps.push({ desc: 'Rail > ' + b.textContent.trim(), go: function () {", checker, "every rail item is walked, one view at a time")
        self.assertLess(checker.index("segSteps(theme, "), checker.index("'Rail > '"), "after the theme, like it")
        self.assertLess(checker.index("'Rail > '"), checker.index("[].forEach.call(cards(), function (card, ci) {"), "the theme and the rail before the per-card steps, so they are never cut")
        self.assertIn("if (window.STUDIO_SHOW_ALL) window.STUDIO_SHOW_ALL();", checker, "a rail step's undo puts every view back for the card steps")
        self.assertIn("window.STUDIO_SHOW_ALL = START && START.more ? function () { setShowAll(true); } : null;", app)
        self.assertIn("say('WALK CUT SHORT: ' + steps.length", checker, "cutting the walk short still fails")
        self.assertIn("walk.textContent = 'step ' + i + ' of ' + steps.length", checker, "a render that runs out of time says how far the walk got")
        # An error that lands after a step's settle is named with that step, before the next step acts.
        self.assertIn("late();  // before this step acts", checker)
        self.assertIn("say(errs[seen] + ' (after ' + (prev || 'opening the page') + ')')", checker)
        self.assertLess(checker.index("late();  // before this step acts"), checker.index("undo = st.go();"))
        self.assertIn("try { prev = st.desc; undo = st.go();", checker, "a step skipped because its card already failed never takes the label")

    def test_page_notes_show_whichever_view_is_open(self) -> None:
        app = self.studio_function("App")
        notes = app[app.index("var pageNotes = "):]
        for fact in ("${leftOut}", "${nonFinite}", "${clamped}", '<p key=${"dc" + i} class="warn">${c}</p>'):
            self.assertIn(fact, notes[:notes.index("\n")], "every page-level warning is a page note")
        body = app[app.index('return html`<div class="page" ref=${wrap}>\n    <header>'):]
        self.assertLess(body.index('<div class="stage"'), body.index("${pageNotes}"), "after the charts")
        self.assertLess(body.index("${pageNotes}"), body.index("${foot}"))
        self.assertNotIn("${leftOut}", app[app.index('var summary = html`'):app.index("var pageNotes = ")], "not hidden inside one view")
        self.assertNotIn("checks) }", app, "the direction checks are no longer in the Best summary")
        self.assertIn("checks.map(function (c, i)", app, "one paragraph per direction warning")

    def test_studio_probe_renders_get_the_studio_budget(self) -> None:
        # Every view is mounted (one at a time is shown), so a studio probe walks every control; 8 s of virtual time is not enough.
        self.assertIn("STUDIO_BUDGET = 450000", (ROOT / "scripts" / "check_report.py").read_text(encoding="utf-8"))
        for name in ("test_studio.py", "test_studio_cards.py"):
            src = (ROOT / "tests" / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertNotRegex(src, r"studio_probe\(\), \d+\)", "no literal budget beside the studio probe")
                self.assertNotRegex(src, r"(?m)^\s*probe = check_report\.studio_probe\(\)[\s\S]{0,1500}?probe, \d+\)", "nor through a probe variable")

    def test_a_one_card_page_gives_its_card_the_whole_width_and_text_stays_12px(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn("railBeside() && !ONLY ?", self.studio_function("App"), "no rail on a one-card page, so no rail width taken")
        self.assertIn('fontSize: 12, fontWeight: 700, fill: "currentColor" }, "#1")', page, "the leaders legend's #1 is 12px")
        self.assertIn("font-size: 12px; font-weight: 600; line-height: 16px;", page[page.index("table.sum .badge-best"):][:400], "the Best badge is 12px")
        self.assertIn("table.sum { min-width: 0; font-size: 13px; table-layout: auto; } table.sum col { width: auto !important; }", page, "on a phone the fixed widths give way")

    def test_one_purple_and_slate_neutrals(self) -> None:
        # The platform primary (brand-500 / brand-400), never violet; slate for text and marks.
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        light, dark, _, printed = self.token_blocks(page)
        for block, want in ((light, {"accent": "#6350dc", "accent-text": "#2811bb", "fg": "#020617", "text-2": "#475569", "neutral": "#64748b", "card": "#f8fafc", "bg": "#f1f5f9", "popover": "#ffffff", "wash": "0.13"}),
                            (dark, {"accent": "#7b66ff", "accent-text": "#9e91f2", "fg": "#f8fafc", "text-2": "#cbd5e1", "neutral": "#94a3b8", "card": "#0f172a", "popover": "#1e293b", "grid": "#e2e8f026", "wash": "0.18"})):
            found = dict(re.findall(r"--([a-z0-9-]+): ([^;]+);", block))
            for name, value in want.items():
                self.assertEqual(found.get(name), value, name)
        for violet in ("#7c3aed", "#8b5cf6", "#6d28d9", "#c4b5fd"):
            self.assertNotIn(violet, page)

    def test_no_colour_or_timing_outside_the_token_blocks(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        rest = page
        for block in self.token_blocks(page):
            rest = rest.replace(block, "")
        rest = rest.replace("&#160;", "")  # an HTML entity, not a colour
        head = rest[:rest.index("/* ---------- data:")]  # the stylesheet and the token comment
        rest = re.sub(r"/\*[\s\S]*?\*/", "", rest)  # comments may cite values
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", rest), [], "a colour outside the token blocks")
        self.assertEqual(re.findall(r"(?<![\w.-])(?:[1-9]\d*|\d*\.\d+)m?s\b(?![\w-])", re.sub(r"/\*[\s\S]*?\*/", "", head)), [], "a duration outside the token blocks")
        self.assertNotIn("cubic-bezier", re.sub(r"/\*[\s\S]*?\*/", "", head).replace(self.token_blocks(page)[0], ""))
        for js in ('ms("--t-bar")', 'ms("--stagger-card")', 'ms("--t-entry")'):
            self.assertIn(js, page, "the page's motion reads the tokens")
        self.assertIn("@media (prefers-reduced-motion: reduce) { .card.playing, .card.playing *, .morph { animation: none !important; }", page)
        self.assertIn('.theme-freeze, .theme-freeze * { transition: none !important; }', page, "a theme switch has no transition")

    def test_the_dark_and_print_blocks_match_their_themes(self) -> None:
        # Dark by toggle is dark by preference, and print is the light theme: one value per token, written once per theme.
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        light, dark_pref, dark_toggle, printed = self.token_blocks(page)
        decls = lambda b: dict(re.findall(r"--([a-z0-9-]+): ([^;]+);", b))
        self.assertEqual(decls(dark_toggle), decls(dark_pref))
        colours = {k: v for k, v in decls(light).items() if not k.startswith(("t-", "stagger-", "ease", "sans", "focus", "shadow"))}
        printed_d = decls(printed)
        paper = ("bg", "card")  # light's slate-50 card on a slate-100 page; paper is white for both
        self.assertEqual({k: printed_d.get(k) for k in colours if k not in paper}, {k: v for k, v in colours.items() if k not in paper}, "print is the light theme")
        self.assertEqual([printed_d.get(k) for k in paper], ["#ffffff", "#ffffff"], "print on white paper")
        for dead in ("--steer", "--s1", "--s2", "--gain-soft", "--loss-soft"):
            self.assertNotIn(dead, page, "a token nothing reads")

    def test_best_keeps_its_halo_and_no_computed_here_label(self) -> None:
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertIn('fill: T.halo, stroke: "none", pointerEvents: "none"', self.studio_function("bestHalo"))
        for view in ("TradeOffValues", "TradeOffCard", "TimeCard"):
            self.assertIn("bestHalo(T, ", self.studio_function(view), view)
        best = self.studio_function("BestCard")
        self.assertIn('" (Top on " + mlabel(D.byKey[D.primary]) + ")"', best)
        self.assertIn("picked on this page because Artemis gives no Best on it", best, "the ⓘ says where the Top comes from")
        self.assertIn('"The page leads with the Top on " + mlabel(pm) + "."', page)
        self.assertNotRegex(page.replace("function here(", ""), r"computed here\)|, computed here\b", "no 'computed here' label on the page")
        self.assertIn('aria-label=${here("The ×, converted from Artemis\'s % change")}', page, "the hero's × says it is converted, in its ⓘ")
        self.assertIn('${ratio ? html`<span class="info" tabindex="0" role="img" aria-label=${here("The ×', page, "shown whenever the hero shows a ×")

    def test_the_rank_in_tooltips_reads_the_view_after_it_is_prepared(self) -> None:
        # DATA_NOW feeds "Rank N of M" in every version tooltip; set before the view's data exists, every rank is blank.
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertLess(page.index("var D = useMemo(function () { return s ? prep(s, failed)"), page.index("DATA_NOW = D;"))

    def test_a_project_snapshot_is_its_runs_as_sessions(self) -> None:
        data = embedded(build_studio.build([project_snapshot(3)], labels=["Build time"]))["datasets"]
        self.assertEqual(data[0]["label"], "Build time")
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-0", "run-1", "run-2"])

    def test_a_one_run_project_is_drawn_as_that_run(self) -> None:
        data = embedded(build_studio.build([project_snapshot(1)]))["datasets"]
        self.assertIn("snapshot", data[0])

    def test_the_same_run_twice_gets_two_entries(self) -> None:
        data = embedded(build_studio.build([run_snapshot(), run_snapshot()]))["datasets"]
        self.assertEqual(len({d["id"] for d in data}), 2)

    def test_data_cannot_close_its_script_element(self) -> None:
        snap = run_snapshot()
        snap["run"]["projectName"] = "A <!-- B </script><script>alert(1)</script>"
        html = build_studio.build([snap])
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertNotIn("<!-- B", html)
        self.assertEqual(embedded(html)["datasets"][0]["label"], snap["run"]["projectName"])

    def test_bad_snapshots_are_refused_not_crashed_on(self) -> None:
        no_run = run_snapshot()
        no_run["run"] = None
        no_base = run_snapshot()
        del no_base["baseline"]
        no_base_metrics = run_snapshot()
        no_base_metrics["baseline"] = {}
        no_winners = run_snapshot()
        del no_winners["perMetricWinners"]
        unmeasured = run_snapshot()
        unmeasured["metrics"] = []  # versions keep their readings, but on no metric the run defines
        cases = [
            ([[run_snapshot()]], "expected a collector snapshot"),
            ([no_run], "`run` is missing or is not a JSON object"),
            ([no_base], "`baseline` is missing"),
            ([no_base_metrics], "`baseline.metrics` is missing"),
            ([no_winners], "`perMetricWinners` is missing"),
            ([dict(run_snapshot(), versions={})], "`versions` is missing or is not a list"),
            ([dict(run_snapshot(), versions=["v1"])], "an item of `versions` is not a JSON object"),
            ([dict(run_snapshot(), metrics=["x"])], "an item of `metrics` is not a JSON object"),
            ([dict(project_snapshot(2), skipped=["x"])], "`skipped` is not a list of JSON objects"),
            ([{"schemaVersion": 2, "kind": "project", "projectId": 7, "runs": [dict(run_snapshot(), versions=[{"version": 1, "metrics": {"compile_runtime": 5}}])]}], "metric reading is not a JSON object"),
            ([unmeasured], "no measured version"),
            ([{"schemaVersion": 2, "kind": "project", "runs": [None]}], "not a JSON object"),
        ]
        for snaps, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message), contextlib.redirect_stderr(io.StringIO()):
                build_studio.build(snaps)

    def test_a_run_with_readings_on_no_defined_metric_is_left_out(self) -> None:
        project = project_snapshot(3)
        project["runs"][0]["metrics"] = []
        with contextlib.redirect_stderr(io.StringIO()) as err:
            data = embedded(build_studio.build([project]))["datasets"]
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-1", "run-2"])
        self.assertIn("left out run run-0", err.getvalue())

    def test_title_is_escaped(self) -> None:
        self.assertIn("<title>A&lt;b>&amp;</title>", build_studio.build([run_snapshot()], title="A<b>&"))

    def test_failed_versions_are_deduplicated_and_the_project_name_is_the_default_label(self) -> None:
        project = project_snapshot(2)
        for r in project["runs"]:
            r["run"]["projectName"] = "Build time"
        data = embedded(build_studio.build([project], failed=["1:1:2,2"]))["datasets"]
        self.assertEqual(data[0]["correctness"], {"1": [2]})
        # A repeat for the same session adds to it.
        data = embedded(build_studio.build([project], failed=["1:1:2", "1:1:3"]))["datasets"]
        self.assertEqual(data[0]["correctness"], {"1": [2, 3]})
        self.assertEqual(data[0]["label"], "Build time")
        project["runs"][0]["run"].pop("projectName")
        self.assertEqual(embedded(build_studio.build([project]))["datasets"][0]["label"], "Project proj-1")

    def test_failed_marks_land_on_the_named_session(self) -> None:
        data = embedded(build_studio.build([run_snapshot(), project_snapshot(2)], failed=["2:2:3,1", "1:1:2"]))["datasets"]
        self.assertEqual(data[1]["correctness"], {"2": [1, 3]})
        self.assertEqual(data[0]["correctness"], {"1": [2]})
        # A lone run stays a run: no sessions, so the page keeps the plain-run layout.
        self.assertIn("snapshot", data[0])
        self.assertNotIn("sessions", data[0])

    def test_bad_input_is_refused_with_a_reason(self) -> None:
        old = run_snapshot()
        old["schemaVersion"] = 1
        cases = [
            ([], [], [], "at least one"),
            ([old], [], [], "schemaVersion"),
            ([run_snapshot()], ["a", "b"], [], "more --label"),
            ([run_snapshot()], [], ["1-2-3"], "expected N:SESSION:VERSIONS"),
            ([run_snapshot()], [], ["2:1:1"], "no snapshot 2"),
            ([run_snapshot()], [], ["1:2:1"], "only session is 1"),
            ([project_snapshot(2)], [], ["1:3:1"], "has 2 session"),
            ([run_snapshot()], [], ["1:1:99"], "no version 99"),
            ([failed_run()], [], [], "no measured version"),
        ]
        for snaps, labels, failed, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                build_studio.build(snaps, labels, failed)

    def test_the_page_starts_in_standards_mode(self) -> None:
        self.assertTrue(build_studio.build([run_snapshot()]).startswith("<!doctype html>"))

    def test_a_run_with_no_measured_version_is_left_out_and_named(self) -> None:
        project = project_snapshot(2)
        project["runs"].insert(0, failed_run())
        project["skipped"] = [{"id": "gone-run-1", "status": "failed", "reason": "no comparison"}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            data = embedded(build_studio.build([project], failed=["1:2:1"]))["datasets"]
        self.assertEqual([s["run"]["id"] for s in data[0]["sessions"]], ["run-0", "run-1"])
        # SESSION is the number the page shows, after the left-out run: session 2 is run-1.
        self.assertEqual(data[0]["correctness"], {"2": [1]})
        self.assertIn("left out run dead-run (failed)", err.getvalue())
        self.assertIn("skipped run gone-run (failed): no comparison", err.getvalue())

    def test_cli_writes_the_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap, out = Path(tmp) / "snap.json", Path(tmp) / "studio.html"
            snap.write_text(json.dumps(run_snapshot()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as said:
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--output", str(out)]), 0)
            self.assertIn("wrote", said.getvalue())
            self.assertIn("studio-data", out.read_text(encoding="utf-8"))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(build_studio.main(["--snapshot", str(Path(tmp) / "missing.json"), "--output", str(out)]), 2)
            self.assertIn("No such file", err.getvalue())
            listed = Path(tmp) / "list.json"
            listed.write_text("[]", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(build_studio.main(["--snapshot", str(listed), "--output", str(out)]), 2)
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--output", str(Path(tmp) / "no" / "dir.html")]), 2)
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(build_studio.main(["--snapshot", str(bad), "--output", str(out)]), 2)
            self.assertIn(f"{bad} is not JSON", err.getvalue())
            # --label and --failed reach the page through the command line.
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_studio.main(["--snapshot", str(snap), "--label", "Build time", "--failed", "1:1:2", "--output", str(out)]), 0)
            data = embedded(out.read_text(encoding="utf-8"))["datasets"][0]
            self.assertEqual((data["label"], data["correctness"]), ("Build time", {"1": [2]}))


class PhoneAndDesktopLayoutTests(unittest.TestCase):
    """What a phone and a desktop show: zero, Best and verdicts in view, the chosen session marked, CSV under each top."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_a_phone_keeps_zero_best_and_verdicts_visible_and_fits_five_groups(self) -> None:
        project = project_snapshot(5)
        titles = ["Use bucket_time_keys_before_probing_hash_join_partitions in query_planner.optimize",
                  "Use BucketTimeKeysBeforeProbingHashJoinPartitionsInQueryPlannerOptimize now",
                  "Pin a3f9c2e81b7d4f06a5e3c9b2d1f8e7a6c5b4d3e2f1a0b9c8 as the seed"]
        for v, title in zip(project["runs"][0]["versions"], titles):
            v["experimentTitle"] = title
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", VISIBLE + """
          return { ranked: texts('ranked'), wide: document.documentElement.scrollWidth, table: card('table').querySelector('table').getBoundingClientRect().width,
                   card: card('table').getBoundingClientRect().width, inner: innerWidth, tableText: card('table').textContent };""", phone=True, more=True)
        boxes = build_studio.build([project], only="box")
        swipe = probed(boxes, "p-proj-1", VISIBLE + "return !!card('box').querySelector('.hint');", phone=True)
        self.assertIn("0%", got["ranked"])
        self.assertFalse(any("Best" in t for t in got["ranked"]), "Best is the Composite pick; one metric's chart never marks it")
        run = build_studio.build([with_intervals(run_snapshot())], only="forest")
        forest = probed(run, embedded(run)["datasets"][0]["id"], VISIBLE + "return texts('forest');", phone=True)
        # A phone shows each verdict as its mark beside the change; every version keeps one.
        self.assertTrue(any(t.endswith("▲") for t in forest) and any(t.endswith("≈") for t in forest), forest)
        self.assertFalse(swipe, "five box groups should fit a phone with no Swipe hint")
        self.assertEqual(got["inner"], 390)
        self.assertLessEqual(got["wide"], 390)
        self.assertLessEqual(got["table"], got["card"], "a long code name in a title pushed the table off the screen")
        self.assertIn("query_\u200bplanner.\u200boptimize", got["tableText"], "a code name should break at its _ and . first")

    def test_a_desktop_shows_the_verdict_wording_and_marks_the_chosen_session(self) -> None:
        project = project_snapshot(3)
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", VISIBLE + """
          var theme = document.documentElement.getAttribute('data-theme');
          var cap = [].filter.call(document.querySelectorAll('.ctl > span'), function (s) { return s.textContent === 'Theme'; })[0];
          if (cap) cap.click();
          var ctlTag = cap ? cap.parentNode.tagName : null;
          var bold = [].filter.call(card('sessions').querySelectorAll('svg text tspan'), function (t) { return /^Discovery session 2$/.test(t.textContent) && +getComputedStyle(t).fontWeight >= 600; }).length;
          return { themeAfter: document.documentElement.getAttribute('data-theme'), theme: theme, ctlTag: ctlTag, bold: bold,
                   best: card('best').textContent, table: card('table').textContent, sessions: card('sessions').textContent };""", session=1)
        self.assertEqual(got["themeAfter"], got["theme"], "a click on the Theme caption changed the theme")
        self.assertEqual(got["ctlTag"], "DIV", "a button group's caption must not be a <label>")
        self.assertGreater(got["bold"], 0, "the chosen session's label should be bold")
        self.assertRegex(got["table"], r"\d+ of \d+ significantly improved")
        self.assertRegex(got["sessions"], r"Discovery session 1's top( correct version)? on [^:]+: v\d")
        self.assertNotIn("'s best", got["sessions"], "a per-metric top is never called best")
        self.assertNotIn("Top by", got["sessions"])

    def test_the_forest_log_scale_reads_one_times_at_no_change(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())], only="forest")
        ds = embedded(html)["datasets"][0]["id"]
        got = probed(html, ds, VISIBLE + "return { ticks: texts('forest'), log: card('forest').querySelector('.seg button[aria-pressed=true]').textContent };",
                     act="[].filter.call(document.querySelectorAll('[data-card=\"forest\"] .seg button'), function (x) { return /^Log/.test(x.textContent); })[0].click();")
        self.assertEqual(got["log"], "Log (×)")
        self.assertIn("1×", got["ticks"], got)

    def test_a_label_shortened_once_takes_new_text_after_a_switch(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var swapped = window.__sw, kept = window.__kp;
          return { swapped: swapped.textContent, swappedFull: swapped.dataset.full || null, kept: kept.textContent.indexOf('Old metric with') === 0 };""", act="""
          var svg = document.querySelector('[data-card="ranked"] svg.recharts-surface'), ns = 'http://www.w3.org/2000/svg';
          var make = function (txt) { var t = document.createElementNS(ns, 'text'); t.setAttribute('x', 10); t.setAttribute('y', 20); t.textContent = txt; svg.appendChild(t); return t; };
          var swapped = make('New metric'); swapped.dataset.full = 'Old metric with a long name'; swapped.dataset.short = 'Old metric with…';
          var kept = make('Old metric with…'); kept.dataset.full = 'Old metric with a long name'; kept.dataset.short = 'Old metric with…';
          window.__sw = swapped; window.__kp = kept;
          window.dispatchEvent(new Event('resize'));""")
        self.assertEqual(got["swapped"], "New metric", "the pass wrote the old label over React's new one")
        self.assertIsNone(got["swappedFull"])
        self.assertTrue(got["kept"])

    def test_csv_keeps_every_run_under_each_runs_top(self) -> None:
        project = project_snapshot(6)
        per_run = len(project["runs"][0]["rankings"][project["runs"][0]["metrics"][0]["key"]])
        self.assertGreater(per_run, 1)
        html = build_studio.build([project])
        got = probed(html, "p-proj-1", "return { csv: window.__csv || null };", act="""
          window.claude = { use: function () { return Promise.resolve({ save: function (o) { window.__csv = o.data; return Promise.resolve(); } }); } };
          var c = document.querySelector('[data-card="sessions"]');
          var dl = [].filter.call(c.querySelectorAll('button'), function (b) { return b.textContent === 'Download'; })[0]; dl.click();
          setTimeout(function () { var o = [].filter.call(c.querySelectorAll('button'), function (b) { return /CSV/.test(b.textContent); })[0]; if (o) o.click(); }, 100);""")
        self.assertIsNotNone(got["csv"], "the sessions card saved no CSV")
        self.assertEqual(len(got["csv"].strip().splitlines()) - 1, 6 * per_run, "the CSV dropped the rows Show hides")


class LeadMetricAndTypeTests(unittest.TestCase):
    """The lead metric, no style editing, the Own layout, text of 15px or more, and Conclusion boxes."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_the_page_leads_with_the_most_important_metric(self) -> None:
        js = ("return { h1: document.querySelector('.headline').textContent, best: document.querySelector('[data-card=best] .means').textContent,"
              " panels: [].map.call(document.querySelectorAll('[data-card=best] .ptitle'), function (t) { return t.textContent; }),"
              " reset: [].map.call(document.querySelectorAll('button'), function (b) { return b.textContent; }).filter(function (t) { return /Reset/.test(t); }) };")
        # Without the collector's bestLines.metric (an older snapshot), the page ranks by importance itself.
        for told in (True, False):
            with self.subTest(bestLines_metric=told):
                snap = low_then_high()
                if not told:
                    snap["bestLines"].pop("metric")
                html = build_studio.build([snap])
                got = probed(html, embedded(html)["datasets"][0]["id"], js)
                self.assertIn("Latency", got["h1"], "the headline led on a low-importance metric that did not move")
                self.assertNotIn("db size", got["h1"].lower())
                self.assertIn("Latency", got["best"])
                self.assertTrue(got["panels"] and got["panels"][0].startswith("Latency"), f"the Best card should show the most important metric first: {got['panels']}")
                self.assertEqual(got["reset"], ["Reset"])

    def test_no_card_offers_style_editing_and_old_edits_do_not_come_back(self) -> None:
        html = build_studio.build([run_snapshot()])
        ds = embedded(html)["datasets"][0]["id"]
        got = probed(html, ds, """
          return { style: [].filter.call(document.querySelectorAll('button'), function (b) { return b.textContent === 'Style'; }).length,
                   editable: document.querySelectorAll('[contenteditable]').length,
                   colour: document.querySelectorAll('input[type=color]').length,
                   h2: document.querySelector('[data-card=\\\"ranked\\\"] h2').textContent };""",
                     act="")
        self.assertEqual((got["style"], got["editable"], got["colour"]), (0, 0, 0))
        # A browser that saved an edited title before still sees the question. The same saved card state hides every series, a
        # field the card still reads from its own key (versions picked now live in the run's shared list), to prove it was read.
        key = "dv-studio:v1:" + ds + ":" + embedded(html)["datasets"][0]["snapshot"]["run"]["id"] + ":ranked"
        every = {k: True for k in ("better", "noise", "worse", "dir-better", "dir-worse", "same")}
        seeded = html.replace("<!doctype html>\n", "<!doctype html>\n<script>try { localStorage.setItem('" + key + "', JSON.stringify({ title: 'My old title', labels: { x: 'old axis' }, hidden: " + json.dumps(every) + " })); } catch (e) {}</script>", 1)
        again = probed(seeded, ds, "var c = document.querySelector('[data-card=\\\"ranked\\\"]'); return { text: c.textContent, v1: [].some.call(c.querySelectorAll('svg text'), function (t) { return /^v1\\b/.test(t.textContent); }) };")
        self.assertIn("Every series is hidden.", again["text"], "the seeded state was not read, so this test checks nothing")
        self.assertFalse(again["v1"])
        self.assertNotIn("My old title", again["text"])
        self.assertNotIn("old axis", again["text"])

    def test_own_scale_puts_every_panel_in_one_row_on_desktop_and_two_columns_on_a_phone(self) -> None:
        html = build_studio.build([run_snapshot()], only="box")  # few iterations: the studio leaves box plots out, their own page draws them
        ds = embedded(html)["datasets"][0]["id"]
        act = "var c = document.querySelector('[data-card=\\\"box\\\"]'); [].filter.call(c.querySelectorAll('.seg button'), function (b) { return b.textContent === 'Own'; })[0].click();"
        read = "var ps = [].map.call(document.querySelectorAll('[data-card=\\\"box\\\"] .multi .panel'), function (p) { var r = p.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(p.querySelector('svg').getBoundingClientRect().width)]; }); return ps;"
        desk = probed(html, ds, read, act=act)
        self.assertGreater(len(desk), 2)
        self.assertEqual(len({p[1] for p in desk}), 1, f"panels wrapped onto more than one row: {desk}")
        self.assertTrue(all(abs(p[2] - p[3]) <= 2 for p in desk), f"a chart is narrower than its panel: {desk}")
        phone = probed(html, ds, read, act=act, phone=True)
        self.assertEqual(len({p[0] for p in phone}), 2, f"a phone should show two columns: {phone}")
        # Nine groups split into rows of 5 and 4 rather than a full row and one panel alone.
        many = run_snapshot()
        donor = next(v for v in many["versions"] if (v["metrics"].get("latency_ms") or {}).get("runs"))
        for n in range(6, 11):
            many["versions"].append(dict(copy.deepcopy(donor), version=n, label=f"v{n}", id=f"ver-{n}"))
        built = build_studio.build([many], only="box")
        rows = probed(built, embedded(built)["datasets"][0]["id"], read, act=act)
        per_row = [sum(1 for p in rows if p[1] == top) for top in sorted({p[1] for p in rows})]
        self.assertEqual(sum(per_row), 9, rows)
        self.assertEqual(sorted(per_row), [4, 5], f"rows should be as even as nine allows: {per_row}")

    def test_conclusions_are_called_conclusion_and_no_text_is_under_12px(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var small = []; var walk = document.createTreeWalker(document.getElementById('root'), NodeFilter.SHOW_TEXT);
          for (var n = walk.nextNode(); n; n = walk.nextNode()) { var el = n.parentElement; if (!n.data.trim() || !el || el.closest('[hidden]')) continue;
            var cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
            if (parseFloat(cs.fontSize) < 12) small.push(n.data.trim().slice(0, 30) + ' ' + cs.fontSize); }
          var heads = [].map.call(document.querySelectorAll('.means h3'), function (h) { return h.textContent; });
          var mono = [].filter.call(document.querySelectorAll('svg text, svg tspan, table.sum td.n'), function (t) { return /Mono|monospace/.test(getComputedStyle(t).fontFamily); }).length;
          return { small: small.slice(0, 5), heads: heads, mono: mono, old: document.getElementById('root').textContent.indexOf('What this means') };""")
        self.assertEqual(got["small"], [])
        self.assertTrue(got["heads"] and all(h == "Conclusion" for h in got["heads"]), got["heads"])
        self.assertEqual(got["old"], -1)
        self.assertEqual(got["mono"], 0, "numbers should be in the text face")

    def test_a_long_rotated_axis_title_stays_inside_its_chart(self) -> None:
        snap = run_snapshot()
        for m in snap["metrics"]:
            m["label"] = "host work between chunks reduction for " + m["key"]
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          return [].map.call(document.querySelectorAll('svg.recharts-surface'), function (svg) { var b = svg.getBoundingClientRect();
            return [].filter.call(svg.querySelectorAll('text[transform]'), function (t) { var r = t.getBoundingClientRect(); return r.height && (r.top < b.top - 1 || r.bottom > b.bottom + 1); }).map(function (t) { return t.textContent; }); })
            .reduce(function (a, b) { return a.concat(b); }, []);""", more=True)
        self.assertEqual(got, [], "a rotated axis title runs past its chart")

    def test_six_digit_ticks_clear_the_axis_title_on_a_phone(self) -> None:
        snap = run_snapshot()

        def scale(st: dict) -> None:
            for k in ("mean", "min", "max", "q1", "median", "q3"):
                if isinstance(st.get(k), (int, float)):
                    st[k] = st[k] * 12500
            if st.get("runs"):
                st["runs"] = [r * 12500 if isinstance(r, (int, float)) else r for r in st["runs"]]
        scale(snap["baseline"]["metrics"]["latency_ms"])
        for v in snap["versions"]:
            if v["metrics"].get("latency_ms"):
                scale(v["metrics"]["latency_ms"])
        html = build_studio.build([snap], only="box")
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var card = document.querySelector('[data-card="box"]'), title = card.querySelector('svg text[transform]');
          if (!title) return { title: false };
          var t = title.getBoundingClientRect();
          var ticks = [].filter.call(card.querySelectorAll('.recharts-cartesian-axis-tick-label'), function (x) { return getComputedStyle(x).visibility !== 'hidden'; });
          return { title: true, ticks: ticks.length, hit: ticks.filter(function (x) { var r = x.getBoundingClientRect(); return r.left < t.right && r.right > t.left && r.top < t.bottom && r.bottom > t.top; }).map(function (x) { return x.textContent; }) };""",
                     phone=True, more=True)
        self.assertTrue(got["title"])
        self.assertGreater(got["ticks"], 1)
        self.assertEqual(got["hit"], [], "a y tick overprints the axis title")


class SessionNamingAndOnlyTests(unittest.TestCase):
    """Discovery sessions are never called runs, --only draws one card, and the forest shades both sides."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_no_label_calls_a_discovery_session_a_run(self) -> None:
        project = project_snapshot(3)
        project["runs"][1]["run"]["taskDescription"] = "A different task entirely"
        html = build_studio.build([project])
        text = probed(html, "p-proj-1", "return document.getElementById('root').innerText;", session=1)
        self.assertIsNone(re.search(r"\bRuns?\b \d|\bRuns in\b|\brun \d", text), "a Discovery session is labelled as a run")
        self.assertIn("Discovery session 2", text)

    def test_only_draws_one_card_with_no_switchers(self) -> None:
        html = build_studio.build([run_snapshot()], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], "return { cards: [].map.call(document.querySelectorAll('section.card'), function (c) { return c.dataset.card; }), switches: [].map.call(document.querySelectorAll('.bar .ctl > span:first-child'), function (s) { return s.textContent; }), h1: document.querySelectorAll('h1').length };")
        self.assertEqual(got, {"cards": ["forest"], "switches": ["Theme"], "h1": 0})
        with self.assertRaisesRegex(ValueError, "--only must be one of"):
            build_studio.build([run_snapshot()], only="pie")

    def test_the_forest_shades_the_better_side_green_and_the_worse_side_red(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var svg = document.querySelector('[data-card="forest"] svg.recharts-surface'), zero = null;
          var areas = [].map.call(svg.querySelectorAll('.recharts-reference-area rect, .recharts-reference-area path'), function (r) { var b = r.getBoundingClientRect(); return { left: b.left, right: b.right, fill: r.getAttribute('fill') }; });
          var line = svg.querySelector('.recharts-reference-line line'); if (line) zero = line.getBoundingClientRect().left;
          var first = svg.querySelector('.recharts-reference-area'), marks = svg.querySelector('.recharts-scatter'), labels = [].filter.call(svg.querySelectorAll('text'), function (t) { return /less|more|improved|regressed|difference/.test(t.textContent); });
          var after = function (n) { return !!(first && n && (first.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)); };
          return { areas: areas, zero: zero, behind: after(marks) && labels.length > 0 && labels.every(after) };""")
        self.assertEqual(len(got["areas"]), 2, got)
        left, right = sorted(got["areas"], key=lambda a: a["left"])
        self.assertLessEqual(abs(left["right"] - got["zero"]), 1.5)
        self.assertLessEqual(abs(right["left"] - got["zero"]), 1.5)
        self.assertNotEqual(left["fill"], right["fill"])
        self.assertTrue(got["behind"], "the bands should sit behind the rows and their labels")


class ConclusionBulletTests(unittest.TestCase):
    """Fewer words: no reading notes or method block, no "(Best)" in titles, Conclusions as bullets."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_the_page_carries_no_reading_notes_and_conclusions_are_bullets(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var root = document.getElementById('root');
          return { text: root.innerText, titles: [].map.call(document.querySelectorAll('h1, .headline, section.card h2'), function (h) { return h.textContent; }),
                   boxes: [].map.call(document.querySelectorAll('.means'), function (m) { return m.querySelectorAll('li').length; }),
                   colours: [].map.call(document.querySelectorAll('.means li span[class^="v-"]'), function (x) { return x.className + '|' + getComputedStyle(x).color; }) };""")
        for gone in ("How to read this", "Verdicts, changes and 95% intervals", "Versions are numbered", "Not shown for this", "stay in this browser only"):
            self.assertNotIn(gone, got["text"])
        self.assertFalse([t for t in got["titles"] if "(Best)" in t], got["titles"])
        self.assertTrue(got["boxes"] and all(n >= 1 for n in got["boxes"]), f"every Conclusion should be bullets: {got['boxes']}")
        better = {c.split("|")[1] for c in got["colours"] if c.startswith("v-better")}
        noise = {c.split("|")[1] for c in got["colours"] if c.startswith("v-noise")}
        self.assertTrue(better and noise and not (better & noise), got["colours"])


class ValueAxisAndVerdictTests(unittest.TestCase):
    """Bar charts get a value axis from zero, every Conclusion looks the same, and every verdict is said."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_bars_have_a_value_axis_from_zero_and_every_conclusion_looks_the_same(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var best = document.querySelector('[data-card="best"]');
          var ticks = [].map.call(best.querySelectorAll('.recharts-yAxis .recharts-cartesian-axis-tick-value, .recharts-cartesian-axis-tick-label'), function (t) { return t.textContent; });
          var borders = [].map.call(document.querySelectorAll('.means'), function (m) { return getComputedStyle(m).borderTopColor + ' ' + getComputedStyle(m).borderTopStyle; });
          var top = document.querySelector('.lede-after .means li');  // the summary sits under chart 1, after the chart
          return { ticks: ticks, grid: best.querySelectorAll('.recharts-cartesian-grid-horizontal line').length, borders: borders, first: top ? top.textContent : '', chose: document.getElementById('root').innerText.indexOf('How Artemis chose Best') };""", more=True)
        self.assertIn("0", got["ticks"], got["ticks"])
        self.assertGreater(got["grid"], 0, "the Best card's bars need light gridlines")
        self.assertGreater(len(got["borders"]), 2)
        self.assertEqual(len(set(got["borders"])), 1, got["borders"])
        self.assertEqual(got["first"], "Best = highest Composite score across all metrics.")
        self.assertEqual(got["chose"], -1)

    def test_the_forest_shows_both_bands_when_one_change_is_huge(self) -> None:
        # This run's shape: a 99.9% gain next to a 500% regression.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        moved[0]["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=99.9, ciLowPct=99.8, ciHighPct=99.95, verdict="better")
        moved[-1]["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=-500.0, ciLowPct=-900.0, ciHighPct=-150.0, verdict="worse")
        html = build_studio.build([snap], only="forest")
        widths = probed(html, embedded(html)["datasets"][0]["id"], """
          var rects = [].map.call(document.querySelectorAll('[data-card="forest"] .recharts-reference-area rect, [data-card="forest"] .recharts-reference-area path'), function (r) { return r.getBoundingClientRect().width; });
          return rects;""")
        self.assertEqual(len(widths), 2, widths)
        # -900% is past the outlier rule's 5x, so that row is clipped at the edge; and "% better" can't pass +100% on a lower-is-better time, so the green band is small but there.
        self.assertGreaterEqual(min(widths) / sum(widths), 0.05, f"one band is gone: {widths}")

    def test_every_verdict_reaches_the_conclusion_when_the_composite_best_is_not_significant_and_the_rest_regressed(self) -> None:
        # A real run's shape: Best at 1.4% less with an interval across 0, every other version significantly regressed.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        self.assertGreaterEqual(len(moved), 2)
        for best in (snap["webUiBest"], snap["bestLines"]):
            best.update(version=moved[0]["version"], label=moved[0]["label"])
        changes = [(1.4, -2.0, 4.0, "noise")] + [(-70.0 - 50 * i, -90.0 - 50 * i, -50.0 - 50 * i, "worse") for i in range(len(moved) - 1)]
        for v, (pct, lo, hi, verdict) in zip(moved, changes):
            v["metrics"]["latency_ms"]["pctBetter"] = pct
            v["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=pct, ciLowPct=lo, ciHighPct=hi, verdict=verdict)
            for r in snap["rankings"].get("latency_ms", []):
                if r["version"] == v["version"]:
                    r["pctBetter"] = pct
        lines = """var lines = function (id) { var c = document.querySelector('[data-card="' + id + '"]'); return c ? [].map.call(c.querySelectorAll('.means li'), function (l) { return l.textContent; }) : null; };"""
        html, forest = build_studio.build([snap]), build_studio.build([snap], only="forest")
        got = {"table": probed(html, embedded(html)["datasets"][0]["id"], lines + "return lines('table');", more=True),
               "forest": probed(forest, embedded(forest)["datasets"][0]["id"], lines + "return lines('forest');")}
        worst = moved[-1]["label"]
        for card in ("forest", "table"):
            text = " | ".join(got[card] or [])
            self.assertNotIn("No interval clears", text)
            self.assertRegex(text, rf"{len(moved) - 1} of \d+ significantly regressed: {worst} ", card)
        self.assertRegex(" | ".join(got["forest"]), rf"1 of {len(moved)} no significant difference: {moved[0]['label']} 1.4% less")
        self.assertNotIn("Best", " | ".join(got["forest"] + got["table"]), "one metric's Conclusion never names the Composite Best")


class BuilderRefusalAndTooltipTests(unittest.TestCase):
    """--only refuses a chart the data lacks, the pp line is falcon's, and a box needs falcon's quartiles."""

    def test_only_refuses_a_chart_the_data_cannot_draw(self) -> None:
        snap = run_snapshot()
        bare = copy.deepcopy(snap)  # no AI Metric: no AI chart and no second metric for the trade-off
        bare["metrics"] = [m for m in bare["metrics"] if m["kind"] != "quality"]
        for v in bare["versions"]:
            v["metrics"].pop("quality_score", None)
        for card, why in (("sessions", "one run has no sessions chart"), ("ai", "no version has an AI Metric score"), ("pareto", "no two metrics")):
            with self.subTest(card=card), self.assertRaisesRegex(ValueError, f"--only {card}: {why}"):
                build_studio.build([bare], only=card)
        for card in ("ai", "pareto"):  # the full fixture has both
            build_studio.build([snap], only=card)
        build_studio.build([project_snapshot(2)], only="sessions")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps(snap), encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = build_studio.main(["--snapshot", str(path), "--only", "sessions", "--output", str(Path(tmp) / "out.html")])
            self.assertEqual(code, 2)
            self.assertFalse((Path(tmp) / "out.html").exists())
            self.assertIn("--only sessions:", err.getvalue())

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_builder_refuses_exactly_the_charts_the_page_leaves_out(self) -> None:
        # drawable() restates the page's pareto() and hasAIScores(); this holds the two together.
        full = run_snapshot()
        bare = copy.deepcopy(full)
        bare["metrics"] = [m for m in bare["metrics"] if m["kind"] != "quality"]
        for v in bare["versions"]:
            v["metrics"].pop("quality_score", None)
        flat = copy.deepcopy(full)
        for v in flat["versions"]:
            if v["metrics"].get("quality_score"):
                v["metrics"]["quality_score"]["mean"] = 0.5
        unscored = copy.deepcopy(full)
        for v in unscored["versions"]:
            if v["metrics"].get("quality_score"):
                v["metrics"]["quality_score"]["mean"] = None

        def with_axes(snap, keys):  # --pareto, built the way the collector builds it
            snap = copy.deepcopy(snap)
            defs = {m["key"]: m for m in snap["metrics"]}
            snap["pareto"] = {"axes": [{"key": k, "higherIsBetter": defs[k]["higherIsBetter"], "kind": defs[k]["kind"]} for k in keys],
                              "points": collect_discovery.pareto_front(snap["versions"], keys, defs)}
            return snap
        axes = with_axes(full, ["latency_ms", "compile_runtime"])
        same = copy.deepcopy(bare)
        for v in same["versions"]:
            if v["metrics"].get("compile_runtime"):
                v["metrics"]["compile_runtime"]["mean"] = 2.0
        flat_axes = with_axes(same, ["latency_ms", "compile_runtime"])
        no_front, no_points = copy.deepcopy(axes), copy.deepcopy(axes)
        no_front["pareto"]["points"] = []
        del no_points["pareto"]["points"]
        for name, snap in (("full", full), ("bare", bare), ("flat", flat), ("unscored", unscored), ("axes", axes), ("flat axes", flat_axes),
                           ("empty front", no_front), ("no points", no_points)):
            html = build_studio.build([snap])
            ds = embedded(html)["datasets"][0]
            drawn = probed(html, ds["id"], "return [].map.call(document.querySelectorAll('section.card'), function (c) { return c.dataset.card; });", more=True)
            for card in ("tradeoff", "pareto", "ai"):
                with self.subTest(snapshot=name, card=card):
                    expect = build_studio.drawable(card, ds) is None  # drawable("pareto") already refuses when the trade-off draws
                    self.assertEqual(card in drawn, expect, drawn)
                self.assertFalse("tradeoff" in drawn and "pareto" in drawn, f"one trade-off card at most: {drawn}")
            if name in ("empty front", "no points"):  # left out cleanly: no card, no error message anywhere
                self.assertNotIn("pareto", drawn)
                self.assertEqual(probed(html, ds["id"], "return document.querySelectorAll('.err').length;", more=True), 0, name)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_a_machine_group_draws_its_runs_not_a_box_without_falcons_quartiles(self) -> None:
        snap = run_snapshot()
        sides = [snap["baseline"]["metrics"]["latency_ms"]] + [v["metrics"]["latency_ms"] for v in snap["versions"] if v["metrics"].get("latency_ms")]
        for k, st in enumerate(sides):
            st["runs"] = [{"value": 5.0 + k + i * 0.5, "runner": "box-a" if i % 2 else "box-b"} for i in range(6)]
            st.update(min=5.0 + k, max=7.5 + k, q1=5.6 + k, median=6.2 + k, q3=6.9 + k)
        html = build_studio.build([snap], only="box")
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="box"]');
          return { rects: [].filter.call(c.querySelectorAll('svg rect'), function (r) { return /NaN/.test(r.outerHTML); }).length,
                   lines: [].filter.call(c.querySelectorAll('svg line'), function (l) { return /NaN/.test(l.outerHTML); }).length,
                   dots: c.querySelectorAll('svg circle').length,
                   means: (c.querySelector('.means') || {}).textContent || '',
                   machine: [].some.call(c.querySelectorAll('button'), function (b) { return b.getAttribute('aria-pressed') === 'true' && /Machine/.test(b.textContent); }) };""",
            act="[].forEach.call(document.querySelectorAll('[data-card=\"box\"] button'), function (b) { if (/^Machine$/.test(b.textContent.trim())) b.click(); });")
        self.assertTrue(got["machine"], "the Machine grouping did not switch on")
        self.assertEqual((got["rects"], got["lines"]), (0, 0), got)
        self.assertGreaterEqual(got["dots"], 12)
        self.assertIn("No box: Artemis gives quartiles per version only", got["means"], "a pooled group says why it has no box")


    @unittest.skipUnless(CHROME, "no Chrome")
    def test_a_version_without_falcons_quartiles_says_why_it_has_no_box(self) -> None:
        snap = run_snapshot()
        sides = [snap["baseline"]["metrics"]["latency_ms"]] + [v["metrics"]["latency_ms"] for v in snap["versions"] if v["metrics"].get("latency_ms")]
        for k, st in enumerate(sides):
            st["runs"] = [{"value": 5.0 + k + i * 0.5} for i in range(6)]
            st.update(min=5.0 + k, max=7.5 + k, q1=5.6 + k, median=6.2 + k, q3=6.9 + k)
        bare = next(v for v in snap["versions"] if v["metrics"].get("latency_ms"))
        for q in ("q1", "median", "q3"):
            bare["metrics"]["latency_ms"].pop(q)
        html = build_studio.build([snap], only="box")
        means = probed(html, embedded(html)["datasets"][0]["id"], "var m = document.querySelector('[data-card=\"box\"] .means'); return m ? m.textContent : '';")
        self.assertIn("No box for " + bare["label"] + ": Artemis sent no quartiles", means)
        snap["provenance"]["quartilesSent"] = False  # a CLI before 1.1.25: the fields never came, so the page says to update it
        html = build_studio.build([snap], only="box")
        means = probed(html, embedded(html)["datasets"][0]["id"], "var m = document.querySelector('[data-card=\"box\"] .means'); return m ? m.textContent : '';")
        self.assertIn("this CLI sends no quartiles; update it to 1.1.25 or later to see boxes", means)


class BestOnlyOverallTests(unittest.TestCase):
    @unittest.skipUnless(CHROME, "no Chrome")
    def test_best_is_marked_only_where_the_chart_is_about_the_overall_pick(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], VISIBLE + r"""
          // the trade-off and Pareto cards mark Best as a solid triangle, the box plots as a solid box and the All versions table with a
          // badge in its Version column, so none is in this per-metric list; the table's one badge is checked below
          var cards = ['ranked', 'forest', 'time', 'ai'].filter(card);
          var badges = [].map.call(card('table').querySelectorAll('.badge-best'), function (b) { return [b.textContent, b.closest('td').querySelector('button.vname').textContent]; });
          return { marked: cards.filter(function (id) { return /\bBest\b/.test(card(id).innerText); }),
                   best: /\bBest\b/.test(card('best').innerText), cards: cards, badges: badges };""", more=True)
        for drawn in ("ranked", "time"):
            self.assertIn(drawn, got["cards"], got)
        best = run_snapshot()["webUiBest"]["label"]
        self.assertEqual(got["badges"], [["Best", best]], "exactly one Best badge in the table, on Artemis's Best")
        self.assertEqual(got["marked"], [], "a per-metric chart marks the Composite Best")
        forest = build_studio.build([with_intervals(run_snapshot())], only="forest")
        self.assertNotRegex(probed(forest, embedded(forest)["datasets"][0]["id"], "return document.querySelector('[data-card=\"forest\"]').innerText;"), r"\bBest\b", "the forest marks the Composite Best")
        self.assertTrue(got["best"], "the Is-it-better card still names Best")
        from studio_fixtures import nemo_with_runs
        snap = nemo_with_runs()
        boxes = build_studio.build([snap], only="box")
        marks = probed(boxes, embedded(boxes)["datasets"][0]["id"], """var c = document.querySelector('[data-card="box"]');
          // The Best label is drawn inside its own box's group (data-group, the group's name), so read the group it sits in.
          return [].map.call(c.querySelectorAll('text.box-best'), function (t) { var g = t.closest('[data-group]'); return [t.textContent, g ? g.getAttribute('data-group') : null]; });""")
        self.assertEqual(marks, [["Best", snap["webUiBest"]["label"]]], "one Best label on the box card, over Artemis's Best and no other version")
        project = build_studio.build([project_snapshot(2)])
        sessions = probed(project, embedded(project)["datasets"][0]["id"], "return document.querySelector('[data-card=\"sessions\"]').innerText;")
        self.assertNotRegex(sessions, r"\bBest\b", "the sessions chart marks a Composite Best")


class OutlierAndAxisTests(unittest.TestCase):
    """The outlier rule, no impossible axis values, even ticks, phone labels clear of marks, plain words."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    @staticmethod
    def shop_shape() -> dict:
        # A real run's shape: three ~98-99.9% gains on a lower-is-better time, and v4 at 517.6% more, interval 11x the rest.
        snap = with_intervals(run_snapshot())
        moved = [v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline")]
        for v, (pct, lo, hi, verdict) in zip(moved, [(99.9, 99.8, 99.95, "better"), (98.3, 98.1, 98.6, "better"), (-517.6, -1100.0, -60.0, "worse")]):
            v["metrics"]["latency_ms"]["pctBetter"] = pct
            v["metrics"]["latency_ms"]["vsBaseline"].update(improvementPct=pct, ciLowPct=lo, ciHighPct=hi, verdict=verdict)
            for r in snap["rankings"]["latency_ms"]:
                if r["version"] == v["version"]:
                    r["pctBetter"] = pct
        sides = [snap["baseline"]["metrics"]["latency_ms"]] + [v["metrics"]["latency_ms"] for v in moved]
        for st, runs in zip(sides, ([9641.3, 9358.7, 9266.0, 9379.5, 9400.0], [9.0, 9.5, 10.0, 10.5, 11.0], [150.0, 160.0, 170.0, 165.0, 155.0], [57000.0, 70000.0, 81000.0, 90000.0, 99053.0])):
            st.update(runs=runs, min=min(runs), max=max(runs), mean=sum(runs) / len(runs), count=len(runs), q1=sorted(runs)[1], median=sorted(runs)[2], q3=sorted(runs)[3])
        return snap

    TICKS = r"""
      var axisText = function (id, axis) { return [].map.call(document.querySelectorAll('[data-card="' + id + '"] .recharts-' + axis + '-tick-labels text'), function (t) { return t.textContent.trim(); }).filter(function (t) { return /^[\u2212+-]?[\d,.]+%?$/.test(t); }); };
      var ticks = function (id) { return axisText(id, 'xAxis'); }, yticks = function (id) { return axisText(id, 'yAxis'); };
      var arrows = function (id) { return document.querySelectorAll('[data-card="' + id + '"] .clip-arrow').length; };
      var txt = function (id) { return document.querySelector('[data-card="' + id + '"]').innerText; };"""

    @staticmethod
    def pct(t: str) -> float:
        return float(t.replace("−", "-").replace("+", "").replace("%", ""))

    def test_a_far_outlier_is_clipped_at_the_edge_with_its_value_and_the_axis_fits_the_rest(self) -> None:
        html, fp = build_studio.build([self.shop_shape()]), build_studio.build([self.shop_shape()], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], self.TICKS + """
          return { ranked: ticks('ranked'), box: yticks('box'), arrows: [0, arrows('ranked'), arrows('box')],
                   boxText: txt('box'), h1: document.querySelector('.headline').textContent };""", more=True)
        f = probed(fp, embedded(fp)["datasets"][0]["id"], self.TICKS + "return { ticks: ticks('forest'), arrows: arrows('forest'), text: txt('forest') };")
        got.update(forest=f["ticks"], forestText=f["text"]); got["arrows"][0] = f["arrows"]
        forest = [self.pct(t) for t in got["forest"]]
        self.assertEqual(got["arrows"][0], 1, "the forest clips v4 at its edge")
        self.assertGreaterEqual(min(forest), -200, f"the forest axis fits the rest, not v4: {forest}")
        self.assertIn("517.6% more", got["forestText"], "a clipped row keeps its value")
        self.assertEqual(got["arrows"][1], 1, "the ranked bars clip v4's 517.6% too (5.2x the rest)")
        self.assertLess(min(self.pct(t) for t in got["ranked"]), 0, "a clipped regression keeps room on the worse side")
        self.assertLessEqual(-min(self.pct(t) for t in got["ranked"]), 100, got["ranked"])
        self.assertEqual(got["arrows"][2], 1, "the box card clips v4's 99,053 ms group")
        box = [float(t.replace(",", "")) for t in got["box"]]
        self.assertGreaterEqual(min(box), 0, f"ms can't go below 0: {box}")
        self.assertLess(max(box), 20000, f"the box axis fits the rest: {box}")
        self.assertIn("to 99,053", got["boxText"].replace("\\n", " "))

    def test_no_axis_shows_an_impossible_value_and_ticks_step_evenly(self) -> None:
        html, fp = build_studio.build([self.shop_shape()]), build_studio.build([self.shop_shape()], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], self.TICKS + """
          return { ranked: ticks('ranked') };""", more=True)
        got["forest"] = probed(fp, embedded(fp)["datasets"][0]["id"], self.TICKS + "return ticks('forest');")
        for card in ("forest", "ranked"):
            vals = [self.pct(t) for t in got[card]]
            with self.subTest(card=card):
                self.assertLessEqual(max(vals), 100, f"a lower-is-better time can't be more than 100% better: {vals}")
                steps = {round(b - a, 6) for a, b in zip(vals, vals[1:])}
                self.assertEqual(len(steps), 1, f"one step on both sides of 0: {vals}")

    def test_a_phone_forest_keeps_values_clear_of_the_marks(self) -> None:
        html = build_studio.build([self.shop_shape()], only="forest")
        hits = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="forest"] svg.recharts-surface'), box = function (e) { return e.getBoundingClientRect(); };
          var marks = [].slice.call(c.querySelectorAll('.recharts-scatter-symbol circle, .recharts-scatter-symbol polygon, .recharts-errorBar line'));
          var labels = [].filter.call(c.querySelectorAll('text'), function (t) { return /% (less|more)/.test(t.textContent); });
          var out = []; labels.forEach(function (t) { var a = box(t); marks.forEach(function (m) { var b = box(m); if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) out.push(t.textContent); }); });
          return { hits: out, labels: labels.length };""", phone=True)
        self.assertGreaterEqual(hits["labels"], 3, hits)
        self.assertEqual(hits["hits"], [], "a value covers a dot or an interval on a phone")

    def test_the_trend_draws_versions_as_dots_not_a_joined_line(self) -> None:
        html = build_studio.build([self.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var curve = document.querySelector('[data-card="time"] .recharts-line:not(.run-line) .recharts-line-curve');  // the dots' own line, not the leader-so-far steps
          return { stroke: curve ? curve.getAttribute('stroke') : 'none', dots: document.querySelectorAll('[data-card="time"] .recharts-line-dots circle, [data-card="time"] .recharts-line-dots > g circle').length };""", more=True)
        self.assertEqual(got["stroke"], "none", "independent versions are never joined into a trend line")
        self.assertGreater(got["dots"], 0, got)

    def test_conclusions_say_each_count_once_in_plain_words(self) -> None:
        lines = """var lines = function (id) { return [].map.call(document.querySelectorAll('[data-card="' + id + '"] .means li'), function (l) { return l.textContent; }); };"""
        html, fp = build_studio.build([self.shop_shape()]), build_studio.build([self.shop_shape()], only="forest")
        got = {"table": probed(html, embedded(html)["datasets"][0]["id"], lines + "return lines('table');", more=True),
               "forest": probed(fp, embedded(fp)["datasets"][0]["id"], lines + "return lines('forest');")}
        text = " | ".join(got["forest"] + got["table"])
        self.assertNotIn("Highest floor", text)
        self.assertIn("Surest gain: v1, at least 99.8% less, the low end of its 95% interval", text)
        self.assertEqual(sum("significantly improved" in l for l in got["table"]), 1, got["table"])

    def test_the_headline_names_both_when_the_overall_pick_is_not_the_best_on_the_lead_metric(self) -> None:
        snap = self.shop_shape()
        v2 = next(v for v in snap["versions"] if v["label"] == "v2")
        for best in (snap["webUiBest"], snap["bestLines"]):
            best.update(version=v2["version"], label="v2")
        snap["perMetricWinners"]["latency_ms"]["raw"].update(version=1, label="v1", pctBetter=99.9)
        html = build_studio.build([snap])
        h1 = probed(html, embedded(html)["datasets"][0]["id"], "return document.querySelector('.headline').textContent;")
        self.assertEqual(h1, "v2, Artemis's overall pick, takes 98.3% less time than the original on Latency (ms), significantly improved; v1 is fastest on Latency (ms) alone (99.9% less)")


class OneCardPageTests(unittest.TestCase):
    """A one-card page names the Best version, since it has no headline."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_a_one_card_page_names_the_best_version(self) -> None:
        snap = run_snapshot()
        html = build_studio.build([snap], only="forest")
        text = probed(html, embedded(html)["datasets"][0]["id"], "return document.getElementById('root').innerText;")
        self.assertIn(f"Best = highest Composite score across all metrics: {snap['bestLines']['label']}.", text)


class IterationWordingTests(unittest.TestCase):
    """A run is a script run and an iteration is one reading, as the Web UI says "Iterations 8"."""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_reading_counts_say_iterations_never_runs(self) -> None:
        snap = with_intervals(run_snapshot())
        html = build_studio.build([snap])
        text = probed(html, embedded(html)["datasets"][0]["id"], "return document.getElementById('root').innerText;", more=True).replace("\u00ad", "")
        self.assertRegex(text, r"from \d+ iterations")
        self.assertIn("Iterations", text)  # the table's column
        boxes = build_studio.build([snap], only="box")  # few iterations: the studio leaves box plots out, their own page draws them
        text += probed(boxes, embedded(boxes)["datasets"][0]["id"], "return document.getElementById('root').innerText;").replace("\u00ad", "")
        self.assertIn("How spread out are the iterations on", text)
        self.assertIsNone(re.search(r"\b\d+ runs\b|\b1 run\b|\bRuns\b", text), re.findall(r".{30}\b(?:\d+ runs|1 run|Runs)\b.{20}", text))


class AIScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def test_an_ai_score_equal_to_the_originals_reads_plain_not_like_a_verdict(self) -> None:
        # A judged score of 0.75 against the original's 0.75 is falcon's 0%; it must not look like the amber of a verdict.
        snap = run_snapshot()
        scored = [v for v in snap["versions"] if (v["metrics"].get("quality_score") or {}).get("mean") is not None]
        scored[0]["metrics"]["quality_score"]["pctBetter"] = 0.0
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          document.querySelectorAll('details').forEach(function (d) { d.open = true; });
          var c = document.querySelector('[data-card="ai"]'), noise = getComputedStyle(document.documentElement).getPropertyValue('--noise').trim();
          var fills = [].map.call(c.querySelectorAll('svg rect'), function (r) { return (r.getAttribute('fill') || '').trim(); });
          return { zero: [].some.call(c.querySelectorAll('svg text'), function (t) { return t.textContent === '0%'; }), amber: fills.filter(function (f) { return f === noise; }).length,
                   pills: c.querySelectorAll('svg rect[rx="11"]').length };""", act="document.querySelectorAll('details').forEach(function (d) { d.open = true; });", more=True)
        self.assertTrue(got["zero"], got)
        self.assertEqual((got["amber"], got["pills"]), (0, 0), "a same score is drawn plain, never in the amber of a verdict")


class VersionLinkTests(unittest.TestCase):
    """A ranked bar or a forest row selects its version; its tooltip's "Open in Artemis" opens the version's Code tab, built
    from the snapshot's own ids only. A click on a mark selects its version; the link lives in the tooltip."""

    BASE = "https://testing.artemis.turintech.ai/projects/proj-1/discover/run-1"
    # Focus each version's tabbable label in turn and read its tooltip 30ms later, once React has drawn VTip (timers, not
    # requestAnimationFrame, which headless Chrome's virtual time does not advance); the probe's
    # read step (wait ms after) returns what was collected. A synchronous focus-then-read would see no tooltip yet.
    ACT = r"""
      var out = window.__vt = { ranked: [], forest: [], focused: null, tipShown: null, done: false }, q = [];
      ['ranked', 'forest'].forEach(function (id) { [].forEach.call(document.querySelectorAll('[data-card="' + id + '"] .vmark[tabindex="0"]'), function (m) { q.push([id, m]); }); });
      (function step(i) {
        if (i >= q.length) { out.done = true; return; }
        var id = q[i][0], m = q[i][1]; m.focus();
        setTimeout(function () {
          var a = document.querySelector('[data-card="' + id + '"] .vtip a.vtip-link');
          if (a) out[id].push({ href: a.getAttribute('href'), target: a.getAttribute('target'), rel: a.getAttribute('rel'), text: a.textContent });
          if (i === 0) { out.focused = document.activeElement === m; out.tipShown = !!document.querySelector('[data-card="' + id + '"] .vtip'); }
          m.blur(); step(i + 1);
        }, 30);
      })(0);"""
    JS = r"""
      var stops = function (id) { return document.querySelectorAll('[data-card="' + id + '"] .vmark[tabindex="0"]').length; }, out = window.__vt || {};
      return { ranked: out.ranked || [], forest: out.forest || [], focused: out.focused, tipShown: out.tipShown, done: !!out.done, anchors: document.querySelectorAll('svg a').length,
               stops: [stops('ranked'), stops('forest')], rows: [document.querySelectorAll('[data-card="ranked"] .recharts-bar-rectangle').length, document.querySelectorAll('[data-card="forest"] .recharts-scatter-symbol').length] };"""

    @classmethod
    def setUpClass(cls) -> None:
        if not CHROME:
            raise unittest.SkipTest("no Chrome")

    def page(self, url, ids=True) -> dict:
        snap = with_intervals(run_snapshot())
        snap["run"].update(webOrigin="https://testing.artemis.turintech.ai", webUrl=url)
        for v in snap["versions"]:
            v["id"] = f"ver-{v['version']}" if ids else None
        html, fp = build_studio.build([snap]), build_studio.build([snap], only="forest")
        got = probed(html, embedded(html)["datasets"][0]["id"], self.JS, act=self.ACT, wait=4000)
        f = probed(fp, embedded(fp)["datasets"][0]["id"], self.JS, act=self.ACT, wait=4000)
        self.assertTrue(got["done"] and f["done"], "every version was focused and read before the probe returned")
        got.update(forest=f["forest"], stops=[got["stops"][0], f["stops"][1]], rows=[got["rows"][0], f["rows"][1]])
        return got

    def test_a_focused_bar_or_forest_row_offers_open_in_artemis_in_its_tooltip(self) -> None:
        got = self.page(self.BASE)
        self.assertTrue(got["ranked"] and got["forest"], got)
        for link in got["ranked"] + got["forest"]:
            self.assertRegex(link["href"], "^" + re.escape(self.BASE) + r"/versions/ver-\d+$")
            self.assertEqual((link["target"], link["rel"]), ("_blank", "noopener"))
            self.assertTrue(link["text"].startswith("Open in Artemis"), link)
        self.assertTrue(got["focused"] and got["tipShown"], "a version takes keyboard focus, and focus opens its tooltip")
        self.assertEqual(got["anchors"], 0, "no mark is a link: a click selects")
        self.assertEqual(got["stops"], got["rows"], "one Tab stop per version: its label, not its mark too")

    def test_no_link_without_the_run_url_or_the_version_id(self) -> None:
        for url, ids in ((None, True), (self.BASE, False), ("https://artemis.turintech.ai/projects/p/discover/r", True), ("http://testing.artemis.turintech.ai/projects/p/discover/r", True), ("https://testing.artemis.turintech.ai.evil.example/projects/p/discover/r", True), (self.BASE + "/versions", True)):
            with self.subTest(url=url, ids=ids):
                got = self.page(url, ids)
                self.assertEqual((got["ranked"], got["forest"]), ([], []))
                self.assertTrue(all(got["rows"]), f"a card drew no rows, so there was nothing to link: {got['rows']}")


class TidierStudioTests(unittest.TestCase):
    """A tidier studio: one change card, box plots only when they earn it, a tidy table, one trend chart, a PDF."""

    def test_the_page_offers_a_pdf_and_prints_without_its_controls(self) -> None:
        html = build_studio.build([run_snapshot()])
        self.assertIn("Download PDF", html)
        self.assertRegex(html, r"@media print \{[^}]*\{[^}]*--bg: #ffffff")
        self.assertIn(".bar, .tools, .toast", html)

    def test_the_trend_has_no_zoom_strip_and_steers_carry_no_text(self) -> None:
        html = build_studio.build([run_snapshot()])
        self.assertNotIn("RC.Brush", html)
        self.assertNotIn('value: "Steer"', html)

    def test_motion_is_short_first_view_only_and_off_for_reduced_motion_and_print(self) -> None:
        html = build_studio.build([run_snapshot()])
        css = html[:html.index("</style>")]
        self.assertIn("@media (prefers-reduced-motion: reduce) { .card.playing, .card.playing *, .morph { animation: none !important; } .card.pre { opacity: 1; } }", css)
        self.assertRegex(css, r"@media print \{[\s\S]*\*, \*::before, \*::after \{ animation: none !important; transition: none !important; \}")
        self.assertIn(".card.pre { opacity: 1 !important; }", css, "print shows a card that was never scrolled to")
        # Each animation's length plus its fixed delay, plus the 150ms stagger and 300ms spread a delay can add: about 700ms at most.
        for rule in re.findall(r"animation: dv\w+ (\d+)ms[^;]*; animation-delay: calc\(var\(--rd, 0ms\)(?: \+ (\d+)ms)?", css):
            self.assertLessEqual(int(rule[0]) + int(rule[1] or 0) + 150, 760, rule)
        self.assertIn("firstView(ref.current", html, "a card plays once, when it first scrolls into view")

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_bar_and_forest_are_one_card_with_a_toggle_and_one_metric(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        ds = embedded(html)["datasets"][0]["id"]
        before = probed(html, ds, "return { ranked: !!document.querySelector('[data-card=\"change\"] [data-card=\"ranked\"]'), forest: !!document.querySelector('[data-card=\"forest\"]') };")
        self.assertEqual(before, {"ranked": True, "forest": False})
        after = probed(html, ds, "return { ranked: !!document.querySelector('[data-card=\"ranked\"]'), forest: !!document.querySelector('[data-card=\"change\"] [data-card=\"forest\"]') };",
                       act="[].filter.call(document.querySelectorAll('[data-card=\"change\"] .seg button'), function (b) { return b.textContent === 'Forest'; })[0].click();")
        self.assertEqual(after, {"ranked": False, "forest": True})

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_a_run_measured_once_offers_no_forest(self) -> None:
        html = build_studio.build([run_snapshot()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """return { buttons: [].map.call(document.querySelectorAll('[data-card="change"] .seg button'), function (b) { return b.textContent; }),
          cards: window.STUDIO_CARDS };""")
        self.assertNotIn("Forest", got["buttons"])
        self.assertNotIn("forest", got["cards"])

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_box_plots_are_an_extra_only_when_two_versions_have_five_iterations(self) -> None:
        few = build_studio.build([run_snapshot()])
        cards = "return [].map.call(document.querySelectorAll('[data-card]'), function (c) { return c.getAttribute('data-card'); });"
        self.assertNotIn("box", probed(few, embedded(few)["datasets"][0]["id"], cards, more=True))
        many = build_studio.build([OutlierAndAxisTests.shop_shape()])
        ds = embedded(many)["datasets"][0]["id"]
        shown = "return [].filter.call(document.querySelectorAll('[data-card]'), function (c) { return c.offsetParent !== null; }).map(function (c) { return c.getAttribute('data-card'); });"
        self.assertIn("box", probed(many, ds, cards, more=False), "box plots get a rail item")
        self.assertNotIn("box", probed(many, ds, shown, more=False), "hidden until picked: the page opens on Best against the original")
        self.assertIn("box", probed(many, ds, shown, more=True), "the checker sees every view")

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_table_shows_verdict_signs_with_a_key_and_the_interval_beside_the_change(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="table"]');
          return { heads: [].map.call(c.querySelectorAll('th'), function (t) { return t.textContent; }), signs: [].map.call(c.querySelectorAll('td .vicon'), function (i) { return i.getAttribute('aria-label'); }),
                   key: c.querySelector('.ikey').textContent, ci: c.querySelectorAll('td.n .ci').length };""")
        self.assertIn("Δ% vs original", got["heads"])
        self.assertFalse(any("95% interval" in h for h in got["heads"]), got["heads"])
        self.assertTrue(got["signs"] and all(got["signs"]), "every sign carries its verdict in words for a screen reader")
        for word in ("Significantly improved", "Needs more runs", "No significant difference", "Significantly regressed"):
            self.assertIn(word, got["key"])
        self.assertGreater(got["ci"], 0)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_trend_fits_every_version_points_at_best_and_says_which_way_is_good(self) -> None:
        html = build_studio.build([OutlierAndAxisTests.shop_shape()])
        got = probed(html, embedded(html)["datasets"][0]["id"], VISIBLE + """
          var t = texts('time');
          return { best: t.filter(function (x) { return /^Top v\d+: /.test(x); }), up: t.some(function (x) { return /^[↑↓] (higher|lower) is better$/.test(x); }), steer: t.indexOf('Steer') >= 0,
                   legend: card('time').querySelector('.legend') ? card('time').querySelector('.legend').textContent : '' };""", more=True)
        self.assertEqual(len(got["best"]), 1, got)
        self.assertTrue(got["up"], "the mean chart says which way is better in the metric's own way")
        self.assertFalse(got["steer"], "steers are dotted lines in the legend, not text on the chart")
        self.assertIn("Top on", got["legend"])

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_each_best_panel_gives_its_change_and_no_interval(self) -> None:
        # Chart 1 is the simplest: the change and better or worse; the interval is on the cards below.
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], "return { ci: document.querySelectorAll('[data-card=\"best\"] .psub .ci').length, sub: [].map.call(document.querySelectorAll('[data-card=\"best\"] .psub'), function (c) { return c.textContent; }) };")
        self.assertEqual(got["ci"], 0)
        self.assertTrue(got["sub"] and all(re.search(r"\b(better|worse)\b|unchanged|no %", t) for t in got["sub"]), got["sub"])


def two_targets(close: bool = False) -> dict:
    """compile_runtime as a second measured target: v2 (40, -10) and v4 (30, 0) lead; v4 edges v1 (20, -5),
    clear of it on latency unless close, when the intervals overlap."""
    snap = run_snapshot()
    next(m for m in snap["metrics"] if m["key"] == "compile_runtime")["kind"] = "target"
    for v in snap["versions"]:
        for key in ("latency_ms", "compile_runtime"):
            vb = ((v["metrics"].get(key) or {}).get("vsBaseline"))
            if vb and vb.get("improvementPct") is not None:
                half = 12 if close else 3
                vb.update(ciLowPct=vb["improvementPct"] - half, ciHighPct=vb["improvementPct"] + half, verdict="noise" if close else "better" if vb["improvementPct"] > 3 else "worse" if vb["improvementPct"] < -3 else "noise")
    return redrawable(snap)  # compile_runtime became a target after collecting


@unittest.skipUnless(CHROME, "no Chrome")
class VersionChartAnswerTests(unittest.TestCase):
    """The version-by-version chart says its answer in the title and shows the leader's interval."""

    def test_versions_with_no_reading_yet_are_not_counted_as_tried(self) -> None:
        # A running Discovery: v3 and v5 have no latency yet, so after v2 only v4 was tried.
        html = build_studio.build([run_snapshot()])
        h2 = probed(html, embedded(html)["datasets"][0]["id"], "return document.querySelector('[data-card=\"time\"] h2').textContent;")
        self.assertIn("the last at v2", h2)
        self.assertIn("in the measured version since", h2)
        self.assertNotIn("3 versions", h2)

    def test_the_title_counts_new_leaders_with_no_claim_with_or_without_intervals(self) -> None:
        bare = run_snapshot()
        for v in bare["versions"]:
            for st in v["metrics"].values():
                if isinstance(st, dict) and st.get("vsBaseline"):
                    st["vsBaseline"].update(ciLowPct=None, ciHighPct=None)
        for name, snap in (("intervals", with_intervals(run_snapshot())), ("none", bare)):
            html = build_studio.build([snap])
            got = probed(html, embedded(html)["datasets"][0]["id"], """var c = document.querySelector('[data-card="time"]');
              return { h2: c.querySelector('h2').textContent, band: c.querySelectorAll('.lead-band path').length, legend: c.querySelector('.legend').textContent };""")
            with self.subTest(intervals=name):
                self.assertRegex(got["h2"], r"^(\d+ new leaders?, the last at v\d+|No new leader after v\d+)")
                self.assertNotRegex(got["h2"] + got["legend"], r"clear|noise", "no new leader is called clear of, or within noise of, another")
                self.assertEqual(got["band"], 0, "the mean chart draws no % interval band")
                self.assertNotIn("95% interval", got["legend"])


class FailedRowsAndTradeOffTests(unittest.TestCase):
    PCT = "[].filter.call(document.querySelectorAll('[data-card=tradeoff] .seg button'), function (b) { return b.textContent === '% change'; })[0].click();"  # the % change view, one click from Values
    """The table hides failed versions behind a counted toggle; the trade-off card reads Artemis's changes on two metrics."""

    def test_the_builder_draws_a_trade_off_only_with_two_compared_metrics(self) -> None:
        one = build_studio.build([run_snapshot()])
        self.assertIsNotNone(build_studio.drawable("tradeoff", embedded(one)["datasets"][0]))
        two = build_studio.build([two_targets()])
        self.assertIsNone(build_studio.drawable("tradeoff", embedded(two)["datasets"][0]))
        with self.assertRaises(ValueError):
            build_studio.build([run_snapshot()], only="tradeoff")

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_trade_off_keeps_no_notes_and_unticks_versions_it_cannot_place(self) -> None:
        html = build_studio.build([two_targets()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="tradeoff"]');
          return { notes: c.querySelectorAll('.missing').length, info: (c.querySelector('.info') || {}).title || '', labels: [].map.call(c.querySelectorAll('.ctl > span'), function (x) { return x.textContent; }),
                   off: [].filter.call(c.querySelectorAll('.pop label'), function (l) { return l.querySelector('input').disabled; }).map(function (l) { return [l.textContent, l.title]; }) };""",
                     act=self.PCT + " setTimeout(function () { [].filter.call(document.querySelectorAll('[data-card=\"tradeoff\"] .tools button'), function (x) { return x.textContent === 'Versions'; })[0].click(); }, 300);")
        self.assertEqual(got["notes"], 0, "no list of left-out versions under the chart")
        self.assertIn("no Artemis change on both metrics", got["info"])
        self.assertTrue({"X axis", "Y axis"} <= set(got["labels"]), got["labels"])
        self.assertEqual(sorted(x[0] for x in got["off"]), ["v3", "v5"], got)
        self.assertTrue(all(x[1].startswith("No Artemis change on ") for x in got["off"]), got)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_box_columns_alternate_faint_bands_and_the_trade_off_has_none(self) -> None:
        boxes = build_studio.build([run_snapshot()], only="box")
        got = probed(boxes, embedded(boxes)["datasets"][0]["id"], """
          var c = document.querySelector('[data-card="box"]'), groups = c.querySelectorAll('.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick').length;
          return { groups: groups, bands: c.querySelectorAll('.col-band').length, fills: [].map.call(c.querySelectorAll('.col-band path, .col-band rect'), function (r) { return r.getAttribute('fill'); }), subtle: getComputedStyle(document.documentElement).getPropertyValue('--subtle').trim() };""")
        self.assertGreaterEqual(got["bands"], 1, got)  # every other column of the original and the versions
        self.assertTrue(got["fills"] and all(f == got["subtle"] for f in got["fills"]), got)  # the theme's subtle surface
        two = build_studio.build([two_targets()])
        self.assertEqual(probed(two, embedded(two)["datasets"][0]["id"], "return document.querySelectorAll('[data-card=\"tradeoff\"] .col-band').length;"), 0)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_failed_versions_are_hidden_counted_and_shown_as_a_cross(self) -> None:
        html = build_studio.build([run_snapshot()])
        ds = embedded(html)["datasets"][0]["id"]
        read = """var c = document.querySelector('[data-card="table"]'), b = [].filter.call(c.querySelectorAll('.tools button'), function (x) { return /failed versions/.test(x.textContent); })[0];
          return { rows: [].map.call(c.querySelectorAll('tbody tr td:first-child button.vname'), function (n) { return n.textContent.replace(/^✕ /, '').trim(); }), button: b ? b.textContent : null,
                   cross: [].map.call(c.querySelectorAll('td .vicon'), function (i) { return i.getAttribute('aria-label'); }).filter(function (l) { return /^Failed/.test(l); }), key: c.querySelector('.ikey').textContent };"""
        before = probed(html, ds, read)
        self.assertFalse({"v3", "v5"} & set(before["rows"]), before["rows"])  # v3 failed to generate, v5 to run
        self.assertEqual(before["button"], "Show failed versions (2)")
        self.assertIn("Failed to run (2, hidden)", before["key"])
        after = probed(html, ds, read, act="[].filter.call(document.querySelectorAll('[data-card=\"table\"] .tools button'), function (x) { return /failed versions/.test(x.textContent); })[0].click();")
        self.assertTrue({"v3", "v5"} <= set(after["rows"]), after["rows"])
        self.assertEqual(sorted(after["cross"]), ["Failed: execution failed", "Failed: generation failed"])

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_trade_off_joins_the_stored_front_and_fades_the_rest(self) -> None:
        read = """var c = document.querySelector('[data-card="tradeoff"]'); if (!c) return null;
          return { means: [].map.call(c.querySelectorAll('.means li'), function (l) { return l.textContent; }).join(' | '),
                   faded: [].filter.call(c.querySelectorAll('g[opacity]'), function (g) { return g.getAttribute('opacity') === '0.75'; }).length, h2: c.querySelector('h2').textContent,
                   labels: [].map.call(c.querySelectorAll('svg text'), function (t) { return t.textContent; }) };"""
        sure = build_studio.build([two_targets()])
        got = probed(sure, embedded(sure)["datasets"][0]["id"], read, act=self.PCT)
        self.assertIn("On the Pareto front: v2, v4", got["means"])  # in order across, left to right: lower latency sits left
        self.assertIn("Pareto front", got["h2"])
        self.assertEqual(got["faded"], 1, "v1 is behind the collector's front: v4 is at least as good on both means")
        self.assertTrue({"v2 · Best", "v4"} <= set(got["labels"]), "every front version is labelled, Best as 'v2 · Best'")
        self.assertIn("Original", got["labels"])
        near = build_studio.build([two_targets(close=True)])
        got = probed(near, embedded(near)["datasets"][0]["id"], read, act=self.PCT)
        self.assertIn("On the Pareto front: v2, v4", got["means"], "overlapping intervals change nothing: the front makes no significance claim")
        self.assertNotIn("within noise", got["means"])
        self.assertEqual(got["faded"], 1)
        one = build_studio.build([run_snapshot()])
        self.assertIsNone(probed(one, embedded(one)["datasets"][0]["id"], read), "one measured metric: no trade-off card")


    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_trade_off_draws_the_original_as_a_triangle_and_a_legend_true_to_the_chart(self) -> None:
        html = build_studio.build([two_targets()])
        got = probed(html, embedded(html)["datasets"][0]["id"], """var c = document.querySelector('[data-card="tradeoff"]');
          var pressed = [].filter.call(c.querySelectorAll('.seg button'), function (b) { return b.getAttribute('aria-pressed') === 'true'; }).map(function (b) { return b.textContent; });
          var legend = [].map.call(c.querySelectorAll('.legend button'), function (b) { var m = b.querySelector('svg'); return [b.textContent, m ? [].map.call(m.children, function (x) { return x.tagName; }).join('+') : '']; });
          return { pressed: pressed, legend: legend, orig: c.querySelectorAll('.orig polygon').length, both: [].map.call(c.querySelectorAll('text.both'), function (t) { return t.textContent; }) };""", act=self.PCT)
        self.assertFalse({"All", "Front"} & set(got["pressed"]), "no zoom control")
        self.assertEqual(got["orig"], 1, "the original is drawn as a triangle")
        hib = {m["key"]: m["higherIsBetter"] for m in two_targets()["metrics"]}
        arrow = {(True, True): "↗", (False, True): "↖", (True, False): "↘", (False, False): "↙"}[(hib["latency_ms"], hib["compile_runtime"])]
        self.assertEqual(got["both"], ["Better on both " + arrow], "the corner each metric's direction gives, as in Values")
        marks = dict(got["legend"])
        self.assertEqual(marks.get("Original (no change on either)"), "polygon", "the legend's original is the same triangle")
        self.assertEqual(marks.get("On the Pareto front (joined by the front line)"), "line+polygon")
        self.assertFalse(any("chance" in k.lower() for k in marks), marks)

    @staticmethod
    def budgeted() -> dict:
        """latency_ms against a model size the collector marked as the budget (a stated 120 MB cap), with a sourced same-size rival."""
        snap = run_snapshot()
        snap["metrics"].append({"key": "model_size_mb", "label": "model size mb", "kind": "target", "higherIsBetter": False, "importance": "none",
                                "unit": "MB", "role": "budget", "cap": 120.0})
        snap["baseline"]["metrics"]["model_size_mb"] = {"mean": 100.0, "count": 1}
        for i, v in enumerate(snap["versions"]):
            if v["metrics"].get("latency_ms"):
                size = 104.0 + 4 * i
                v["metrics"]["model_size_mb"] = {"mean": size, "count": 1, "pctBetter": 100 - size, "vsBaseline": {"improvementPct": 100 - size, "verdict": "pending", "readings": 1}}
        snap["externalReferences"] = [{"label": "stock rival", "metrics": {"latency_ms": 7.0, "model_size_mb": 120.0}, "gateFailed": True,
                                       "failures": ["nonspeech: too many runaway clips"], "source": {"file": "rival.json", "sha256": "0" * 64, "note": None}}]
        return redrawable(snap)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_every_pair_opens_on_its_values_and_a_budget_pair_offers_the_cap_view(self) -> None:
        html = build_studio.build([self.budgeted()], tradeoff="model_size_mb,latency_ms")
        ds = embedded(html)["datasets"][0]["id"]
        read = """var c = document.querySelector('[data-card="tradeoff"]'); return { h2: c.querySelector('h2').textContent,
          pressed: [].filter.call(c.querySelectorAll('.seg button'), function (b) { return b.getAttribute('aria-pressed') === 'true'; }).map(function (b) { return b.textContent; }),
          views: [].map.call(c.querySelectorAll('.seg button'), function (b) { return b.textContent; }), text: c.textContent,
          orig: [].map.call(c.querySelectorAll('.orig text'), function (t) { return t.textContent; }),
          menus: [].map.call(c.querySelectorAll('select'), function (m) { return [].map.call(m.options, function (o) { return o.value; }); }),
          labels: [].map.call(c.querySelectorAll('svg text'), function (t) { return t.dataset.full || t.textContent; }) };"""  # a shortened label keeps its full text
        got = probed(html, ds, read)
        self.assertIn("in their own values", got["h2"])
        self.assertEqual(got["pressed"], ["Values"])
        self.assertEqual(got["views"], ["Values", "Within the cap", "% change"])
        self.assertEqual(got["menus"][0].count("latency_ms") + got["menus"][1].count("model_size_mb"), 0, "neither menu offers the other axis's metric")
        self.assertIn("Better on both ↙", got["labels"], "two lower-is-better metrics: down and left")
        self.assertEqual(got["orig"], ["Original"], "the original sits at its real values, as a triangle")
        self.assertTrue(any(l.startswith("Size cap, 120") for l in got["labels"]), "the cap line on the budget axis")
        cap = probed(html, ds, read, act="[].filter.call(document.querySelectorAll('[data-card=tradeoff] .seg button'), function (b) { return b.textContent === 'Within the cap'; })[0].click();")
        self.assertIn("within the size cap", cap["h2"])
        self.assertTrue(any(l.startswith("Same size: stock rival") and "fails the gate (nonspeech)" in l for l in cap["labels"]), cap["labels"])
        self.assertTrue(any(l.endswith("%") and "MB" in l for l in cap["labels"]), "each row shows its size and share of the cap")
        plain = build_studio.build([two_targets()])
        got = probed(plain, embedded(plain)["datasets"][0]["id"], read)
        self.assertEqual(got["views"], ["Values", "% change"], "no budget metric: Values first, no within-the-cap view, whatever the names")

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_percent_view_plots_each_metric_its_own_way_round(self) -> None:
        # Every version is a larger model than the original (size: lower is better). On % change it plots above the original, and
        # the green wash and "Better on both" sit down and left, where the two lower-is-better directions point; each axis says so.
        html = build_studio.build([self.budgeted()], tradeoff="latency_ms,model_size_mb")
        got = probed(html, embedded(html)["datasets"][0]["id"], """var c = document.querySelector('[data-card="tradeoff"]'), box = function (e) { var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
          var o = box(c.querySelector('.orig polygon')), good = c.querySelector('.corner-wash radialGradient[id$="-good"]'), bad = c.querySelector('.corner-wash radialGradient[id$="-bad"]');
          var at = function (g) { return g ? [g.getAttribute('cx'), g.getAttribute('cy')] : null; };
          return { o: [(o[0] + o[2]) / 2, (o[1] + o[3]) / 2], good: at(good), bad: at(bad), both: [].map.call(c.querySelectorAll('text.both'), function (t) { return t.textContent; }),
                   labels: [].map.call(c.querySelectorAll('.recharts-label'), function (t) { return t.textContent; }),
                   marks: [].map.call(c.querySelectorAll('.tp:not(.gate) polygon'), function (p) { var b = box(p); return (b[1] + b[3]) / 2; }) };""",
                     act="[].filter.call(document.querySelectorAll('[data-card=\"tradeoff\"] .seg button'), function (b) { return b.textContent === '% change'; })[0].click();")
        self.assertEqual(got["both"], ["Better on both ↙"])
        self.assertTrue(any(l.endswith("% change, lower is better") for l in got["labels"]), got["labels"])
        self.assertTrue(any(l.endswith("% change, ← lower is better") for l in got["labels"]), got["labels"])
        _, oy = got["o"]
        self.assertEqual(got["good"], ["0", "1"], "the green wash fades out from the lower left: lower latency and a smaller model are better")
        self.assertEqual(got["bad"], ["1", "0"], "the red wash fades out from the upper right, worse on both")
        self.assertTrue(got["marks"] and all(y < oy for y in got["marks"]), f"every larger model plots above the original: {got['marks']} vs {oy}")

    @staticmethod
    def in_bytes() -> dict:
        """The budget pair with the model size in bytes: ticks like 1,200,000,000 and a cap line across the plot."""
        snap = FailedRowsAndTradeOffTests.budgeted()
        k = 10_000_000
        m = next(m for m in snap["metrics"] if m["key"] == "model_size_mb")
        m.update(cap=m["cap"] * k, unit="bytes")
        snap["baseline"]["metrics"]["model_size_mb"]["mean"] *= k
        for v in snap["versions"]:
            st = v["metrics"].get("model_size_mb")
            if st:
                st["mean"] *= k
        snap["externalReferences"][0]["metrics"]["model_size_mb"] *= k
        return snap

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_values_view_keeps_long_ticks_and_the_cap_label_clear(self) -> None:
        html = build_studio.build([self.in_bytes()], tradeoff="latency_ms,model_size_mb")
        found = [p for p in check_report.studio_render_checks(html, CHROME) if p.startswith(("LABELS OVERLAP", "LABEL HIDDEN", "LABEL CUT OFF")) and " in Trade-off" in p]
        self.assertEqual(found, [])

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_checker_catches_a_corner_or_axis_title_against_the_metrics_direction(self) -> None:
        html = build_studio.build([self.budgeted()], tradeoff="latency_ms,model_size_mb")
        direction = lambda ps: [p for p in ps if p.startswith(("WRONG BETTER CORNER", "WRONG AXIS DIRECTION"))]
        self.assertEqual(direction(check_report.studio_render_checks(html, CHROME)), [])
        # A long metric name: the layout pass shortens the axis title with an ellipsis, and the checker reads its whole text.
        snap = self.budgeted()
        next(m for m in snap["metrics"] if m["key"] == "model_size_mb")["label"] = "nonspeech words per minute of the parent model size"
        self.assertEqual(direction(check_report.studio_render_checks(build_studio.build([snap], tradeoff="latency_ms,model_size_mb"), CHROME)), [])
        # A bug this guards: a fixed up-and-right corner and "% better" axis titles on two lower-is-better metrics.
        corner, title = 'bothText = "Better on both " + pc.arrow', '"% change, " + (sy > 0 ? "higher is better" : "lower is better")'
        self.assertEqual((html.count(corner), html.count(title)), (1, 1))
        found = direction(check_report.studio_render_checks(html.replace(corner, 'bothText = "Better on both \u2197"').replace(title, '"% better \u2192"'), CHROME))
        self.assertTrue(any(p.startswith('WRONG BETTER CORNER: "Better on both \u2197"') for p in found), found)
        self.assertTrue(any(p.startswith("WRONG AXIS DIRECTION:") and "model size" in p.lower() for p in found), found)

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_the_checker_catches_an_empty_conclusion_bullet(self) -> None:
        html = build_studio.build([run_snapshot()]) + late("var ul = document.querySelector('[data-card=time] .means ul'); var li = document.createElement('li'); ul.appendChild(li);")
        self.assertTrue(any(p.startswith("EMPTY BULLET:") for p in check_report.studio_render_checks(html, CHROME)))

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_tooltips_rank_versions_and_the_trade_off_crosses_out_gate_failures_and_names_best(self) -> None:
        snap = two_targets()  # v2 is a refuted experiment: it ran and is valid, so it is never crossed
        snap["metrics"].append({"key": "gate_ok", "label": "gate ok", "kind": "target", "higherIsBetter": True, "importance": "none", "unit": None})
        for v in snap["versions"]:  # as collect_discovery.py --gate-metric gate_ok writes it: v1 read 0, so it is out of every pick
            v["metrics"]["gate_ok"] = {"mean": 0 if v["label"] == "v1" else 1, "count": 1, "runs": [0 if v["label"] == "v1" else 1]}
            v["gateFailed"] = v["label"] == "v1"
        snap["gate"] = {"metric": "gate_ok", "failed": ["v1"]}
        snap["rankings"] = {k: [r for r in rows if r["label"] != "v1"] for k, rows in (snap.get("rankings") or {}).items()}
        redrawable(snap)
        html = build_studio.build([snap], tradeoff="compile_runtime,latency_ms")
        ds = embedded(html)["datasets"][0]["id"]
        hover = lambda sel: "var d = " + sel + "; ['mouseover', 'mousemove'].forEach(function (t) { d.dispatchEvent(new MouseEvent(t, { bubbles: true })); });"
        # A version's mark (.vmark) opens the card's own tooltip (.vtip); Recharts' steps aside for it.
        tip = lambda card: "var w = document.querySelector('[data-card=\"" + card + "\"] .vtip'); return w ? w.innerText : '';"
        # The tooltips as a reader sees them: a forest point (for the rank every version tooltip carries) and the gate failure's cross
        # once its legend entry shows it. A bar's tooltip follows the pointer's position, which headless Chrome does not synthesise.
        # Every version tooltip carries its rank. Read it where hovering works headless: a forest point (bars take the pointer's position).
        forest = build_studio.build([snap], only="forest")
        rank_tip = probed(forest, embedded(forest)["datasets"][0]["id"], tip("forest"), act=hover("document.querySelector('[data-card=\"forest\"] .recharts-scatter-symbol .vmark')"))
        show_gate = "[].filter.call(document.querySelectorAll('[data-card=\"tradeoff\"] .legend button'), function (b) { return /Failed the gate/.test(b.textContent); })[0].click();"
        gate_tip = probed(html, ds, tip("tradeoff"), act=show_gate + " setTimeout(function () { " + hover("document.querySelector('[data-card=\"tradeoff\"] .gate .vmark')") + " }, 300);")
        got = probed(html, ds, """var c = document.querySelector('[data-card="tradeoff"]'), ch = document.querySelector('[data-card="change"]'), tb = document.querySelector('[data-card="table"]');
          return { x: c.querySelector('select').value, gate: c.querySelectorAll('.gate').length, legend: c.querySelector('.legend').textContent,
                   change: ch.textContent, table: tb.textContent,
                   labels: [].map.call(c.querySelectorAll('svg text'), function (t) { return t.textContent; }), means: c.querySelector('.means').textContent };""")
        got.update(tip=rank_tip, gateTip=gate_tip)
        self.assertRegex(got["tip"], r"Rank \d+ of \d+ on ")
        self.assertEqual(got["x"], "compile_runtime", "--tradeoff sets the axis the card opens on")
        self.assertEqual(got["gate"], 0, "a gate failure starts hidden; its legend entry, struck through, brings it back")
        self.assertIn("Failed the gate", got["legend"])
        shown = probed(html, embedded(html)["datasets"][0]["id"], "return document.querySelectorAll('[data-card=\"tradeoff\"] .gate').length;",
                       act="[].filter.call(document.querySelectorAll('[data-card=\"tradeoff\"] .legend button'), function (b) { return /Failed the gate/.test(b.textContent); })[0].click();")
        self.assertEqual(shown, 1, "only v1, which read 0 on the gate metric, is a cross; the refuted v2 is not")
        self.assertIn("failed the gate: v1", got["means"])
        self.assertRegex(got["gateTip"], r"Failed the gate \(.+ = 0\): values not usable")
        self.assertNotIn("Rank ", got["gateTip"], "a gate failure is never ranked")
        self.assertRegex(got["change"], r"Failed the gate \(.+ = 0\): v1\. Their values are not usable")
        self.assertIn("failed the gate, values not usable", got["table"])
        best = embedded(html)["datasets"][0]["snapshot"].get("bestLines") or {}
        if best.get("label"):
            self.assertIn(best["label"] + " · Best", got["labels"])

NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node not installed")
class SelectionAndCornerTests(unittest.TestCase):
    """One version selection shared by every card of a run, the trade-off's controls on one aligned
    row, and "Better on both" kept off every mark, the Original and reference points included. Node and static, no render."""

    PAGE = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")

    @classmethod
    def fns(cls, *names: str) -> str:
        return "\n".join(BuildTests.studio_function(n) for n in names) + "\n"

    @staticmethod
    def node(src: str):
        return json.loads(subprocess.run([NODE, "-e", src], capture_output=True, text=True, timeout=60, check=True).stdout)

    def test_a_change_to_the_picked_versions_reaches_every_card_of_that_run_only(self) -> None:
        start = self.PAGE.index("var PICKED_SUBS = {};")
        bus = "var PICKED_SUBS = {};\n" + self.fns("busKey", "readBus", "writeBus", "subscribeBus", "pickedKey", "readPicked", "writePicked", "subscribePicked", "togglePicked")
        stub = "var mem = {}; function load(k, d) { return k in mem ? mem[k] : d; } function store(k, v) { mem[k] = v; }\n"
        call = """var seen = { ranked: [], table: [], other: [] };
          var stopRanked = subscribePicked("d:r1", function (o) { seen.ranked.push(o); });
          subscribePicked("d:r1", function (o) { seen.table.push(o); });
          subscribePicked("d:r2", function (o) { seen.other.push(o); });
          writePicked("d:r1", togglePicked(readPicked("d:r1"), "v3"));
          stopRanked();
          writePicked("d:r1", togglePicked(readPicked("d:r1"), "v3"));
          console.log(JSON.stringify({ seen: seen, stored: readPicked("d:r1"), key: pickedKey("d:r1") }));"""
        got = self.node(stub + bus + call)
        self.assertEqual(got["seen"]["ranked"], [["v3"]], "a card listening gets the change; once it unmounts, nothing more")
        self.assertEqual(got["seen"]["table"], [["v3"], []], "every card on the run sees the untick and the tick back")
        self.assertEqual(got["seen"]["other"], [], "another run's (or session's) cards are untouched")
        self.assertEqual(got["stored"], [], "the list is stored, so a reload keeps it")
        self.assertEqual(got["key"], "d:r1:picked", "under the run's scope, so Reset (forget(dataset + ':')) clears it")
        self.assertLess(start, self.PAGE.index("function useCard("))

    def test_every_card_reads_and_writes_the_shared_selection(self) -> None:
        use = BuildTests.studio_function("useCard")
        self.assertIn("var pk = usePicked(scope), setPicked = pk[1], fk = useFocus(scope), setFocus = fk[1];", use)
        self.assertIn("return [Object.assign({}, v, { offV: pk[0], focusV: fk[0] }), setAll];", use, "every card's offV and focusV are the run's shared lists")
        self.assertIn('if ("offV" in patch) setPicked(patch.offV);', use, "set({ offV }) from any card goes to the shared list")
        self.assertIn('if ("focusV" in patch) setFocus(patch.focusV);', use, "set({ focusV }) likewise")
        self.assertIn("delete n.offV; delete n.focusV;", use, "no card keeps a private copy that could drift")
        self.assertIn("useEffect(function () { setList(readBus(scope, kind)); return subscribeBus(scope, kind, setList); }, [scope, kind]);", BuildTests.studio_function("useBus"))
        self.assertIn('return useBus(scope, "picked");', BuildTests.studio_function("usePicked"))
        self.assertIn('return useBus(scope, "focus");', BuildTests.studio_function("useFocus"))
        card = BuildTests.studio_function("Card")
        self.assertIn("set({ offV: o });", card, "the Versions boxes")
        self.assertIn("set({ offV: [] });", card, "All")
        self.assertIn("set({ offV: vlist.slice() });", card, "None")
        table = BuildTests.studio_function("SummaryCard")
        self.assertIn('cs[1]({ offV: togglePicked(c.offV || [], r.label) });', table, "a table row's box")
        self.assertIn('class=${[off ? "unpicked" : "", sel ? "focused" : ""].join(" ").trim()}', table, "an unticked row stays listed, dimmed; a selected one is marked")
        self.assertNotRegex(self.PAGE, r"load\([^)]*\)\.offV", "no card reads offV around the shared list")

    def test_selected_versions_are_their_own_list_beside_the_hidden_ones(self) -> None:
        bus = "var PICKED_SUBS = {};\n" + self.fns("busKey", "readBus", "writeBus", "subscribeBus", "togglePicked")
        stub = "var mem = {}; function load(k, d) { return k in mem ? mem[k] : d; } function store(k, v) { mem[k] = v; }\n"
        call = """var hid = [], sel = [];
          subscribeBus("d:r1", "picked", function (o) { hid.push(o); }); subscribeBus("d:r1", "focus", function (o) { sel.push(o); });
          writeBus("d:r1", "focus", togglePicked(readBus("d:r1", "focus"), "v12"));
          writeBus("d:r1", "focus", togglePicked(readBus("d:r1", "focus"), "v3"));
          writeBus("d:r1", "focus", togglePicked(readBus("d:r1", "focus"), "v12"));
          console.log(JSON.stringify({ hid: hid, sel: sel, key: busKey("d:r1", "focus") }));"""
        got = self.node(stub + bus + call)
        self.assertEqual(got["sel"], [["v12"], ["v12", "v3"], ["v3"]], "select, select another, click again to clear")
        self.assertEqual(got["hid"], [], "selecting never hides")
        self.assertEqual(got["key"], "d:r1:focus", "under the run's scope, so Reset clears it")

    def pick_js(self) -> str:
        # A tiny React stand-in: h builds plain objects, the context is whatever the test provides.
        return ("var CTX = null, React = { createContext: function () { return {}; }, useContext: function () { return CTX; } };"
                "function h(type, props) { return { type: type, props: props || {}, children: [].slice.call(arguments, 2) }; }\n"
                + "var PickCtx = React.createContext(null);\n" + self.fns("pickable", "Pick"))

    def test_a_mark_selects_its_version_and_never_navigates(self) -> None:
        call = """var calls = [], window = { open: function (u) { calls.push(["open", u]); } }, location = { assign: function (u) { calls.push(["go", u]); } }, tip = { show: function (l, href) { calls.push(["show", l, href]); }, hide: function () { calls.push(["hide"]); }, hideSoon: function () { calls.push(["hideSoon"]); },
              openFor: function () { return true; }, focusLink: function () { calls.push(["link"]); return true; }, contains: function () { return false; } };
          CTX = { focusV: ["v3"], toggleFocus: function (l) { calls.push(["toggle", l]); }, tip: tip };
          var el = pickable("https://a/versions/x", "v12", { type: "circle" }, false, ["v12: try"]), g = Pick(Object.assign({}, el.props, { children: el.children[0] }));
          var ev = function (key, shift) { var e = { key: key, shiftKey: !!shift, prevented: false, preventDefault: function () { e.prevented = true; }, stopPropagation: function () {}, currentTarget: "mark" }; return e; };
          g.props.onClick(ev()); var enter = ev("Enter"); g.props.onKeyDown(enter); var space = ev(" "); g.props.onKeyDown(space);
          g.props.onKeyDown(ev("Escape")); var tab = ev("Tab"); g.props.onKeyDown(tab); g.props.onMouseEnter(ev()); g.props.onFocus(ev());
          var mouse = Pick(Object.assign({}, pickable(null, "v3", {}, true, null).props, { children: {} }));
          CTX = null; var bare = Pick({ label: "v1", children: "child" });
          console.log(JSON.stringify({ type: g.type, cls: g.props.className, role: g.props.role, tab: g.props.tabIndex, pressed: g.props["aria-pressed"], href: "href" in g.props,
            calls: calls, prevented: [enter.prevented, space.prevented, tab.prevented], mouse: [mouse.props.className, mouse.props.tabIndex, mouse.props["aria-hidden"]], bare: bare }));"""
        got = self.node(self.pick_js() + call)
        self.assertEqual(got["type"], "g", "a group, not an <a>: a click never opens Artemis")
        self.assertFalse(got["href"])
        self.assertEqual((got["role"], got["tab"], got["pressed"]), ("button", 0, "false"), "a keyboard stop that says whether it is selected")
        self.assertEqual(got["calls"][:3], [["toggle", "v12"], ["toggle", "v12"], ["toggle", "v12"]], "click, Enter and Space all toggle the selection")
        self.assertEqual(got["calls"][3:], [["hide"], ["link"], ["show", "v12", "https://a/versions/x"], ["show", "v12", "https://a/versions/x"]],
                         "Escape closes the tooltip, Tab goes into its link, hover and focus open it with the version's Artemis link")
        self.assertEqual(got["prevented"], [True, True, True])
        self.assertEqual(got["mouse"], ["vmark focused", -1, "true"], "a bar beside its tabbable label is mouse-only, and shows it is selected")
        self.assertEqual(got["bare"], "child", "outside a card it draws the mark alone")

    def test_a_selected_version_that_is_then_hidden_dims_nothing(self) -> None:
        # Select v2 by its table name, then untick its box: no card may fade every mark with none left to emphasise.
        call = """var vlist = ["v1", "v2", "v3"], focus = ["v2"], off = [];
          var before = focusShown(focus, vlist, off); off = off.concat(["v2"]); var after = focusShown(focus, vlist, off);
          var other = focusShown(["v2", "v3"], vlist, ["v2"]), elsewhere = focusShown(["v9"], vlist, []);
          console.log(JSON.stringify([before, after, other, elsewhere]));"""
        got = self.node(self.fns("focusShown") + call)
        self.assertEqual(got, [True, False, True, False], "selected and shown emphasises; selected then hidden, or not on this card, dims nothing")
        card = BuildTests.studio_function("Card")
        self.assertIn("hasFocus = focusShown(focusV, vlist, c.offV || []);", card)
        self.assertIn("${hasFocus ? html`<button type=\"button\" class=\"btn clear-sel\"", card, "Clear selection shows only with something to clear")

    def test_a_sessions_bar_is_drawn_plain_and_a_ranked_bar_selects(self) -> None:
        call = """var T = { card: "C", neutral: "N" }, colors = function () { return "G"; };
          var sp = { x: 10, y: 5, width: 40, height: 20, index: 0, payload: { label: "Session 1|version 3", tip: ["Session 1"], shown: 4, clip: 0 } };
          var plain = hbarShape(T, colors, true, true)(sp), ranked = hbarShape(T, colors, true)(Object.assign({}, sp, { payload: { v: "v3", href: "h", tip: ["v3"], shown: 4, clip: 0 } }));
          console.log(JSON.stringify({ plain: plain.type === Pick, ranked: ranked.type === Pick, label: ranked.props.label, href: ranked.props.href, mouseOnly: ranked.props.mouseOnly }));"""
        got = self.node(self.pick_js() + self.fns("hbarShape") + call)
        self.assertEqual((got["plain"], got["ranked"]), (False, True), "a sessions bar never opens VTip or selects a label no other card knows")
        self.assertEqual((got["label"], got["href"], got["mouseOnly"]), ("v3", "h", True))
        self.assertIn("shape=${hbarShape(T, colorOf, true, true)}", BuildTests.studio_function("SessionsCard"))
        self.assertIn("shape=${hbarShape(T, colorOf, true)}", BuildTests.studio_function("RankedCard"))

    def test_the_version_tooltip_is_a_non_modal_dialog_its_mark_points_at(self) -> None:
        call = """var tip = { show: function () {}, hide: function () {}, hideSoon: function () {}, openFor: function (l) { return l === "v12"; }, focusLink: function () { return false; }, contains: function () { return false; } };
          CTX = { focusV: [], toggleFocus: function () {}, tip: tip, tipId: "ds-ranked-vtip" };
          var open = Pick(Object.assign({}, pickable("h", "v12", {}, false, ["v12"]).props, { children: {} })), shut = Pick(Object.assign({}, pickable("h", "v3", {}, false, ["v3"]).props, { children: {} }));
          var mouse = Pick(Object.assign({}, pickable("h", "v12", {}, true, ["v12"]).props, { children: {} }));
          console.log(JSON.stringify([open.props["aria-describedby"] || null, shut.props["aria-describedby"] || null, mouse.props["aria-describedby"] || null]));"""
        got = self.node(self.pick_js() + call)
        self.assertEqual(got, ["ds-ranked-vtip", None, None], "the focused mark whose tooltip is open points at it")
        card = BuildTests.studio_function("Card")
        self.assertIn('<div class="tip vtip" id=${tipId} role="dialog" aria-modal="false" aria-label=${tipV.label + " details"}', card)
        self.assertNotIn('role="tooltip"', card, "a tooltip role can't hold a focusable link")
        self.assertIn('var tipId = fileBase + "-vtip"', card)

    def test_the_shipped_skill_names_behaviour_not_people_or_decisions(self) -> None:
        # Readers of the skill see what the studio does; who asked for it, and which option was picked, stay out.
        for f in [ROOT / "SKILL.md", ROOT / "assets" / "chart-studio.html", ROOT / "assets" / "studio-core.js"] + sorted((ROOT / "references").glob("*.md")):
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=f.name):
                self.assertNotRegex(text, r"(?i)\bEoin\b|\boption \(b\)")

    def test_markers_by_role_best_solid_others_open_original_grey(self) -> None:
        # One marker scheme on every trade-off and Pareto view: Best a solid purple triangle with its halo, every other version an
        # open purple triangle, the original a grey (slate) triangle, a gate failure its red cross.
        call = """var T = { accent: "ACC", card: "CARD", orig: "ORIG", halo: "HALO" };
          var one = function (e) { return { cls: e.props.className, fill: e.props.fill, stroke: e.props.stroke }; };
          console.log(JSON.stringify({ best: one(versionTri(T, 0, 0, 8, true)), other: one(versionTri(T, 0, 0, 8, false)), orig: one(origTriMark(T, 0, 0, 11)),
            bestLegend: bestLegend(T).map(function (e) { return [e.type, e.props.fill]; }), origLegend: [origLegend(T).type, origLegend(T).props.fill, origLegend(T).props.stroke] }));"""
        js = "function h(type, props) { return { type: type, props: props || {}, children: [].slice.call(arguments, 2) }; }\n" + self.fns("legendTri", "bestLegend", "origLegend", "origTriMark", "origTri", "versionTri")
        got = self.node(js + call)
        self.assertEqual(got["best"], {"cls": "vtri best", "fill": "ACC", "stroke": "ACC"}, "the Best: solid purple")
        self.assertEqual(got["other"], {"cls": "vtri", "fill": "CARD", "stroke": "ACC"}, "every other version: open purple")
        self.assertEqual(got["orig"], {"cls": "otri", "fill": "ORIG", "stroke": "CARD"}, "the original: grey, never orange")
        self.assertEqual(got["bestLegend"], [["circle", "HALO"], ["polygon", "currentColor"]], "the Best's swatch: halo and solid triangle")
        self.assertEqual(got["origLegend"], ["polygon", "currentColor", "CARD"])
        values, pct, pareto = (BuildTests.studio_function(n) for n in ("TradeOffValues", "TradeOffCard", "ParetoCard"))
        self.assertIn("var isBest = p === bp && isArtemisBest(D) && !p.gate, body = p.gate ? crossMark(T, cx, cy) : versionTri(T, cx, cy, R, isBest);", values, "a gate failure keeps its cross")
        self.assertIn("isBest && !hd.best ? bestHalo(T, cx, cy, R + 8) : null", values)
        self.assertIn("var isBest = p === bp && isArtemisBest(D), styled = versionTri(T, cx, cy, r, isBest);", pct)
        self.assertIn("isBest && !hd.best ? bestHalo(T, cx, cy, r + 8) : null", pct)
        self.assertIn("versionTri(T, p.cx, p.cy, 8, isBest)", pareto)
        self.assertIn("isBest && !hd.best ? bestHalo(T, p.cx, p.cy, 15) : null", pareto)
        for name, body in (("values", values), ("pct", pct), ("pareto", pareto)):
            with self.subTest(card=name):
                self.assertIn('label: "Best (filled, with halo)", color: T.accent, mark: bestLegend(T)', body)
                self.assertIn("color: T.orig, mark: [origLegend(T)]", body)
                self.assertNotRegex(body, r'fill: (p\.front|k === "front"|filled) \? T\.accent', "no filled-by-front marker left")
        self.assertEqual(self.PAGE.count("origTriMark(T, sp.cx, sp.cy, OR)"), 2, "the original in Values and % change")
        self.assertNotIn('shape: "dot" }, { key: "other"', pareto, "the Pareto legend draws triangles, not dots and rings")

    def test_every_legend_triangle_comes_from_one_helper(self) -> None:
        # The legend triangle was written five times (two tri closures, the Pareto card's open, bestLegend, origLegend).
        call = """var a = legendTri("currentColor"), b = legendTri("CARD", 0.75), c = legendTri("currentColor", undefined, 6.5, "CARD");
          var one = function (e) { return [e.type, e.props.fill, e.props.stroke, e.props.opacity === undefined ? null : e.props.opacity, e.props.points]; };
          console.log(JSON.stringify([one(a), one(b), one(c)]));"""
        js = "function h(type, props) { return { type: type, props: props || {}, children: [].slice.call(arguments, 2) }; }\n" + self.fns("legendTri", "origTri")
        got = self.node(js + call)
        self.assertEqual([g[:4] for g in got], [["polygon", "currentColor", "currentColor", None], ["polygon", "CARD", "currentColor", 0.75], ["polygon", "currentColor", "CARD", None]])
        self.assertEqual(got[0][4], "0 -6.5 5.5 4.5 -5.5 4.5", "5.5 by default")
        self.assertEqual(got[2][4], "0 -7.5 6.5 5.5 -6.5 5.5")
        self.assertEqual(self.PAGE.count("points: origTri(0, 0, "), 1, "only legendTri builds a legend triangle")
        self.assertNotIn("var tri = function", self.PAGE)
        self.assertIn('legendTri("currentColor")]; }', BuildTests.studio_function("bestLegend"))
        self.assertIn('return legendTri("currentColor", undefined, 6.5, T.card);', BuildTests.studio_function("origLegend"))
        self.assertIn("var open = function (op) { return [legendTri(T.card, op)]; };", BuildTests.studio_function("ParetoCard"))
        for view in ("TradeOffValues", "TradeOffCard"):
            self.assertIn("legendTri(T.card, FADE)", BuildTests.studio_function(view), view)

    def test_a_legend_keeps_every_entry_whatever_is_hidden(self) -> None:
        # The Best entry once came and went with its point: hiding "On the front" dropped it, every later entry moved up one,
        # and the checker's walk (which clicks each legend button by position, then clicks it again) lost "Original".
        for view in ("TradeOffValues", "TradeOffCard"):
            body = BuildTests.studio_function(view)
            line = next(l for l in body.splitlines() if "var bestOn = " in l)
            with self.subTest(view=view):
                self.assertNotIn("shown", line, "the Best entry is in the legend whenever the view can draw it")
                self.assertNotIn("hd.", line)
        self.assertIn("color: T.orig, mark: [origLegend(T)]", BuildTests.studio_function("TradeOffValues"), "Original stays in the legend, a grey triangle")

    def test_the_trade_off_views_draw_no_interval_marks(self) -> None:
        # No shaded boxes or whisker crosses behind the triangles: a version's interval is in its tooltip, the forest and the bars.
        for view in ("TradeOffValues", "TradeOffCard", "ParetoCard"):
            body = BuildTests.studio_function(view)
            with self.subTest(view=view):
                reads = re.findall(r"\.[xy](?:lo|hi)\b", body)
                self.assertEqual(reads, [], "nothing is drawn at an interval's ends")
                self.assertNotIn('className: "wh"', body)
                self.assertNotIn('key: "ci"', body, "no legend entry for intervals")
                self.assertNotIn("hd.ci", body)
        self.assertNotIn(".tp .wh", self.PAGE, "no leftover whisker style")
        self.assertNotIn("95% interval on each axis", self.PAGE)
        self.assertIn("bestHalo(T, cx, cy, r + 8) : null, pickable(p.href, p.v.label, styled, false, p.tip)", BuildTests.studio_function("TradeOffCard"), "no chance rings and no leader lines")

    def test_the_original_is_slate_and_no_orange_is_left(self) -> None:
        # slate-800 / slate-400, artemis-ui develop f6d00737 src/styles.css :138 and :134; the old orange --baseline is retired.
        light, dark, dark2, printed = BuildTests.token_blocks(self.PAGE)
        for block, want in ((light, "#1e293b"), (dark, "#94a3b8"), (dark2, "#94a3b8"), (printed, "#1e293b")):
            self.assertIn("--orig: " + want + ";", block)
        for gone in ("--baseline", "T.baseline", "#d9731a", "#f28c28"):
            self.assertNotIn(gone, self.PAGE)
        self.assertIn('"--orig", ', BuildTests.studio_function("tokens"), "the theme reads it into T.orig")

    def test_a_run_draws_one_trade_off_card_never_both(self) -> None:
        # A run with two measured metrics and an AI Metric once drew the trade-off card and, further down, an old Pareto card.
        both, one = two_targets(), run_snapshot()  # both: two measured targets plus an AI Metric; one: one target plus an AI Metric
        for name, snap, want in (("both", both, "tradeoff"), ("one measured", one, "pareto")):
            ds = embedded(build_studio.build([snap]))["datasets"][0]
            with self.subTest(snapshot=name):
                drawn = [c for c in ("tradeoff", "pareto") if build_studio.drawable(c, ds) is None]
                self.assertEqual(drawn, [want])
        with self.assertRaisesRegex(ValueError, "--only pareto: the trade-off card draws this run's trade-off"):
            build_studio.build([both], only="pareto")
        got = self.node(self.fns("oneTradeOff") + "console.log(JSON.stringify([oneTradeOff({ x: 'a' }, { x: 'b' }), oneTradeOff({ x: 'a' }, null), oneTradeOff(null, null)]));")
        self.assertEqual(got, [None, {"x": "a"}, None], "the trade-off wins; the Pareto card only without one")
        page = self.PAGE
        self.assertIn("pp = oneTradeOff(pp, to);", page)
        self.assertIn('pp ? [["pareto", ParetoCard]] : []).filter(function (x) { return x[0] === ONLY; })[0];', page, "--only follows the same rule")
        self.assertNotIn('pareto(D) ? [["pareto", ParetoCard]]', page)
        self.assertIn('f.tradeoff ? ["tradeoff"] : f.pareto ? ["pareto"] : []', build_studio.CORE.read_text(encoding="utf-8"), "one Trade-off rail item, and so STUDIO_CARDS, the Pareto card only without the trade-off")
        self.assertIn("railViews({ multi: multi, tradeoff: !!to, pareto: !!pp, steered: steered, boxes: boxes, ai: ai })", page)

    def test_tooltip_lines_are_drawn_by_one_helper(self) -> None:
        self.assertEqual(self.PAGE.count('class=${l[0] === "~" ? "t2" : ""}'), 1, "one copy of the line rendering")
        self.assertIn("${tipLines(p.tip)}", BuildTests.studio_function("Tip"))
        self.assertIn("${tipLines(tipV.lines)}", BuildTests.studio_function("Card"))

    def test_escape_on_the_mark_or_in_the_tooltip_closes_it(self) -> None:
        # Escape in the tooltip once hid it and gave focus back to the mark, whose focus opened it again in the same render.
        call = """var state = null, rect = { left: 0, top: 0, right: 10, width: 800 }, ctl;
          var o = { now: function () { return state; }, set: function (v) { state = v; }, tipRef: { current: null }, timer: { current: 0 }, from: { current: null }, quiet: { current: null },
                    card: function () { return { getBoundingClientRect: function () { return rect; } }; }, hoverMs: function () { return 0; } };
          ctl = tipController(o);
          CTX = { focusV: [], toggleFocus: function () {}, tip: ctl, tipId: "t" };
          var g = Pick(Object.assign({}, pickable("h", "v12", {}, false, ["v12"]).props, { children: {} }));
          var mark = { getBoundingClientRect: function () { return rect; }, focus: function () { g.props.onFocus({ currentTarget: mark }); } };
          var key = function (k) { return { key: k, shiftKey: false, preventDefault: function () {}, stopPropagation: function () {}, currentTarget: mark }; };
          mark.focus(); var opened = !!state; g.props.onKeyDown(key("Escape")); var onMark = state;
          mark.focus(); var again = !!state; ctl.escape(); var inTip = state, quiet = o.quiet.current;
          mark.focus(); var reopen = !!state;
          console.log(JSON.stringify({ opened: opened, onMark: onMark, again: again, inTip: inTip, quiet: quiet, reopen: reopen, back: o.from.current === mark }));"""
        got = self.node(self.pick_js() + self.fns("tipController") + call)
        self.assertTrue(got["opened"] and got["again"], "focus opens the tooltip")
        self.assertIsNone(got["onMark"], "Escape on the focused mark closes it")
        self.assertIsNone(got["inTip"], "Escape in the tooltip closes it, though focus goes back to the mark")
        self.assertIsNone(got["quiet"], "only that one return of focus is skipped")
        self.assertTrue(got["reopen"], "focusing the mark later opens it again")
        self.assertIn('if (e.key === "Escape") { e.preventDefault(); tipApi.escape(); }', BuildTests.studio_function("Card"))

    def test_the_tooltip_carries_open_in_artemis_and_marks_no_longer_link(self) -> None:
        card = BuildTests.studio_function("Card")
        self.assertIn('${tipV.href ? html`<a class="vtip-link" href=${tipV.href} target="_blank" rel="noopener">Open in Artemis ↗</a>` : null}', card)
        self.assertIn("onMouseEnter=${tipApi.keep} onMouseLeave=${tipApi.hideSoon} onKeyDown=${tipKey}", card, "it stays open while the pointer is on it")
        self.assertIn('if (e.key === "Escape") { e.preventDefault(); tipApi.escape(); }', card, "Escape closes it and returns to the mark")
        self.assertIn('hoverMs: function () { return ms("--t-hover"); }', card, "the hover token, not a new duration")
        self.assertIn("o.timer.current = setTimeout(function () { o.set(null); }, o.hoverMs());", BuildTests.studio_function("tipController"))
        self.assertIn("h(PickCtx.Provider, { value: pickCtx }, html`<section", card)
        self.assertIn('(hasFocus ? " has-focus" : "")', card)
        self.assertIn('onClick=${function () { set({ focusV: [] }); }}>Clear selection</button>', card)
        self.assertIn('if ("href" in p) return null;', BuildTests.studio_function("Tip"), "Recharts' tooltip steps aside for a version mark")
        self.assertNotIn('className: "vlink"', self.PAGE, "no mark is an <a> any more")
        self.assertNotIn("function linked(", self.PAGE)
        self.assertEqual(self.PAGE.count("pickable(") - 1, 9, "every former link site goes through pickable")
        self.assertIn(".card.has-focus .vmark:not(.focused) { opacity: var(--dim); }", self.PAGE)
        self.assertRegex(self.PAGE[:self.PAGE.index("[data-theme")], r"--dim: 0\.3;", "the dim level is a token")
        time = BuildTests.studio_function("TimeCard")
        self.assertIn('h(Pick, { key: "d", href: null, label: pl.label, mouseOnly: true, tip: null }', time, "the leaders chart's dots select too")
        table = BuildTests.studio_function("SummaryCard")
        self.assertIn('onClick=${function () { cs[1]({ focusV: togglePicked(c.focusV || [], r.label) }); }}', table, "a row's name selects")
        self.assertIn('cs[1]({ offV: togglePicked(c.offV || [], r.label) });', table, "its box still hides")

    def test_the_trade_off_controls_sit_on_one_aligned_row(self) -> None:
        card = BuildTests.studio_function("TradeOffCard")
        self.assertIn('controls: html`<div class="ctls">${axes}${plotSeg}</div>`', card, "Values and Within the cap")
        self.assertIn('controls=${html`<div class="ctls">${axes}${plotSeg}</div>`}', card, "% change: the same row, no zoom")
        self.assertNotIn('label="View"', card, "no Front / All zoom")
        self.assertNotIn("small=${true}", card, "the axis menus are the same size as Plot and View")
        self.assertIn('controls=${html`<div class="ctls">${sel(kx, "x")}${sel(ky, "y")}</div>`}', BuildTests.studio_function("ParetoCard"))
        self.assertIn(".ctls { display: inline-flex; flex-wrap: wrap; gap: 8px 12px; align-items: flex-end; }", self.PAGE)
        self.assertIn(".ctls select, .ctls .seg { height: 34px; }", self.PAGE, "one height for menus and segmented buttons")
        self.assertIn("@media (max-width: 559px) { .ctls { flex: 1 1 100%; }", self.PAGE, "a phone gives the row its own line")

    def corner_js(self) -> str:
        core = (ROOT / "assets" / "studio-core.js").read_text(encoding="utf-8")
        return ("var PHONE_W = 560; function textW(s, px) { return String(s).length * px * 0.62; }\n" + core + "\n"
                + self.fns("overlaps", "originBox", "refBox", "cornerSpot", "niceStep", "niceAxis", "pctAxes"))

    def test_better_on_both_never_sits_on_the_original_or_a_reference(self) -> None:
        # Values once passed only the version markers, so the text could cover the stock reference near the better corner.
        call = """var c = { x: "left", y: "bottom" }, L0 = 78, R0 = 1000, T0 = 24, B0 = 340, t = "Better on both ↙";
          console.log(JSON.stringify({ clear: cornerSpot(c, t, [], L0, R0, T0, B0) !== null,
            ref: cornerSpot(c, t, [refBox(L0 + 40, B0 - 8, "stock Q4_K_M")], L0, R0, T0, B0),
            orig: cornerSpot(c, t, [originBox(L0 + 20, B0 - 30)], L0, R0, T0, B0),
            top: cornerSpot({ x: "left", y: "top" }, t, [refBox(L0 + 40, T0 + 30, "stock")], L0, R0, T0, B0),
            touch: overlaps([0, 0, 10, 10], [10, 0, 20, 10]), cross: overlaps([0, 0, 10, 10], [9, 9, 20, 20]) }));"""
        got = self.node(self.corner_js() + call)
        self.assertTrue(got["clear"])
        self.assertIsNone(got["ref"], "a reference in the bottom corner: the text is left out, not drawn on it")
        self.assertIsNone(got["orig"], "the Original's triangle and label count too")
        self.assertEqual(got["top"], {"box": None, "y": 16, "inside": False}, "at the top it moves above the plot")
        self.assertEqual((got["touch"], got["cross"]), (False, True), "boxes that only touch don't overlap")
        values = BuildTests.studio_function("TradeOffValues")
        self.assertIn("if (bx != null && by != null && !hd.baseline) boxes.push(originBox(px(bx), py(by)));", values, "the Original, while it is drawn")
        self.assertIn('if (!hd.refs) points.forEach(function (r) { var past = !inX(r.x) || !inY(r.y); boxes.push(refBox(px(r.x), py(r.y), r.name + (past ? " " + num(mx, r.x) : ""))); });', values, "every reference point, while drawn")
        self.assertIn("spot = cornerSpot(corner, cornerText, marks, L0, R0, T0, B0);", values)
        self.assertLess(values.index("var marks = boxes.slice();"), values.index("// The reference lines' own labels"), "marks are the points, not the line labels")
        for view in ("TradeOffValues", "TradeOffCard"):
            self.assertIn("boxes.some(function (o) { return overlaps(b, o); })", BuildTests.studio_function(view), "one overlap test")
        self.assertEqual(self.PAGE.count("b[0] < o[2] && o[0] < b[2]"), 0, "no second copy of the overlap test")

    def test_two_targets_percent_view_keeps_better_on_both_clear_of_v4_at_desktop_width(self) -> None:
        # The risky case: on % change v4 plots at (-30%, 0), on the bottom row near the lower-left corner box.
        snap = two_targets()
        hib = {m["key"]: m["higherIsBetter"] for m in snap["metrics"]}
        pts = []
        for v in snap["versions"]:
            a, b = ((v["metrics"].get(k) or {}).get("vsBaseline") or {} for k in ("latency_ms", "compile_runtime"))
            if a.get("improvementPct") is None or b.get("improvementPct") is None or v.get("gateFailed"):
                continue
            sx, sy = (-1 if hib["latency_ms"] is False else 1), (-1 if hib["compile_runtime"] is False else 1)
            turn = lambda s, lo, hi: [lo, hi] if s > 0 else [-hi, -lo]
            xl, xh = turn(sx, a["ciLowPct"], a["ciHighPct"]); yl, yh = turn(sy, b["ciLowPct"], b["ciHighPct"])
            pts.append({"label": v["label"], "x": sx * a["improvementPct"], "y": sy * b["improvementPct"], "xlo": xl, "xhi": xh, "ylo": yl, "yhi": yh})
        call = f"""var pts = {json.dumps(pts)}, mx = {{ higherIsBetter: {json.dumps(hib["latency_ms"])} }}, my = {{ higherIsBetter: {json.dumps(hib["compile_runtime"])} }};
          var out = [1100, 1166, 1200].map(function (W) {{
            var ax = pctAxes(pts, true, W), X = ax.x.domain, Y = ax.y.domain, width = Math.max(W, 300), M = {{ top: 24, right: 24, left: 8, bottom: 30 }};
            var L0 = M.left + 70, R0 = width - M.right, T0 = M.top, B0 = 400 - M.bottom - 30;
            var px = function (x) {{ return L0 + (x - X[0]) / (X[1] - X[0]) * (R0 - L0); }}, py = function (y) {{ return B0 - (y - Y[0]) / (Y[1] - Y[0]) * (B0 - T0); }};
            var boxes = pts.map(function (p) {{ return [px(p.x) - 9, py(p.y) - 9, px(p.x) + 9, py(p.y) + 9]; }}).concat([originBox(px(0), py(0))]);
            var c = bestCorner(mx, my), spot = cornerSpot(c, "Better on both " + c.arrow, boxes, L0, R0, T0, B0);
            var v4 = pts.filter(function (p) {{ return p.label === "v4"; }})[0];
            return {{ W: W, corner: c.x + "-" + c.y, inside: !!(spot && spot.inside), v4: [Math.round(px(v4.x)), Math.round(py(v4.y))], box: spot && spot.box ? spot.box.map(Math.round) : null }};
          }});
          console.log(JSON.stringify(out));"""
        got = self.node(self.corner_js() + call)
        for g in got:
            self.assertEqual(g["corner"], "left-bottom", g)
            self.assertTrue(g["inside"], f"'Better on both' stays in its corner, clear of v4 and the Original: {g}")
            self.assertGreater(g["v4"][0] - 9, g["box"][2], f"v4's marker starts right of the text box: {g}")

@unittest.skipUnless(NODE, "node not installed")
class IntervalTests(unittest.TestCase):
    """A run measured once has no 95% interval anywhere, so the studio leaves out what only intervals give, the forest first."""

    @staticmethod
    def has_intervals(snap: dict) -> bool:
        fn = build_studio.CORE.read_text(encoding="utf-8")  # the page's own pure logic, as the builder inlines it
        call = f"console.log(JSON.stringify(hasIntervals({json.dumps({'versions': snap['versions']})})));"
        return json.loads(subprocess.run([NODE, "-e", fn + call], capture_output=True, text=True, timeout=60, check=True).stdout)

    def test_a_run_measured_once_has_no_intervals_and_draws_no_forest(self) -> None:
        once = run_snapshot()
        self.assertFalse(any((m.get("vsBaseline") or {}).get("ciLowPct") is not None for v in once["versions"] for m in v["metrics"].values()))
        self.assertFalse(self.has_intervals(once))
        page = (Path(build_studio.__file__).resolve().parent.parent / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        # Both places that pick the forest ask first: the change card's toggle, and the cards the page reports it drew.
        self.assertIn('view = c.view === "forest" && ci ? "forest" : "bar"', page)
        self.assertIn('var changeView = load(scope + ":change", {}).view === "forest" && hasIntervals(D) ? "forest" : "ranked"', page)

    def test_one_version_with_an_interval_keeps_the_forest(self) -> None:
        snap = run_snapshot()
        v = next(v for v in snap["versions"] if (v["metrics"].get("latency_ms") or {}).get("vsBaseline"))
        v["metrics"]["latency_ms"]["vsBaseline"].update(ciLowPct=1.0, ciHighPct=9.0)
        self.assertTrue(self.has_intervals(snap))
        self.assertTrue(self.has_intervals(with_intervals(run_snapshot())))


@unittest.skipUnless(NODE, "node not installed")
class LinkCoreTests(unittest.TestCase):
    """Option C: a link goes only under the run's own Web UI origin, the one the collector built its URLs on."""

    ORIGIN = "https://artemis.acme.example"

    def href(self, fn: str, run: dict):
        return TradeOffCoreTests.run_js(f"{fn}({json.dumps(run)})")

    def test_any_https_deployment_links_its_own_run_and_project(self) -> None:
        run = {"webOrigin": self.ORIGIN, "webUrl": self.ORIGIN + "/projects/p-1/discover/r-1/", "projectUrl": self.ORIGIN + "/projects/p-1"}
        self.assertEqual(self.href("runHref", run), self.ORIGIN + "/projects/p-1/discover/r-1")
        self.assertEqual(self.href("projectHref", run), self.ORIGIN + "/projects/p-1")
        port = {"webOrigin": self.ORIGIN + ":8443", "webUrl": self.ORIGIN + ":8443/projects/p/discover/r"}
        self.assertEqual(self.href("runHref", port), port["webUrl"])

    def test_nothing_outside_the_runs_own_origin_is_linked(self) -> None:
        url = "/projects/p/discover/r"
        for run in ({"webUrl": "https://artemis.turintech.ai" + url},  # no origin: an older snapshot
                    {"webOrigin": self.ORIGIN, "webUrl": "https://artemis.turintech.ai" + url},
                    {"webOrigin": self.ORIGIN, "webUrl": self.ORIGIN + ".evil.example" + url},
                    {"webOrigin": self.ORIGIN, "webUrl": self.ORIGIN + ":8443" + url},
                    {"webOrigin": self.ORIGIN, "webUrl": self.ORIGIN + url + "/versions"},
                    {"webOrigin": self.ORIGIN, "webUrl": self.ORIGIN + "/projects/p?next=https://evil.example/discover/r"},
                    {"webOrigin": "http://artemis.acme.example", "webUrl": "http://artemis.acme.example" + url},
                    {"webOrigin": "javascript:alert(1)//", "webUrl": "javascript:alert(1)//" + url},
                    {"webOrigin": self.ORIGIN + "/x", "webUrl": self.ORIGIN + "/x" + url}):
            with self.subTest(run=run):
                self.assertIsNone(self.href("runHref", run))
        self.assertIsNone(self.href("projectHref", {"webOrigin": self.ORIGIN, "projectUrl": self.ORIGIN + "/projects/p/discover/r"}), "the project link is the project page only")


class TradeOffCoreTests(unittest.TestCase):
    """The trade-off's rules on the template's own functions: what a run is comes from the collector, never from a metric's name."""

    @staticmethod
    def run_js(call: str):
        fns = build_studio.CORE.read_text(encoding="utf-8")
        return json.loads(subprocess.run([NODE, "-e", fns + f"console.log(JSON.stringify({call}));"], capture_output=True, text=True, timeout=60, check=True).stdout)

    SIZE = {"key": "model_size_mb", "unit": "MB", "higherIsBetter": False, "role": "budget", "cap": 1319.830496}
    WER = {"key": "pooled_wer_ratio_vs_q8", "unit": None, "higherIsBetter": False}

    def test_two_lower_is_better_metrics_are_better_down_and_left(self) -> None:
        self.assertEqual(self.run_js(f"bestCorner({json.dumps(self.SIZE)}, {json.dumps(self.WER)})"), {"x": "left", "y": "bottom", "arrow": "↙"})

    def test_each_direction_sets_its_own_side(self) -> None:
        fps = {"key": "fps", "higherIsBetter": True}
        self.assertEqual(self.run_js(f"bestCorner({json.dumps(fps)}, {json.dumps(self.WER)})")["arrow"], "↘")
        self.assertEqual(self.run_js(f"bestCorner({json.dumps(self.SIZE)}, {json.dumps(fps)})")["arrow"], "↖")
        self.assertEqual(self.run_js(f"bestCorner({json.dumps(fps)}, {json.dumps(fps)})")["arrow"], "↗")

    def test_the_fronts_staircase_turns_at_the_corner_both_neighbours_beat(self) -> None:
        # Two neighbours on a front, sorted by x: one wins on x, the other on y, for every pair of directions.
        for hx, hy, want in [(True, True, {"x": 1, "y": 2}), (False, False, {"x": 3, "y": 5}), (True, False, {"x": 1, "y": 5}), (False, True, {"x": 3, "y": 2})]:
            with self.subTest(hib=(hx, hy)):
                axes = [{"key": "x", "hib": hx}, {"key": "y", "hib": hy}]
                a_wins_y = hx  # the larger x wins on x when higher is better, so the smaller x must win on y
                a, b = ({"x": 1, "y": 5 if hy else 2}, {"x": 3, "y": 2 if hy else 5}) if a_wins_y else ({"x": 1, "y": 2 if hy else 5}, {"x": 3, "y": 5 if hy else 2})
                corner = self.run_js(f"stairCorner({json.dumps(a)}, {json.dumps(b)}, {json.dumps(axes)})")
                self.assertEqual(corner, want)
                for p in (a, b):  # both neighbours are at least as good as the corner on each axis
                    for ax in axes:
                        self.assertTrue(p[ax["key"]] >= corner[ax["key"]] if ax["hib"] else p[ax["key"]] <= corner[ax["key"]], (p, corner, ax))

    def test_every_pair_opens_on_values_and_only_the_budget_metric_adds_the_cap_view(self) -> None:
        self.assertEqual(self.run_js(f"tradeoffViews({json.dumps(self.SIZE)}, {json.dumps(self.WER)})"), ["values", "quality", "pct"])
        self.assertEqual(self.run_js(f"tradeoffViews({json.dumps(self.WER)}, {json.dumps(self.SIZE)})"), ["values", "quality", "pct"], "either axis")
        # Pairs a name rule took for model compression: with no budget role there is no within-the-cap view.
        for x, y in [("bytes_per_op", "ns_per_op"), ("payload_size_kb", "time_per_request_ms"), ("rss_mb", "error_rate"), ("model_size_mb", "pooled_wer")]:
            with self.subTest(pair=(x, y)):
                self.assertEqual(self.run_js(f"tradeoffViews({{key: '{x}', unit: 'MB', higherIsBetter: false}}, {{key: '{y}', higherIsBetter: false}})"), ["values", "pct"])

    def test_the_front_is_read_from_the_collector_in_either_order(self) -> None:
        snap = {"fronts": {"a": {"b": ["v2", "v4"]}}}
        self.assertEqual(self.run_js(f"frontOf({json.dumps(snap)}, 'a', 'b')"), ["v2", "v4"])
        self.assertEqual(self.run_js(f"frontOf({json.dumps(snap)}, 'b', 'a')"), ["v2", "v4"], "one entry per pair, either way round")
        self.assertIsNone(self.run_js(f"frontOf({json.dumps(snap)}, 'a', 'c')"))
        self.assertIsNone(self.run_js("frontOf({}, 'a', 'b')"))
        core = build_studio.CORE.read_text(encoding="utf-8")
        for gone in ("function dominates", "function onFront", "paretoChances", "MC_DRAWS", "MC_SEED", "PCT_AXES"):
            self.assertNotIn(gone, core, "the page works out no front, and no chance of being on one")

    def test_the_pareto_card_claims_no_front_the_collector_did_not_store(self) -> None:
        body = BuildTests.studio_function("ParetoCard")
        self.assertNotIn("frontOf(D.s, kx, ky) || []", body, "no stored front is never read as an empty front, which would call every version beaten")
        self.assertIn('status: v._gate ? "gate" : !stored ? "plain" : stored.indexOf(v.label) >= 0 ? "front" : "other"', body)
        self.assertIn("var src = v._gate ? { metrics: v._raw } : v", body, "a gate failure is drawn from its raw readings")
        self.assertIn("crossMark(T, p.cx, p.cy)", body, "as a cross, as on the trade-off card")
        self.assertIn('useCard(props.scope, "pareto", { hidden: { gate: true } })', body, "hidden at first")
        self.assertEqual(body.count("allowDataOverflow=${true}"), 2, "both axes keep their domain when a cross is past it")
        self.assertIn("x: clampTo(d.x, X), y: clampTo(d.y, Y)", body, "a gate cross past the axes sits at the edge")
        self.assertIn("edgeArrow(p.cx, p.cy, p.payload.dx, p.payload.dy, T.worse)", body, "with the trade-off's own edge arrow")
        self.assertEqual((ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8").count("function edgeArrow("), 1, "one copy of the helper")

    def test_one_run_each_is_read_from_the_iterations(self) -> None:
        v = lambda n: {"metrics": {"wer": {"vsBaseline": {"readings": n}}}}
        self.assertTrue(self.run_js(f"measuredOnce([{json.dumps(v(1))}, {json.dumps(v(1))}], {{wer: 1}}, ['wer'])"))
        self.assertFalse(self.run_js(f"measuredOnce([{json.dumps(v(1))}, {json.dumps(v(5))}], {{wer: 1}}, ['wer'])"), "one version run five times")
        self.assertFalse(self.run_js(f"measuredOnce([{json.dumps(v(1))}], {{wer: 5}}, ['wer'])"), "the original run five times")

    def test_a_sourced_reference_is_the_same_size_rival_and_says_it_fails_the_gate(self) -> None:
        refs = [{"label": "stock Q4_K_M", "metrics": {"pooled_wer_ratio_vs_q8": 1.187, "model_size_mb": 1319.83, "eligible": 0}, "gateFailed": True,
                 "failures": ["nonspeech: 23 runaway clips only the candidate has"], "source": {"file": "handy_q4km-dev.json"}},
                {"label": "Q8_0", "metrics": {"pooled_wer_ratio_vs_q8": 1.0, "model_size_mb": 2185.03}, "gateFailed": False, "source": {"file": "q8_0-dev.json"}},
                {"label": "unrelated", "metrics": {"latency_ms": 3}}]
        got = self.run_js(f"tradeoffRefs({json.dumps(refs)}, 'model_size_mb', 'pooled_wer_ratio_vs_q8', {json.dumps(self.SIZE)})")
        self.assertEqual([(r["name"], r["x"], r["y"], r["same"], r["gateFailed"], r["why"], r["file"]) for r in got],
                         [("stock Q4_K_M", 1319.83, 1.187, True, True, "nonspeech", "handy_q4km-dev.json"), ("Q8_0", 2185.03, 1.0, False, False, None, "q8_0-dev.json")])
        self.assertEqual(self.run_js(f"tradeoffRefs([], 'model_size_mb', 'pooled_wer_ratio_vs_q8', null)"), [])


@unittest.skipUnless(NODE, "node not installed")
class LeaderStepTests(unittest.TestCase):
    """The version chart's new leaders, read from the collector's runningBest on the template's own function."""

    @staticmethod
    def steps(series: list) -> list:
        fn = build_studio.CORE.read_text(encoding="utf-8")
        call = f"console.log(JSON.stringify(leaderSteps({json.dumps(series)})));"
        return json.loads(subprocess.run([NODE, "-e", fn + call], capture_output=True, text=True, timeout=60, check=True).stdout)

    def test_a_version_that_is_its_own_best_so_far_is_a_numbered_new_leader(self) -> None:
        series = run_snapshot()["runningBest"]["latency_ms"]
        led = [r["version"] for r in series if r["mean"] is not None and r["bestVersion"] == r["version"]]
        self.assertTrue(led)
        self.assertEqual(self.steps(series), [{"version": v, "first": i == 0, "n": i} for i, v in enumerate(led)])

    def test_gaps_are_not_new_leaders(self) -> None:
        series = [{"version": 1, "mean": None, "bestVersion": None}, {"version": 2, "mean": 5, "bestVersion": 2}, {"version": 3, "mean": 6, "bestVersion": 2},
                  {"version": 4, "mean": None, "bestVersion": 2}, {"version": 5, "mean": 4, "bestVersion": 5}]
        self.assertEqual(self.steps(series), [{"version": 2, "first": True, "n": 0}, {"version": 5, "first": False, "n": 1}])
        self.assertEqual(self.steps([]), [], "a metric with no stored direction has an empty runningBest")

    def test_the_phone_flag_is_set_before_the_legend_reads_it(self) -> None:
        body = BuildTests.studio_function("TimeCard")
        self.assertLess(body.index("var narrowT = W < PHONE_W;"), body.index("!narrowT"),
                        "a phone legend never promises leader numbers the chart does not draw")

    def test_no_leader_is_called_clear_or_within_noise(self) -> None:
        body = re.sub(r"/\*.*?\*/|//[^\n]*", "", BuildTests.studio_function("TimeCard"), flags=re.S)
        for gone in ("clear", "within noise", "ciLowPct", "ciHighPct", "noisy"):
            self.assertNotIn(gone, body)
        self.assertIn("(D.s.runningBest || {})[key]", body, "the leader so far is the collector's")


class ComputedHereLabelTests(unittest.TestCase):
    """One wording for what the page works out itself, the same in the studio and the report kit."""

    def test_the_studio_and_the_report_kit_use_the_same_words(self) -> None:
        # Both say what the page works out the same way, and neither says "computed here" in anything a reader sees
        # (comments may still name the old words, to say they are gone).
        for name in ("studio-core.js", "report-kit.js"):
            src = (ROOT / "assets" / name).read_text(encoding="utf-8")
            code = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S)
            with self.subTest(file=name):
                self.assertRegex(code, r"""\bhere\(what\) \{ return what \+ (['"]): worked out on this page from Artemis\\?'s numbers\1;""")
                self.assertNotRegex(code, r"(?i)computed here")
        kit = (ROOT / "assets" / "report-kit.js").read_text(encoding="utf-8")
        self.assertIn('const HERE = "Worked out on this page from Artemis\'s numbers";', kit, "the kit's tag says the same words")

    def test_the_studio_shows_no_computed_here_label(self) -> None:
        # The studio carries no "Computed here, not by Artemis" chip or header line; a card's ⓘ still says what it works out.
        page = (ROOT / "assets" / "chart-studio.html").read_text(encoding="utf-8")
        self.assertNotIn('class="tag here"', page)
        self.assertNotIn("${HERE}", page)
        self.assertNotIn("madeLine", page)
        self.assertIn("props.here ? here(props.here) : null", page, "the ⓘ keeps what the card works out")
        for card in ("RankedCard", "TimeCard", "TradeOffValues", "TradeOffCard", "ParetoCard"):
            self.assertNotRegex(BuildTests.studio_function(card), r'\bhere="(?!The size cap)', f"{card} reads its order, leaders or front from the collector, so its ⓘ claims no work of its own")

    @unittest.skipUnless(CHROME, "no Chrome")
    def test_cards_that_compute_say_what_in_their_info_only(self) -> None:
        html = build_studio.build([with_intervals(run_snapshot())])
        got = probed(html, embedded(html)["datasets"][0]["id"], VISIBLE + r"""
          return ['ranked', 'time'].filter(card).map(function (id) { var i = card(id).querySelector('.info'); return [id, card(id).querySelectorAll('.tag.here').length, i ? i.getAttribute('aria-label') : null]; });""")
        self.assertEqual([g[0] for g in got], ["ranked", "time"], "the ranked and version charts draw")
        for cid, tags, info in got:
            with self.subTest(card=cid):
                self.assertEqual(tags, 0)
                self.assertNotIn("worked out on this page", info or "", "the order, Top and new leaders are the collector's")


@unittest.skipUnless(CHROME, "no Chrome")
class EveryCsvTests(unittest.TestCase):
    """Every card's Download > CSV gives a file: a column built from a field that was gone threw a TypeError, with no file and no toast."""

    def test_every_cards_csv_downloads(self) -> None:
        html = build_studio.build([two_targets()])
        press = lambda card, sel: "var c = document.querySelector('[data-card=\"" + card + "\"]'); var b = c && [].filter.call(c.querySelectorAll('button'), " + sel + ")[0]; if (b) b.click(); else window.__errs.push('no button in ' + '" + card + "');"
        capture = ("window.__errs = []; window.addEventListener('error', function (e) { window.__errs.push(e.message); });"
                   "URL.createObjectURL = function (b) { b.text().then(function (t) { window.__last = t; }); return 'about:blank'; };"
                   "HTMLAnchorElement.prototype.click = function () {};")
        for view, card in ((None, "ranked"), (None, "time"), (None, "table"), ("% change", "tradeoff"), ("Values", "tradeoff")):
            with self.subTest(card=card, view=view):
                pick = press(card, "function (b) { return b.textContent.trim() === " + json.dumps(view) + "; }") if view else ""
                act = (capture + pick + " setTimeout(function () { " + press(card, "function (b) { return b.textContent.trim() === 'Download'; }")
                       + " setTimeout(function () { " + press(card, "function (b) { return b.getAttribute('data-dl') === 'csv'; }") + " }, 200); }, 300);")
                got = probed(html, embedded(html)["datasets"][0]["id"], "return { errs: window.__errs, csv: window.__last || '' };", act=act, wait=1500, more=True)
                self.assertEqual(got["errs"], [], card)
                self.assertGreater(len(got["csv"].strip().splitlines()), 1, card)


@unittest.skipUnless(CHROME, "no Chrome")
class BoxFixtureTests(unittest.TestCase):
    def test_a_run_with_five_runs_per_side_draws_falcons_boxes(self) -> None:
        from studio_fixtures import nemo_with_runs
        html = build_studio.build([nemo_with_runs()], only="box")
        got = probed(html, embedded(html)["datasets"][0]["id"], """var c = document.querySelector('[data-card="box"]');
          return { boxes: c.querySelectorAll('svg rect[fill-opacity]').length, means: (c.querySelector('.means') || {}).textContent || '' };""")
        self.assertGreater(got["boxes"], 0, "falcon's quartiles draw boxes")
        self.assertNotIn("No box", got["means"])


@unittest.skipUnless(CHROME, "no Chrome")
class NoArtemisBestTests(unittest.TestCase):
    """Prod's CLI 1.1.18 sends no bestVersion: the page never calls its own pick Best, and says on the page to update the CLI."""

    def test_a_page_with_no_best_from_artemis(self) -> None:
        import collect_discovery
        from studio_fixtures import FIXTURE
        payloads = collect_discovery.load_from_dir(str(FIXTURE))
        del payloads["comparison"]["bestVersion"]  # as CLI 1.1.18 sends it
        snap = collect_discovery.build_snapshot(payloads, collected_at="2026-01-01T00:00:00Z")
        self.assertFalse(snap["provenance"]["bestSent"])
        html = build_studio.build([snap])
        got = probed(html, embedded(html)["datasets"][0]["id"], """return { top: (document.querySelector('.lede-after') || document.body).textContent,
          best: document.querySelector('[data-card="best"]').textContent, info: (document.querySelector('[data-card="best"] .info') || { getAttribute: function () { return ''; } }).getAttribute('aria-label') };""")
        self.assertIn("update it to 1.1.20 or later", got["top"])
        self.assertIn("leads with the Top on", got["top"])
        self.assertNotIn("(Best)", got["best"])
        self.assertIn("(Top on ", got["best"])
        self.assertNotIn("computed here", got["top"] + got["best"], "no label: the ⓘ says where the pick comes from")
        self.assertIn("picked on this page", got["info"])


@unittest.skipUnless(CHROME, "no Chrome")
class CapLabelTests(unittest.TestCase):
    def test_the_size_cap_label_is_never_drawn_hidden(self) -> None:
        # Run A on CLI 1.1.18: with the budget metric on the y axis, "Size cap, ..." was hidden under a point label.
        snap = FailedRowsAndTradeOffTests.budgeted()
        html = build_studio.build([snap], tradeoff="latency_ms,model_size_mb")
        self.assertEqual([p for p in check_report.studio_render_checks(html, CHROME) if "Size cap" in p], [])
        got = probed(html, embedded(html)["datasets"][0]["id"], """var c = document.querySelector('[data-card="tradeoff"]');
          return [].filter.call(c.querySelectorAll('svg text'), function (t) { return /Size cap/.test(t.textContent); }).map(function (t) { return [t.getAttribute('data-optional') || (t.getAttribute('transform') ? 'rotated' : ''), getComputedStyle(t).visibility]; });""")
        self.assertTrue(all(v != "hidden" for _, v in got), got)


if __name__ == "__main__":
    unittest.main()
