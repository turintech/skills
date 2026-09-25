/*
 * Artemis Discovery report kit. Inline this file into a report page (build_report.py does it).
 * One global, ArtemisReport. Every chart draws SVG from data you pass in; nothing is fetched.
 * Colours come from the page's CSS tokens, so light and dark themes both work.
 */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';

  // ---------- DOM and formatting helpers ----------
  function h(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function s(parent, tag, attrs, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    parent.append(e);
    return e;
  }
  const fmt = {
    num: (x, d = 2) => (x == null ? '' : Number(x).toFixed(d)),
    pct: (x, d = 1) => (x == null ? '' : (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(d) + '%'),
    times: (x, d = 2) => (x == null ? '' : Number(x).toFixed(d) + '×'),
    share: (x, d = 1) => (x == null ? '' : (x * 100).toFixed(d) + '%'),
    short: (text, max = 36) => (!text || text.length <= max ? text || '' : text.slice(0, max - 2).replace(/\s+\S*$/, '') + '…'),
  };

  // Quartiles by linear interpolation between order statistics (the usual "type 7").
  function stats(values) {
    const x = (values || []).filter(v => v != null && isFinite(v)).slice().sort((a, b) => a - b);
    if (!x.length) return null;
    const q = p => { const i = (x.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i); return x[lo] + (x[hi] - x[lo]) * (i - lo); };
    return { n: x.length, min: x[0], q1: q(0.25), med: q(0.5), q3: q(0.75), max: x[x.length - 1], mean: x.reduce((a, b) => a + b, 0) / x.length };
  }

  // Text width in px, so label gutters fit the labels instead of a guess.
  const ctx = document.createElement('canvas').getContext('2d');
  function textWidth(text, font) { ctx.font = font; return ctx.measureText(text || '').width; }
  const FONT = { lab: '600 13px "IBM Plex Sans", system-ui, sans-serif', sub: '400 11.5px "IBM Plex Sans", system-ui, sans-serif', val: '600 12px "IBM Plex Mono", monospace' };

  // One tooltip for the page.
  let tipEl = null;
  function tip(node, lines) {
    if (!lines || !lines.length) return;
    node.addEventListener('pointermove', e => {
      if (!tipEl) { tipEl = h('div', 'ar-tip'); tipEl.hidden = true; document.body.append(tipEl); }
      tipEl.textContent = '';
      lines.forEach((l, i) => { if (i) tipEl.append(h('br')); tipEl.append(String(l)); });
      tipEl.hidden = false;
      tipEl.style.left = Math.min(e.clientX + 14, window.innerWidth - 330) + 'px';
      tipEl.style.top = (e.clientY + 14) + 'px';
    });
    node.addEventListener('pointerleave', () => { if (tipEl) tipEl.hidden = true; });
  }

  function niceStep(span, target = 6) {
    const raw = span / target, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
  }
  function decimals(step) { return Math.max(0, -Math.floor(Math.log10(step) + 1e-9)); }
  function svgRoot(el, W, H, label) { return s(el, 'svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label || '' }); }
  function gutter(rows) {
    return Math.ceil(Math.max(60, ...rows.map(r => Math.max(textWidth(r.label, FONT.lab), textWidth(r.sub || '', FONT.sub)))) + 24);
  }
  // A linear x scale over one or more domains; with two, the axis is visibly broken between them.
  function xScale(domains, x0, x1, gap = 34) {
    const spans = domains.map(d => d[1] - d[0]), total = spans.reduce((a, b) => a + b, 0);
    const width = x1 - x0 - gap * (domains.length - 1);
    let cursor = x0;
    const segs = domains.map((d, i) => { const w = width * spans[i] / total, seg = { lo: d[0], hi: d[1], a: cursor, b: cursor + w }; cursor += w + gap; return seg; });
    const f = v => { const g = segs.find(q => v >= q.lo - 1e-12 && v <= q.hi + 1e-12) || (v < segs[0].lo ? segs[0] : segs[segs.length - 1]); return g.a + (v - g.lo) / (g.hi - g.lo) * (g.b - g.a); };
    f.segs = segs;
    return f;
  }
  function drawXAxis(svg, x, y0, y1, opts) {
    for (const g of x.segs) {
      const step = opts.step || niceStep(g.hi - g.lo, Math.max(3, Math.round(6 * (g.b - g.a) / 600))), dp = opts.decimals != null ? opts.decimals : decimals(step);
      for (let t = Math.ceil(g.lo / step - 1e-9) * step; t <= g.hi + 1e-9; t += step) {
        s(svg, 'line', { x1: x(t), x2: x(t), y1: y0, y2: y1, class: 'ar-grid' });
        s(svg, 'text', { x: x(t), y: y1 + 16, 'text-anchor': 'middle', class: 'ar-ax' }, opts.tickFormat ? opts.tickFormat(t) : t.toFixed(dp));
      }
    }
    x.segs.slice(1).forEach(g => { const bx = g.a - 17; s(svg, 'path', { d: `M${bx - 6} ${y1 + 5} l5 -9 M${bx + 1} ${y1 + 5} l5 -9`, class: 'ar-break' }); });
  }
  function refLine(svg, x, r, y0, y1) {
    s(svg, 'line', { x1: x(r.value), x2: x(r.value), y1: y0 - 6, y2: y1, class: r.strong ? 'ar-ref strong' : 'ar-ref' });
    if (r.label) s(svg, 'text', { x: x(r.value) + 5, y: y0 - 10, class: r.strong ? 'ar-reflab strong' : 'ar-reflab' }, r.label);
  }

  // ---------- Page pieces ----------
  /* header(el, { eyebrow, title: string | [string | {em}], lede, prov: [string], link: {href, label} }) */
  function header(el, o) {
    if (o.eyebrow) el.append(h('div', 'ar-eyebrow', o.eyebrow));
    const t = h('h1');
    (Array.isArray(o.title) ? o.title : [o.title]).forEach(p => t.append(typeof p === 'string' ? p : h('em', '', p.em)));
    el.append(t);
    if (o.lede) el.append(h('p', 'ar-lede', o.lede));
    const pv = h('div', 'ar-prov');
    (o.prov || []).forEach(x => pv.append(h('span', '', x)));
    if (o.link) { const a = h('a', 'ar-open', o.link.label || 'Open in Artemis'); a.href = o.link.href; a.target = '_blank'; a.rel = 'noreferrer'; pv.append(a); }
    el.append(pv);
  }

  /* headline(el, { left: {k, v, unit, n}, mid: {big, small}, right: {k, v, unit, n} }) */
  function headline(el, o) {
    el.classList.add('ar-headline');
    const side = (d, right) => {
      const b = h('div', 'ar-hs' + (right ? ' r' : ''));
      b.append(h('span', 'ar-k', d.k));
      const v = h('span', 'ar-v' + (right ? ' hero' : ''), d.v);
      if (d.unit) v.append(h('small', '', d.unit));
      b.append(v);
      if (d.n) b.append(h('span', 'ar-n', d.n));
      return b;
    };
    const m = h('div', 'ar-mid');
    m.append(h('b', '', o.mid.big));
    m.insertAdjacentHTML('beforeend', '<svg viewBox="0 0 120 16" aria-hidden="true"><path d="M2 8H112M104 2L114 8L104 14" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>');
    if (o.mid.small) m.append(h('span', '', o.mid.small));
    el.append(side(o.left), m, side(o.right, true));
  }

  // Key items: { swatch: colour, text } for a colour, { glyph: 'box' | 'dot', text } for how to read a mark.
  const GLYPHS = {
    box: '<svg width="70" height="18" aria-hidden="true"><line x1="4" x2="66" y1="9" y2="9" stroke="currentColor" stroke-width="1.5"/><rect x="20" y="3" width="30" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><line x1="33" x2="33" y1="3" y2="15" stroke="currentColor" stroke-width="2.5"/></svg>',
    dot: '<svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="4" fill="currentColor" fill-opacity=".6"/></svg>',
  };
  function keyItem(item) {
    const sp = h('span');
    if (item.glyph && GLYPHS[item.glyph]) sp.insertAdjacentHTML('beforeend', GLYPHS[item.glyph]);
    if (item.swatch) { const sw = h('span', 'sw'); sw.style.background = item.swatch; sp.append(sw); }
    sp.append(item.text);
    return sp;
  }

  /* figure(parent, { n, question }) -> { chart, key(items), finding(bold, rest), caption(text) } */
  function figure(parent, o) {
    const sec = h('section', 'ar-fig');
    if (o.n != null) sec.append(h('span', 'ar-fn', 'Figure ' + o.n));
    sec.append(h('h2', '', o.question));
    const key = h('div', 'ar-key'); key.hidden = true;
    const chart = h('div', 'ar-chart');
    const finding = h('p', 'ar-finding');
    const cap = h('p', 'ar-cap');
    sec.append(key, chart, finding, cap);
    parent.append(sec);
    return {
      section: sec, chart,
      key: items => { key.textContent = ''; items.forEach(i => key.append(keyItem(i))); key.hidden = false; },
      finding: (bold, rest) => { finding.textContent = ''; finding.append(h('b', '', bold)); if (rest) finding.append(' ' + rest); },
      caption: text => { cap.textContent = text; },
    };
  }

  // ---------- Charts ----------
  /* rankedBars(el, rows, opts)
     rows: [{ label, sub, value, text, color, faded, tip: [lines] }] in the order to draw (best first)
     opts: { base: 0, min, max, refs: [{value, label, strong}], tickFormat, aria, note } */
  function rankedBars(el, rows, o = {}) {
    const base = o.base != null ? o.base : 0, rh = 34, T = 36, R = 120, W = 880;
    const L = gutter(rows), H = T + rows.length * rh + (o.note ? 50 : 30);
    const vals = rows.map(r => r.value).concat([base]).concat((o.refs || []).map(r => r.value));
    const lo = o.min != null ? o.min : Math.min(...vals), hi = o.max != null ? o.max : Math.max(...vals);
    const pad = (hi - lo) * 0.04, x = xScale([[lo - (o.min != null ? 0 : pad), hi + (o.max != null ? 0 : pad)]], L, W - R);
    const svg = svgRoot(el, W, H, o.aria);
    const yb = T + rows.length * rh - 4;
    drawXAxis(svg, x, T - 8, yb, o);
    (o.refs || []).forEach(r => refLine(svg, x, r, T, yb));
    s(svg, 'line', { x1: x(base), x2: x(base), y1: T - 8, y2: yb, class: 'ar-zero' });
    rows.forEach((r, i) => {
      const y = T + i * rh;
      s(svg, 'text', { x: L - 12, y: y + (r.sub ? 10 : 15), 'text-anchor': 'end', class: 'ar-lab' + (r.strong ? ' strong' : '') }, r.label);
      if (r.sub) s(svg, 'text', { x: L - 12, y: y + 24, 'text-anchor': 'end', class: 'ar-sub' }, r.sub);
      const a = x(Math.min(base, r.value)), b = x(Math.max(base, r.value));
      const bar = s(svg, 'rect', { x: a, y: y + 4, width: Math.max(2, b - a), height: rh - 12, rx: 3, style: `fill:${r.color || 'var(--ar-neutral)'};fill-opacity:${r.faded ? 0.35 : 1};stroke:${r.faded ? (r.color || 'var(--ar-neutral)') : 'none'}` });
      s(svg, 'text', { x: Math.max(b, x(base)) + 8, y: y + 19, class: 'ar-val' }, r.text != null ? r.text : fmt.num(r.value));
      tip(bar, r.tip);
    });
    if (o.note) s(svg, 'text', { x: 8, y: H - 10, class: 'ar-note' }, o.note);
    return svg;
  }

  /* strip(el, groups, opts): every measurement as a dot.
     groups: [{ label, sub, values: [], color, mean, note, strong }]
     opts: { band: {from, to, label}, refs, domains: [[lo, hi], ...] (two domains break the axis), axisLabel, aria } */
  function strip(el, groups, o = {}) {
    const rh = 34, T = 40, R = 30, W = 880;
    const L = gutter(groups), H = T + groups.length * rh + 44;
    const all = groups.flatMap(g => g.values || []).concat(o.band ? [o.band.from, o.band.to] : []);
    const pad = (Math.max(...all) - Math.min(...all)) * 0.06 || 0.5;
    const x = xScale(o.domains || [[Math.min(...all) - pad, Math.max(...all) + pad]], L, W - R);
    const svg = svgRoot(el, W, H, o.aria);
    const yb = T + groups.length * rh - 6;
    if (o.band) {
      s(svg, 'rect', { x: x(o.band.from), y: T - 12, width: Math.max(2, x(o.band.to) - x(o.band.from)), height: yb - T + 12, class: 'ar-band' });
      if (o.band.label) s(svg, 'text', { x: x(o.band.to) + 5, y: T - 16, class: 'ar-sub' }, o.band.label);
    }
    drawXAxis(svg, x, T - 12, yb, o);
    (o.refs || []).forEach(r => refLine(svg, x, r, T - 6, yb));
    if (o.axisLabel) s(svg, 'text', { x: W - R, y: H - 4, 'text-anchor': 'end', class: 'ar-sub' }, o.axisLabel);
    groups.forEach((g, i) => {
      const y = T + i * rh + 6, c = g.color || 'var(--ar-neutral)';
      s(svg, 'text', { x: L - 12, y: y + (g.sub ? -1 : 4), 'text-anchor': 'end', class: 'ar-lab' + (g.strong ? ' strong' : '') }, g.label);
      if (g.sub) s(svg, 'text', { x: L - 12, y: y + 13, 'text-anchor': 'end', class: 'ar-sub' }, g.sub);
      if (!g.values || !g.values.length) { s(svg, 'text', { x: L + 4, y: y + 4, class: 'ar-note' }, g.note || 'not measured'); return; }
      const mean = g.mean != null ? g.mean : stats(g.values).mean;
      s(svg, 'line', { x1: x(mean), x2: x(mean), y1: y - 10, y2: y + 10, style: `stroke:${c};stroke-width:2.5` });
      g.values.forEach((v, j) => tip(s(svg, 'circle', { cx: x(v), cy: y, r: 5, style: `fill:${c};fill-opacity:.8;stroke:var(--ar-paper);stroke-width:1.5` }), [g.label + ', measurement ' + (j + 1), fmt.num(v, o.decimals != null ? o.decimals : 3)]));
    });
    return svg;
  }

  /* boxes(el, groups, opts): box plots with every measurement overlaid.
     groups: [{ label, sub, values: [], color, fill, strong }]
     opts: { refs, axisLabel, valueDecimals, aria } */
  function boxes(el, groups, o = {}) {
    const rh = 50, T = 30, R = 70, W = 880;
    const rows = groups.map(g => Object.assign({}, g, { st: stats(g.values), label: g.label + '  (n=' + (g.values || []).length + ')' }));
    const L = gutter(rows), H = T + rows.length * rh + 44;
    const all = rows.flatMap(r => r.values || []);
    const pad = (Math.max(...all) - Math.min(...all)) * 0.05 || 0.5;
    const x = xScale([[Math.min(...all) - pad, Math.max(...all) + pad]], L, W - R);
    const svg = svgRoot(el, W, H, o.aria);
    const yb = T + rows.length * rh - 6;
    drawXAxis(svg, x, T - 8, yb, o);
    (o.refs || []).forEach(r => refLine(svg, x, r, T, yb));
    if (o.axisLabel) s(svg, 'text', { x: W - 8, y: H - 4, 'text-anchor': 'end', class: 'ar-sub' }, o.axisLabel);
    const dp = o.valueDecimals != null ? o.valueDecimals : 2;
    rows.forEach((r, i) => {
      const yc = T + i * rh + 18, c = r.color || 'var(--ar-neutral)', b = r.st;
      s(svg, 'text', { x: L - 12, y: yc - 1, 'text-anchor': 'end', class: 'ar-lab' + (r.strong ? ' strong' : '') }, r.label);
      if (r.sub) s(svg, 'text', { x: L - 12, y: yc + 14, 'text-anchor': 'end', class: 'ar-sub' }, r.sub);
      if (!b) { s(svg, 'text', { x: L + 4, y: yc + 4, class: 'ar-note' }, 'not measured'); return; }
      s(svg, 'line', { x1: x(b.min), x2: x(b.max), y1: yc, y2: yc, style: `stroke:${c};stroke-width:1.5` });
      [b.min, b.max].forEach(v => s(svg, 'line', { x1: x(v), x2: x(v), y1: yc - 6, y2: yc + 6, style: `stroke:${c};stroke-width:1.5` }));
      const box = s(svg, 'rect', { x: x(b.q1), y: yc - 13, width: Math.max(2, x(b.q3) - x(b.q1)), height: 26, rx: 3, style: `fill:${r.fill || 'var(--ar-neutral-soft)'};stroke:${c};stroke-width:1.5` });
      s(svg, 'line', { x1: x(b.med), x2: x(b.med), y1: yc - 13, y2: yc + 13, style: `stroke:${c};stroke-width:3` });
      r.values.forEach((v, j) => s(svg, 'circle', { cx: x(v), cy: yc + ((j * 7) % 15) - 7, r: 2.8, style: `fill:${c};fill-opacity:.55` }));
      s(svg, 'text', { x: x(b.max) + 8, y: yc + 4, class: 'ar-val' }, fmt.num(b.med, dp));
      tip(box, [r.label, 'median ' + fmt.num(b.med, dp) + ', mean ' + fmt.num(b.mean, dp), 'middle half ' + fmt.num(b.q1, dp) + ' to ' + fmt.num(b.q3, dp), 'range ' + fmt.num(b.min, dp) + ' to ' + fmt.num(b.max, dp)]);
    });
    return svg;
  }
  const BOX_KEY = [{ glyph: 'box', text: 'box: middle half of the runs, line: median, whiskers: slowest to fastest run' }, { glyph: 'dot', text: 'one measurement' }];

  /* scatter(el, points, opts)
     points: [{ x, y, color, faded, shape: 'dot' | 'diamond', label, tip }]
     opts: { xLabel, yLabel, ratioLines: [{k, label, strong}], aria } */
  function scatter(el, points, o = {}) {
    const W = 880, H = 440, L = 64, R = 30, T = 24, B = 54;
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const xp = (Math.max(...xs) - Math.min(...xs)) * 0.08 || 1, yp = (Math.max(...ys) - Math.min(...ys)) * 0.08 || 1;
    const x0 = Math.min(...xs) - xp, x1 = Math.max(...xs) + xp, y0 = Math.min(...ys) - yp, y1 = Math.max(...ys) + yp;
    const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const svg = svgRoot(el, W, H, o.aria);
    const xs_ = niceStep(x1 - x0), ys_ = niceStep(y1 - y0);
    for (let g = Math.ceil(y0 / ys_) * ys_; g <= y1; g += ys_) { s(svg, 'line', { x1: L, x2: W - R, y1: Y(g), y2: Y(g), class: 'ar-grid' }); s(svg, 'text', { x: L - 8, y: Y(g) + 4, 'text-anchor': 'end', class: 'ar-ax' }, g.toFixed(decimals(ys_))); }
    for (let g = Math.ceil(x0 / xs_) * xs_; g <= x1; g += xs_) { s(svg, 'line', { x1: X(g), x2: X(g), y1: T, y2: H - B, class: 'ar-grid' }); s(svg, 'text', { x: X(g), y: H - B + 16, 'text-anchor': 'middle', class: 'ar-ax' }, g.toFixed(decimals(xs_))); }
    if (o.xLabel) s(svg, 'text', { x: (L + W - R) / 2, y: H - 10, 'text-anchor': 'middle', class: 'ar-sub' }, o.xLabel);
    if (o.yLabel) s(svg, 'text', { x: 14, y: (T + H - B) / 2, transform: `rotate(-90 14 ${(T + H - B) / 2})`, 'text-anchor': 'middle', class: 'ar-sub' }, o.yLabel);
    const id = 'arclip' + Math.random().toString(36).slice(2, 8);
    s(s(svg, 'clipPath', { id }), 'rect', { x: L, y: T, width: W - L - R, height: H - T - B });
    for (const r of o.ratioLines || []) {
      s(svg, 'line', { x1: X(x0), y1: Y(r.k * x0), x2: X(x1), y2: Y(r.k * x1), class: r.strong ? 'ar-ref strong' : 'ar-ref', 'clip-path': `url(#${id})` });
      const px = Math.min(x1, (y1 - yp * 0.6) / r.k);
      if (r.label && px > x0) s(svg, 'text', { x: X(px) - 6, y: Y(r.k * px) - 4, 'text-anchor': 'end', class: r.strong ? 'ar-reflab strong' : 'ar-reflab' }, r.label);
    }
    for (const p of points) {
      const c = p.color || 'var(--ar-neutral)';
      const m = p.shape === 'diamond'
        ? s(svg, 'path', { d: `M${X(p.x)} ${Y(p.y) - 7} l7 7 l-7 7 l-7 -7 z`, style: `fill:var(--ar-paper);stroke:${c};stroke-width:2` })
        : s(svg, 'circle', { cx: X(p.x), cy: Y(p.y), r: 5.5, style: `fill:${c};fill-opacity:${p.faded ? 0.35 : 0.9};stroke:var(--ar-paper);stroke-width:1.5` });
      if (p.label) s(svg, 'text', { x: X(p.x) + (p.labelLeft ? -10 : 10), y: Y(p.y) - 8, 'text-anchor': p.labelLeft ? 'end' : 'start', class: p.shape === 'diamond' ? 'ar-sub' : 'ar-val' }, p.label);
      tip(m, p.tip);
    }
    return svg;
  }

  /* trajectory(el, points, opts): values in the order versions were made; gaps break the line.
     points: [{ label, y (null for a gap), color, mark, valueLabel, tip }]
     opts: { zero: {value, label}, annotations: [{after: index, text}], yLabel, yFormat, aria } */
  function trajectory(el, points, o = {}) {
    const W = 880, H = 340, L = 70, R = 30, T = 34, B = 44;
    const ys = points.filter(p => p.y != null).map(p => p.y).concat(o.zero ? [o.zero.value] : []);
    const pad = (Math.max(...ys) - Math.min(...ys)) * 0.1 || 1, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
    const X = i => L + (W - L - R) * (i + 0.5) / points.length, Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const svg = svgRoot(el, W, H, o.aria);
    const st = niceStep(y1 - y0);
    for (let g = Math.ceil(y0 / st) * st; g <= y1; g += st) { s(svg, 'line', { x1: L, x2: W - R, y1: Y(g), y2: Y(g), class: 'ar-grid' }); s(svg, 'text', { x: L - 8, y: Y(g) + 4, 'text-anchor': 'end', class: 'ar-ax' }, o.yFormat ? o.yFormat(g) : g.toFixed(decimals(st))); }
    if (o.zero) { s(svg, 'line', { x1: L, x2: W - R, y1: Y(o.zero.value), y2: Y(o.zero.value), class: 'ar-zero' }); if (o.zero.label) s(svg, 'text', { x: L + 6, y: Y(o.zero.value) - 6, class: 'ar-sub' }, o.zero.label); }
    if (o.yLabel) s(svg, 'text', { x: 14, y: (T + H - B) / 2, transform: `rotate(-90 14 ${(T + H - B) / 2})`, 'text-anchor': 'middle', class: 'ar-sub' }, o.yLabel);
    for (const a of o.annotations || []) {
      const ax = (X(a.after) + X(a.after + 1)) / 2;
      s(svg, 'line', { x1: ax, x2: ax, y1: T - 14, y2: H - B, class: 'ar-ref strong' });
      s(svg, 'text', { x: ax + 6, y: T - 18, class: 'ar-reflab strong' }, a.text);
    }
    let seg = [];
    const flush = () => { if (seg.length > 1) s(svg, 'polyline', { points: seg.join(' '), style: 'fill:none;stroke:var(--ar-accent);stroke-width:2;stroke-linejoin:round' }); seg = []; };
    points.forEach((p, i) => {
      s(svg, 'text', { x: X(i), y: H - B + 18, 'text-anchor': 'middle', class: 'ar-lab' }, p.label);
      if (p.y == null) { flush(); s(svg, 'text', { x: X(i), y: o.zero ? Y(o.zero.value) + 18 : H - B - 8, 'text-anchor': 'middle', class: 'ar-note' }, p.gapText || 'not measured'); return; }
      seg.push(X(i) + ',' + Y(p.y));
    });
    flush();
    points.forEach((p, i) => {
      if (p.y == null) return;
      const c = p.color || 'var(--ar-accent)';
      if (p.mark) s(svg, 'circle', { cx: X(i), cy: Y(p.y), r: 10, style: `fill:none;stroke:${c};stroke-width:2` });
      tip(s(svg, 'circle', { cx: X(i), cy: Y(p.y), r: 5, style: `fill:${c};stroke:var(--ar-paper);stroke-width:2` }), p.tip);
      if (p.valueLabel) s(svg, 'text', { x: X(i), y: Y(p.y) - 14, 'text-anchor': 'middle', class: 'ar-val' }, p.valueLabel);
    });
    return svg;
  }

  /* table(el, headers, rows, numericColumns): rows are arrays of strings */
  function table(el, headers, rows, numeric = []) {
    const wrap = h('div', 'ar-tbl'), t = h('table');
    const hr = h('tr'); headers.forEach((c, i) => hr.append(h('th', numeric.includes(i) ? 'num' : '', c)));
    const th = h('thead'); th.append(hr); t.append(th);
    const tb = h('tbody');
    rows.forEach(r => { const tr = h('tr'); r.forEach((c, i) => tr.append(h('td', numeric.includes(i) ? 'num' : '', c == null ? '' : String(c)))); tb.append(tr); });
    t.append(tb); wrap.append(t); el.append(wrap);
    return t;
  }

  // Categorical colours for runs or groups, in a fixed order (validated for colour-vision deficiency).
  const series = i => 'var(--ar-c' + ((i % 6) + 1) + ')';

  window.ArtemisReport = { h, s, fmt, stats, tip, header, headline, figure, rankedBars, strip, boxes, BOX_KEY, scatter, trajectory, table, series };
})();
