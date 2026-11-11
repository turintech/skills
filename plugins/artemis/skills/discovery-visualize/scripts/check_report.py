#!/usr/bin/env python3
"""Check a built report before sharing it.

Static checks always run. With Chrome or Chromium installed, the page is also rendered headlessly and checked
for script errors and unhandled rejections, any request other than Google Fonts, labels drawn outside their
chart, a chart narrower than its card that is not centred in it, empty titles or findings, and the snapshot's
best lines (`bestLines.lede` and each of `bestLines.notes`) missing from the page. Exit status is non-zero
when anything fails.

    python3 check_report.py report.html
    python3 check_report.py --studio studio.html

With --studio it checks a chart studio page from build_studio.py instead, opening every dataset and Discovery
session in turn (a one-card page: only the first, the one it draws) with every section open, then every view
behind a control (each card's segmented buttons, menus and legend entries, and the theme, one at a time; the
Versions, Metrics and Download pop-ups are not walked). It fails on: a dash; script errors or unhandled
rejections; a view other than the one asked for; a card with no chart, table or sentence; a closed section; a
project view without its sessions card; a value label or category name hidden, shortened, cut off or
overlapping another; a sideways scroll with no cue; a page wider than the window; no "Best = ..." line, or a
metric whose own best is not named with its version; and a probe that throws says why (PROBE ERROR). The
studio is set in IBM Plex Sans with tabular figures, no monospace; its PNG and SVG downloads may fetch Google
Fonts to embed them, and nothing else may be fetched apart from the chart libraries' pinned script URLs.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from build_studio import IDENTIFIERS  # names the page matches on keep their dashes, as the builder leaves them

# Browser globals that a top-level `const`/`let` cannot redeclare; doing so stops the whole script.
RESERVED = ("top", "name", "parent", "status", "length", "origin", "self", "frames", "history", "location")

PROBE = """
<script>
// As in the studio probe: measure once the web fonts are in, never in the fallback font's wider widths.
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { setTimeout(function () {
  var out = (window.__AR_ERRORS || []).slice();
  document.querySelectorAll('svg').forEach(function (svg) {
    var vb = svg.viewBox && svg.viewBox.baseVal;
    if (!vb || !vb.width) return;
    svg.querySelectorAll('text').forEach(function (t) {
      if (t.getAttribute('transform')) return;
      var b = t.getBBox();
      if (b.x < -1 || b.x + b.width > vb.width + 1 || b.y < -1 || b.y + b.height > vb.height + 1)
        out.push('OUTSIDE CHART: ' + t.textContent.slice(0, 60));
    });
  });
  (performance.getEntriesByType('resource') || []).forEach(function (r) {
    if (!/^(data:|blob:|https:\\/\\/(fonts\\.googleapis\\.com|fonts\\.gstatic\\.com)\\/)/.test(r.name)) out.push('LIVE FETCH: loaded ' + r.name.slice(0, 80));
  });
  var h1 = document.querySelector('h1');
  if (!h1 || !h1.textContent.trim()) out.push('EMPTY TITLE');
  document.querySelectorAll('section h2').forEach(function (h2) {
    var f = h2.parentElement.querySelector('.ar-finding, .finding');
    if (f && !f.textContent.trim()) out.push('EMPTY FINDING under: ' + h2.textContent.slice(0, 60));
  });
  if (!document.querySelector('svg')) out.push('NO CHART RENDERED');
  // The collector's best lines must reach the page word for word, whatever page script drew it.
  var bl = typeof SNAPSHOT !== 'undefined' && SNAPSHOT && SNAPSHOT.bestLines;
  if (bl) {
    // What a reader can see: the live page's innerText, which leaves out scripts, styles and hidden text.
    var squash = function (x) { return String(x).replace(/\\s+/g, ' ').trim(); };
    var text = squash(document.body.innerText);
    var shown = function (line) {
      // A whole match: "v3 is best on fps" is not satisfied by "v3 is best on fps_p99".
      for (var i = text.indexOf(line); i >= 0; i = text.indexOf(line, i + 1)) if (!/[A-Za-z0-9_]/.test(text.charAt(i + line.length))) return true;
      return false;
    };
    [bl.lede].concat(Object.keys(bl.notes || {}).map(function (k) { return bl.notes[k]; })).forEach(function (line) {
      if (!shown(squash(line))) out.push('MISSING BEST LINE (keep it verbatim): ' + squash(line).slice(0, 90));
    });
  }
  // The collector's stored-direction warnings, word for word, with or without a Best.
  var dc = typeof SNAPSHOT !== 'undefined' && SNAPSHOT && Array.isArray(SNAPSHOT.directionChecks) ? SNAPSHOT.directionChecks : [];
  if (dc.length) {
    var whole = String(document.body.innerText).replace(/\\s+/g, ' ');
    dc.forEach(function (line) { var l = String(line).replace(/\\s+/g, ' ').trim(); if (whole.indexOf(l) < 0) out.push('MISSING DIRECTION CHECK (keep it verbatim): ' + l.slice(0, 90)); });
  }
  // A chart narrower than its card sits in the middle of it, not pinned to the left.
  document.querySelectorAll('.ar-chart svg').forEach(function (svg) {
    var box = svg.parentElement.getBoundingClientRect(), r = svg.getBoundingClientRect();
    if (r.width < box.width - 2 && Math.abs((r.left + r.width / 2) - (box.left + box.width / 2)) > 3)
      out.push('OFF-CENTRE CHART: ' + (svg.getAttribute('aria-label') || '').slice(0, 60));
  });
  var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = out.join('\\n') || 'OK';
  document.body.appendChild(d);
}, 1200); });
</script>
"""
STUDIO_PROBE = """
<script>
// Measure only once the web fonts are in: labels laid out in the fallback font are wider, and the page lays them out
// again when the fonts arrive (document.fonts.ready), so measuring before that reported overlaps that never show.
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { setTimeout(function () {
  var out = [], view = (window.__STUDIO_VIEW || '') + (window.innerWidth < 500 ? ', ' + window.innerWidth + 'px' : '');
  var say = function (m) { out.push(m + (view ? ' [' + view + ']' : '')); };
  // A throw in this probe still reports, with its cause, and never passes for a clean page.
  var bail = function (e) { say('PROBE ERROR: ' + e.message + ' ' + String(e.stack || '').split('\\n').slice(1, 2).join('').trim()); var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = out.join('\\n'); document.body.appendChild(d); };
  try {
  (window.__AR_ERRORS || []).forEach(say);
  // The page must draw the view the checker asked for, or that view was never checked.
  var asked = window.__STUDIO_START, drew = window.STUDIO_VIEW_DRAWN;
  if (asked && !drew) say('WRONG VIEW: the page did not report the view it drew');
  if (asked && drew && (asked.dataset !== drew.dataset || (asked.session || 0) !== drew.session)) say('WRONG VIEW: asked ' + asked.dataset + ' s' + ((asked.session || 0) + 1) + ', drew ' + drew.dataset + ' s' + (drew.session + 1));
  // Every resource the page loaded, however it asked: only the template's pinned chart libraries and the fonts.
  var pinned = __STUDIO_SCRIPTS__;
  var loaded = {}, resources = function (when) {  // every resource the page has loaded so far, each named once
    (performance.getEntriesByType('resource') || []).forEach(function (r) {
      if (loaded[r.name]) return; loaded[r.name] = 1;
      if (pinned.indexOf(r.name) < 0 && !/^(data:|blob:|https:\\/\\/(fonts\\.googleapis\\.com|fonts\\.gstatic\\.com)\\/)/.test(r.name)) say('LIVE FETCH: loaded ' + r.name.slice(0, 80) + (when ? ' (after ' + when + ')' : ''));
    });
  };
  resources('');
  var root = document.getElementById('root');
  if (root && /chart libraries did not load/.test(root.textContent)) say('RENDER: the chart libraries did not load; check the network and run again');
  // The page's own failure messages (it did not load, failed to start, has no such chart) say the cause; pass it on.
  else if (root) [].forEach.call(root.querySelectorAll(':scope > .err, .page > .err'), function (e) { say('RENDER: ' + e.textContent.trim().slice(0, 120)); });
  // A one-card page (build_studio.py --only) has no h1: its card's heading is the title.
  var h1 = document.querySelector('h1') || (window.STUDIO_ONLY ? document.querySelector('section.card h2') : null);
  if (!h1 || !h1.textContent.trim()) say('EMPTY TITLE');
  // Nothing drawn anywhere, and no card saying why (a one-card forest with no intervals yet says so, and passes).
  var explained = [].some.call(document.querySelectorAll('.plot .sparse, .plot .missing'), function (e) { return e.textContent.trim(); });
  if (!document.querySelector('.recharts-surface, table.sum') && !explained) say('NO CHART RENDERED');  // the summary card is a table
  if (window.STUDIO_MULTI && !window.STUDIO_ONLY && !document.querySelector('[data-card="sessions"]')) say('NO SESSIONS CARD: a project view must draw its sessions card');
  // Every card the page meant to draw is on the page (a card that renders nothing at all is gone without an error).
  (window.STUDIO_CARDS || []).forEach(function (id) { if (!document.querySelector('[data-card="' + id + '"]')) say('MISSING CARD: ' + id); });
  // The checks each card must pass in every view: something drawn, and no part hidden behind a sideways scroll.
  var cardSeen = {}, cardChecks = function (when) {
    var tail = when ? ' (after ' + when + ')' : '', once = function (msg) { if (cardSeen[msg]) return; cardSeen[msg] = 1; say(msg + tail); };  // each problem once, at the first view it shows in
    // Every card draws something: a chart, its table, or a sentence saying why it has nothing (one empty card fails on its own).
    [].forEach.call(document.querySelectorAll('section.card'), function (card) {
      var plot = card.querySelector('.plot');
      var said = [].some.call(plot ? plot.querySelectorAll('.sparse, .missing, .err') : [], function (e) { return e.textContent.trim(); });
      if (plot && !plot.querySelector('.recharts-surface, table') && !said) { var t = card.querySelector('h2'); once('EMPTY CARD: ' + (t ? t.textContent.trim().slice(0, 60) : 'a card')); }
    });
    // A value the page could not format: "undefined", "NaN" or "null" where the page writes its own words and numbers
    // (the headline, panel lines, numbers, chart labels), never in collected text such as an experiment title.
    // An en or em dash a reader can see (a metric key drawn as its name, say): the page uses commas, colons and "to".
    if (/[\u2013\u2014]/.test(document.body.innerText)) { var dm = /.{0,30}[\u2013\u2014].{0,30}/.exec(document.body.innerText); once('DASH ON PAGE: "' + (dm ? dm[0] : '') + '"'); }
    var own = function (e) { var c = e.cloneNode(true); [].forEach.call(c.querySelectorAll('.data'), function (d) { d.remove(); }); return c.textContent; };  // collected text (titles, steers) is marked .data
    [].forEach.call(document.querySelectorAll('h1, .psub, .val, .num, td.n, svg text, .means li, .means p, p.missing, p.warn, p.lede'), function (e) {
      var s = own(e), b = /(^|[^A-Za-z])(undefined|NaN|null)([^A-Za-z]|$)/.exec(s);
      if (b && getComputedStyle(e).visibility !== 'hidden') once('BROKEN VALUE: "' + s.trim().slice(0, 70) + '"');
    });
    // A chart or table wider than its card hides part of itself; it must say so ("Swipe ...") or fit.
    [].forEach.call(document.querySelectorAll('.plot'), function (p) {
      if (p.scrollWidth > p.clientWidth + 1 && !p.querySelector('.hint')) { var c = p.closest('.card'), t = c && c.querySelector('h2'); once('HIDDEN BEHIND A SIDEWAYS SCROLL, NO CUE: ' + (t ? t.textContent.trim().slice(0, 60) : 'a chart') + ' (' + p.scrollWidth + 'px in ' + p.clientWidth + 'px)'); }
    });
  };
  cardChecks('');
  // A section left closed was never drawn, so nothing in it was checked; the studio opens each one for the checker.
  [].forEach.call(document.querySelectorAll('details:not([open])'), function (d) { say('CLOSED SECTION, NOT CHECKED: ' + (d.querySelector('summary') || d).textContent.trim().slice(0, 60)); });
  if (document.documentElement.scrollWidth > window.innerWidth + 1) say('PAGE WIDER THAN THE WINDOW: ' + document.documentElement.scrollWidth + 'px');
  // Every label drawn inside a chart: none may overlap another or be cut by the chart's edge or its clip area.
  var said = {};
  var labels = function (when) {
    [].forEach.call(document.querySelectorAll('svg.recharts-surface'), function (svg) {
      var box = svg.getBoundingClientRect(), card = svg.closest('.card'), h = card && card.querySelector('h2');
      var name = (h ? h.textContent.trim() : 'a chart').slice(0, 50);
      var texts = [].filter.call(svg.querySelectorAll('text'), function (t) { var r = t.getBoundingClientRect(); return r.width > 1 && r.height > 1 && t.textContent.trim() && getComputedStyle(t).visibility !== 'hidden'; });
      var rects = texts.map(function (t) { return t.getBoundingClientRect(); });
      var clipOf = function (el) {
        for (var e = el; e && e !== svg; e = e.parentNode) {
          var c = e.getAttribute && e.getAttribute('clip-path'), m = c && /url\\(#([^)]+)\\)/.exec(c), cp = m && document.getElementById(m[1]), r = cp && cp.querySelector('rect');
          if (r) { var x = +r.getAttribute('x'), y = +r.getAttribute('y'); return { left: box.left + x, top: box.top + y, right: box.left + x + +r.getAttribute('width'), bottom: box.top + y + +r.getAttribute('height') }; }
        }
        return null;
      };
      var report = function (msg) { var k = msg + ' in ' + name; if (said[k]) return; said[k] = 1; say(k + (when ? ' (after ' + when + ')' : '')); };
      // A value or name label the layout pass hid is lost on screen and in the PNG and SVG; only axis ticks may give way.
      // A label the layout pass cut short has lost its value; only an axis title may be shortened (the Metric menu has it whole).
      [].forEach.call(svg.querySelectorAll('text[data-short]'), function (t) { if (!t.getAttribute('transform') && !(t.classList.contains('recharts-label') && !t.closest('.recharts-label-list')) && t.dataset.short === t.textContent) report('LABEL SHORTENED: "' + (t.dataset.full || '').slice(0, 30) + '" shows as "' + t.textContent.slice(0, 30) + '"'); });
      // A name on a bar chart's category axis is data too: a number tick may give way, a version or session name may not.
      [].forEach.call(svg.querySelectorAll('text'), function (t) {
        var s = t.textContent.trim(); if (!s || getComputedStyle(t).visibility !== 'hidden') return;
        if (!t.closest('.recharts-cartesian-axis-tick-labels')) report('LABEL HIDDEN: "' + s.slice(0, 30) + '"');
        else if (!/^[+\\u2212-]?[\\d.,]+\\s*(%|\\u00d7|[a-z\\u00b5]{1,3})?$/i.test(s) && !(t.closest('.recharts-xAxis-tick-labels') && /^v\\d+$/.test(s)) && s !== 'original') report('NAME HIDDEN: "' + s.slice(0, 30) + '"');  // a number, or a vN tick on an x axis of versions in order, may give way
      });
      texts.forEach(function (t, i) {
        var r = rects[i], lim = clipOf(t) || box, label = t.textContent.trim().slice(0, 30);
        if (r.left < lim.left - 1 || r.right > lim.right + 1 || r.top < lim.top - 1 || r.bottom > lim.bottom + 1) report('LABEL CUT OFF: "' + label + '"');
        for (var j = i + 1; j < texts.length; j++) {
          var q = rects[j];
          if (texts[j].contains(t) || t.contains(texts[j])) continue;
          var ox = Math.min(r.right, q.right) - Math.max(r.left, q.left), oy = Math.min(r.bottom, q.bottom) - Math.max(r.top, q.top);
          if (ox > 2 && oy > 2) report('LABELS OVERLAP: "' + label + '" and "' + texts[j].textContent.trim().slice(0, 30) + '"');
        }
      });
    });
  };
  labels('');
  var bl = window.SNAPSHOT && window.SNAPSHOT.bestLines;
  if (window.SNAPSHOT && !('bestLines' in window.SNAPSHOT)) say('NO BEST LINES: the snapshot has no bestLines key, so the Best checks did not run; collect it again');
  if (bl) {
    var squash = function (x) { return String(x).replace(/\\s+/g, ' ').trim(); };
    var text = squash(document.body.innerText);
    var shown = function (line) {
      for (var i = text.indexOf(line); i >= 0; i = text.indexOf(line, i + 1)) if (!/[A-Za-z0-9_]/.test(text.charAt(i + line.length))) return true;
      return false;
    };
    // The studio says how Best was chosen in one line ("Best = ..."), and names each metric whose own best is another
    // version: the version and the metric (its key or the name the page shows) in one line. Other notes verbatim.
    if (!/Best = /.test(text)) say('MISSING BEST RULE: say in one line how Best was chosen ("Best = ...")');
    var lines = [].map.call(document.querySelectorAll('h1, li, p'), function (e) { return squash(e.textContent); }), names = window.STUDIO_LABELS || {};
    var swapDash = function (x) { return String(x).replace(/^\\s*[\u2013\u2014]\\s*|\\s*[\u2013\u2014]\\s*$/g, '').replace(/(\\w*\\d)\\s*\u2013\\s*(?=[\u2013\u2212-]?\\w*\\d)/g, '$1 to ').replace(/\\s*[\u2013\u2014]\\s*/g, ', '); };
    var esc = function (x) { return x.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); };
    Object.keys(bl.notes || {}).forEach(function (k) {
      var kk = swapDash(k);  // the builder swaps a dash in the note's text, never in the key
      var note = squash(bl.notes[k]), m = /^(\\S+) is best on (.+)$/.exec(note), v = m && new RegExp('(^|[^A-Za-z0-9_])' + esc(m[1]) + '([^A-Za-z0-9_]|$)');
      var pair = m && new RegExp('(^|[^A-Za-z0-9_])' + esc(m[1]) + ' (?:on|does best on|is fastest on) (' + esc(k) + '|' + esc(kk) + (names[k] ? '|' + esc(names[k]) : '') + ')(?=$|[,.;:)]| alone)');
      var ok = m && (m[2] === k || m[2] === kk) ? lines.some(function (l) { return pair.test(l); }) : shown(note);
      if (!ok) say('MISSING BEST NOTE: ' + note.slice(0, 90));
    });
  }
  // The collector's stored-direction warnings ("x is set as higher-is-better on this project; check Settings > Metrics"),
  // whatever the Best state: the snapshot's own list, else bestLines.checks, else the lede's sentences (an older snapshot).
  var snap = window.SNAPSHOT || {}, bl2 = snap.bestLines || null;
  var checks = Array.isArray(snap.directionChecks) ? snap.directionChecks : bl2 ? (bl2.checks || (String(bl2.lede || '').match(/[^.]*? is set as (?:higher|lower)-is-better on this project; check Settings > Metrics\\./g) || [])) : [];
  if (checks.length) {
    var whole = document.body.innerText.replace(/\\s+/g, ' ');
    checks.forEach(function (line) { var l = String(line).replace(/\\s+/g, ' ').trim(); if (whole.indexOf(l) < 0) say('MISSING DIRECTION CHECK (keep it verbatim): ' + l.slice(0, 90)); });
  }
  // What the user and the collector said about this view reaches the page: each correctness mark (with the word), each
  // run left out, and the values Artemis sent as NaN.
  var seen2 = String(document.body.innerText);
  (window.STUDIO_FAILED || []).forEach(function (n) {
    var said = seen2.split('\\n').some(function (l) { return /correctness check/.test(l) && new RegExp('(^|[^A-Za-z0-9])v' + n + '([^0-9]|$)').test(l); });
    if (!said) say('MISSING CORRECTNESS MARK: v' + n + ' failed the user check, and the page does not say so');
  });
  (window.STUDIO_LEFT_OUT || []).forEach(function (r) { var name = r.id ? 'run ' + String(r.id).slice(0, 8) : 'a run with no id'; if (seen2.indexOf(name + ' (' + r.reason) < 0) say('MISSING LEFT-OUT RUN: ' + name); });
  ((window.SNAPSHOT || {}).nonFinite || []).slice(0, 3).forEach(function (n) { if (seen2.indexOf(n) < 0) say('MISSING NON-FINITE NOTE: ' + n); });
  // Then every view behind a control: each card's buttons, menus and legend entries, and the theme, one at a time
  // from the default and back, so a mode that only breaks when chosen is drawn too. Bounded, never recursive.
  var seen = (window.__AR_ERRORS || []).length, steps = [], MAX = 400;
  var cards = function () { return document.querySelectorAll('.card'); };
  var nameOf = function (card, ci) { var t = card.querySelector('h2'); return (t ? t.textContent : 'card ' + (ci + 1)).trim().slice(0, 50); };
  var pressedIn = function (group) { return [].map.call(group.querySelectorAll('button'), function (b) { return b.getAttribute('aria-pressed') === 'true'; }).indexOf(true); };
  var segSteps = function (group0, find, label, owner) {
    var orig = pressedIn(group0);
    if (orig < 0) { say('WALK: no button is pressed in ' + label + ', so its views were not walked from a default'); return; }
    [].forEach.call(group0.querySelectorAll('button'), function (b, bi) {
      if (b.disabled || bi === orig) return;
      steps.push({ desc: label + ' > ' + b.textContent.trim(), card: owner, go: function () {
        var g = find(), x = g && g.querySelectorAll('button')[bi];
        if (!x) return null;  // the card already failed and shows its message; that error is reported
        x.click();
        return function () { var g = find(); if (g && orig >= 0 && g.querySelectorAll('button')[orig]) g.querySelectorAll('button')[orig].click(); };
      } });
    });
  };
  [].forEach.call(cards(), function (card, ci) {
    var name = nameOf(card, ci), at = function () { return cards()[ci]; };
    [].forEach.call(card.querySelectorAll('.seg'), function (seg, gi) { segSteps(seg, function () { return at() && at().querySelectorAll('.seg')[gi]; }, name, at); });
    [].forEach.call(card.querySelectorAll('select'), function (sel, si) {
      var orig = sel.value;
      [].forEach.call(sel.options, function (o) {
        if (o.value === orig) return;
        steps.push({ desc: name + ' > ' + o.textContent.trim(), card: at, go: function () {
          var set = function (v) { var s = at() && at().querySelectorAll('select')[si]; if (s) { s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); } return !!s; };
          if (!set(o.value)) return null;
          return function () { set(orig); };
        } });
      });
    });
    [].forEach.call(card.querySelectorAll('.legend button'), function (b, li) {
      steps.push({ desc: name + ' > legend ' + b.textContent.trim(), card: at, go: function () {
        var click = function () { var x = at() && at().querySelectorAll('.legend button')[li]; if (x) x.click(); return !!x; };
        if (!click()) return null;
        return click;
      } });
    });
  });
  var theme = document.querySelector('.bar .seg[aria-label="Theme"]');
  if (theme) segSteps(theme, function () { return document.querySelector('.bar .seg[aria-label="Theme"]'); }, 'Theme');
  if (steps.length > MAX) say('WALK CUT SHORT: ' + steps.length + ' views behind controls, only the first ' + MAX + ' were drawn');
  steps = steps.slice(0, MAX);
  var i = 0, wideSaid = 0;
  var finish = function () {
    var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = out.join('\\n') || 'OK';
    document.body.appendChild(d);
  };
  var next = function () {
    if (i >= steps.length) return finish();
    var st = steps[i++], undo = null;
    // A card that already failed shows its own message, which is reported once; its other views are not walked again.
    var owner = st.card && st.card();
    if (owner && owner.querySelector('.err')) return setTimeout(next, 0);
    var before = (window.__AR_ERRORS || []).length;
    try { undo = st.go(); if (undo === null && (window.__AR_ERRORS || []).length === before) say('WALK: the control for ' + st.desc + ' was gone, so that view was not drawn'); } catch (e) { say('WALK: could not open ' + st.desc + ': ' + e.message); }
    setTimeout(function () {
      var errs = window.__AR_ERRORS || [];
      for (; seen < errs.length; seen++) say(errs[seen] + ' (after ' + st.desc + ')');
      if (document.documentElement.scrollWidth > window.innerWidth + 1 && !wideSaid) { wideSaid = 1; say('PAGE WIDER THAN THE WINDOW after ' + st.desc + ': ' + document.documentElement.scrollWidth + 'px'); }  // once
      try { labels(st.desc); cardChecks(st.desc); resources(st.desc); } catch (e) { return bail(e); }
      try { if (undo) undo(); } catch (e) { say('WALK: could not undo ' + st.desc + ': ' + e.message); }
      setTimeout(next, 150);
    }, 250);
  };
  next();
  } catch (e) { bail(e); }
}, 2500); });
</script>
"""
CATCHER = ('<script>window.__AR_ERRORS=[];window.addEventListener("error",function(e){window.__AR_ERRORS.push("SCRIPT ERROR: "+e.message+" (line "+e.lineno+")")});'
           'window.addEventListener("unhandledrejection",function(e){var r=e.reason;window.__AR_ERRORS.push("UNHANDLED REJECTION: "+(r&&r.message?r.message:String(r)))});</script>')
# Any request the page makes at run time, however it is spelled, other than the fonts it may embed.
NETWORK_TRAP = """<script>(function () {
  var ok = /^(data:|blob:|https:\\/\\/fonts\\.(googleapis|gstatic)\\.com\\/)/;
  var log = function (how, url) { url = String(url && url.url || url); if (!ok.test(url)) window.__AR_ERRORS.push('LIVE FETCH: ' + how + ' ' + url.slice(0, 80)); };
  var f = window.fetch; if (f) window.fetch = function (u) { log('fetch', u); return f.apply(this, arguments); };
  var o = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function (m, u) { log('XMLHttpRequest', u); return o.apply(this, arguments); };
  if (navigator.sendBeacon) { var b = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = function (u) { log('sendBeacon', u); return b.apply(null, arguments); }; }
  ['WebSocket', 'EventSource'].forEach(function (k) { var C = window[k]; if (C) window[k] = function (u) { log(k, u); return new C(u); }; });
})();</script>"""


def static_checks(html: str) -> list[str]:
    problems = []
    if re.search(r"[–—]|&(ndash|mdash|#8211|#8212);", html):
        problems.append("DASH: an en or em dash is in the page; use a comma, colon or 'to'")
    for name in RESERVED:
        if re.search(rf"^\s*(const|let)\s+{name}\s*=", html, re.M):
            problems.append(f"RESERVED NAME: a top-level `{name}` clashes with a browser global and stops the script")
    if re.search(r"monospace|\bPlex Mono\b", html, re.I):
        problems.append("MONOSPACE: the report uses one sans family with tabular figures, no monospace")
    if re.search(r"\bfetch\s*\(|XMLHttpRequest", html):
        problems.append("LIVE FETCH: the page must embed its data, not fetch it")
    if "<title>" not in html[:8192]:
        problems.append("NO <title> in the first 8KB")
    return problems


# The chart libraries the studio template pins, exactly; a new one is a change to review here too.
STUDIO_SCRIPTS = (
    "https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/react-is/18.3.1/umd/react-is.production.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/recharts/3.10.1/Recharts.min.js",
    "https://unpkg.com/htm@3.1.1/dist/htm.umd.js",
)


def studio_probe() -> str:
    return STUDIO_PROBE.replace("__STUDIO_SCRIPTS__", json.dumps(list(STUDIO_SCRIPTS)))


def studio_static_checks(html: str) -> list[str]:
    # A dash in the collected data (an AI-written experiment title, say) is named by its field; the builder swaps them.
    data = re.search(r'(<script type="application/json" id="studio-data">)(.*?)(</script>)', html, re.S)
    page = html[:data.start(2)] + html[data.end(2):] if data else html
    problems = [p for p in static_checks(page) if not p.startswith("LIVE FETCH")]
    if data and dashed_text(data.group(2)):
        problems.append(f"DASH IN DATA: an en or em dash in {dashed_text(data.group(2))}; rebuild with build_studio.py, which swaps them")
    if "XMLHttpRequest" in page:  # the template, not the collected data: a run about fetch() is not a fetch
        problems.append("LIVE FETCH: the page must embed its data, not fetch it")
    start, end = page.find("function exportFonts()"), page.find("function withFonts(")
    if start < 0 or end <= start:
        problems.append("LIVE FETCH: the font loader is not where the check expects (exportFonts before withFonts)")
    for match in re.finditer(r"\bfetch\s*\(\s*", page):
        arg = page[match.end():match.end() + 40]
        fonts = arg.startswith('"https://fonts.googleapis.com/') or (arg.startswith("url)") and 0 <= start < match.start() < end)
        if not fonts:
            problems.append("LIVE FETCH: only the SVG download's Google Fonts may be fetched; embed the data")
    if "__STUDIO_DATA__" in html or "__TITLE__" in html:
        problems.append("NOT BUILT: run build_studio.py; the template's placeholders are still in the page")
    else:
        try:
            if not studio_views(html):
                problems.append("NO DATA: the page holds no snapshot to draw")
        except ValueError as error:
            problems.append(f"NO DATA: {error}")
    return problems


def dashed_text(raw: str) -> str | None:
    """The first text field of the embedded data with an en or em dash in it, by name; None if there is none."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None  # NO DATA says why
    def walk(value, field):
        if isinstance(value, str):
            return field if not IDENTIFIERS.search(field) and re.search("[\u2013\u2014]", value) else None
        items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
        return next((hit for k, v in items if (hit := walk(v, k if isinstance(k, str) else field))), None)
    return walk(data, "")


def _not_json(name: str) -> None:
    raise ValueError(f"{name} is not JSON, so the browser cannot read it")


def studio_views(html: str) -> list[tuple[str, int]]:
    """Every (dataset id, session index) the studio can show; ValueError says why the data is unreadable."""
    match = re.search(r'<script type="application/json" id="studio-data">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("no studio-data block in the page")
    try:
        # Parsed as the browser's JSON.parse sees it: build_studio.py writes "<" as \u003c, which is valid JSON.
        data = json.loads(match.group(1), parse_constant=_not_json)
    except ValueError as error:
        raise ValueError(f"studio-data does not parse: {error}") from None
    views = []
    for n, ds in enumerate(data.get("datasets") or [] if isinstance(data, dict) else [], 1):
        if not isinstance(ds, dict) or not ds.get("id"):
            raise ValueError(f"dataset {n} in studio-data has no id")
        views += [(ds["id"], i) for i in range(len(ds.get("sessions") or [None]))]
    # A one-card page (build_studio.py --only) draws only the first snapshot's first session, so that is all it shows.
    return views[:1] if isinstance(data, dict) and data.get("only") else views


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def chrome_env(tmp: str | Path) -> dict[str, str]:
    """Chrome's environment with TMPDIR inside a run's own temporary folder: each launch leaves copies of its built-in
    extensions in TMPDIR, so they go when the folder does, never piling up in /tmp."""
    return {**os.environ, "TMPDIR": str(tmp)}


def probe_page(page_html: str, chrome: str, budget: int, where: str) -> list[str]:
    """Render one page headlessly and return its probe's lines; a crash or timeout is a RENDER line with the detail."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "probe.html"
        try:
            page.write_text(page_html, encoding="utf-8")
            result = subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={Path(tmp) / 'profile'}",
                 "--window-size=1000,900", f"--virtual-time-budget={budget}", "--dump-dom", page.as_uri()],
                env=chrome_env(tmp), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
            )
        except subprocess.TimeoutExpired:
            return [f"RENDER: the page timed out after 120 s {where}"]
        except OSError as error:  # a full disk, or a Chrome that will not start
            return [f"RENDER: could not run Chrome {where}: {error}"]
    match = re.search(r'<pre id="__ar_probe">(.*?)</pre>', result.stdout, re.S)
    if not match:
        # The cause, when there is one: the page's own failure message in the dumped page, else Chrome's last words.
        said = re.search(r'class="err">([^<]{1,160})<', result.stdout)
        tail = result.stderr.strip()[-200:]
        detail = f": the page says {said.group(1).strip()!r}" if said else f" (Chrome exit {result.returncode}: {tail})" if result.returncode or tail else ""
        return [f"RENDER: the page did not finish rendering {where}{detail}"]
    text = html_lib.unescape(match.group(1)).strip()  # once, so a probe line about "&lt;b&gt;" keeps its text
    return [] if text == "OK" else text.splitlines()


def with_probe(html: str, before: str, probe: str) -> str:
    """The catcher and traps go first, after any doctype, so the page stays in standards mode."""
    doctype = re.match(r"\s*<!doctype html>\s*", html, re.I)
    head = doctype.group(0) if doctype else ""
    return head + CATCHER + NETWORK_TRAP + before + html[len(head):] + probe


def render_checks(html: str, chrome: str, before: str = "", probe: str = PROBE, budget: int = 4000) -> list[str]:
    return probe_page(with_probe(html, before, probe), chrome, budget, "in headless Chrome")


def studio_render_checks(html: str, chrome: str) -> list[str]:
    problems = []
    try:
        views = studio_views(html)
    except ValueError:
        return []  # the static checks already say why
    for dataset, session in views:
        # "<" escaped so an id can never close the script element it sits in.
        # "more": open "More charts" too, so every card is drawn.
        start = json.dumps({"dataset": dataset, "session": session, "more": True}).replace("<", "\\u003c")
        view = json.dumps(f"{dataset}, session {session + 1}").replace("<", "\\u003c")
        before = f"<script>window.__STUDIO_START={start};window.__STUDIO_VIEW={view};</script>"
        problems += render_checks(html, chrome, before, studio_probe(), 200000)
        problems += phone_checks(html, chrome, before)
    return problems


PHONE = """<!doctype html><body style="margin:0"><iframe id="f" style="width:390px;height:900px;border:0"></iframe>
<script>
var f = document.getElementById('f');
f.srcdoc = __PAGE__;
var tries = 0, wait = setInterval(function () {
  var p = f.contentDocument && f.contentDocument.getElementById('__ar_probe');
  if (!p && ++tries < 2000) return;  // 200 s: the probe's longest walk (400 steps at 400 ms, after 2.5 s) fits
  clearInterval(wait);
  var d = document.createElement('pre'); d.id = '__ar_probe'; d.textContent = p ? p.textContent : 'RENDER: the page did not finish rendering at 390px';
  document.body.appendChild(d);
}, 100);
</script>"""


def phone_checks(html: str, chrome: str, before: str) -> list[str]:
    """The same probe in a 390px frame, as on a phone; headless Chrome will not open a window under 500px."""
    # "<" as \u003c keeps the page's own </script> and <!-- from ending this script.
    outer = PHONE.replace("__PAGE__", json.dumps(with_probe(html, before, studio_probe())).replace("<", "\\u003c"))
    return probe_page(outer, chrome, 200000, "at 390px")


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    studio = "--studio" in args
    if studio:
        args.remove("--studio")
    if len(args) != 1:
        print("usage: check_report.py [--studio] page.html", file=sys.stderr)
        return 2
    try:
        html = Path(args[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"check_report.py: {error}", file=sys.stderr)
        return 2
    problems = studio_static_checks(html) if studio else static_checks(html)
    chrome = find_chrome()
    if chrome:
        problems += studio_render_checks(html, chrome) if studio else render_checks(html, chrome)
    elif studio:
        # The studio's checks are mostly rendered ones, so a static pass alone is not a pass.
        problems.append("NOT RENDERED: no Chrome or Chromium found, so only the static checks ran; install one and run again")
    else:
        print("note: no Chrome or Chromium found, so only static checks ran; open the page and look at it")
    for p in problems:
        print("FAIL", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
