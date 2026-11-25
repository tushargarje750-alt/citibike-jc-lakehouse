'use strict';

// Draws the demo page from data/demo.json (written by scripts/export_demo_data.py).
// No libraries: every chart is a small hand-made SVG.
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const nf = new Intl.NumberFormat('en-US');
  const tooltip = document.getElementById('tooltip');
  const drawers = [];
  let activeClear = null;

  const SERIES = {
    member: { name: 'Members', color: 'var(--s1)' },
    casual: { name: 'Casual riders', color: 'var(--s2)' },
    weekday: { name: 'Typical weekday', color: 'var(--s1)' },
    weekend: { name: 'Typical weekend day', color: 'var(--s2)' },
    dry: { name: 'Dry day', color: 'var(--s1)' },
    wet: { name: 'Wet day (1 mm or more)', color: 'var(--s2)' },
  };
  const AREAS = { 'Jersey City': 'var(--s1)', Hoboken: 'var(--s2)' };
  const TEMPERATURE_BANDS = {
    1: ['Freezing', '< 0 °C'],
    2: ['Cold', '0–10 °C'],
    3: ['Mild', '10–20 °C'],
    4: ['Warm', '20–27 °C'],
    5: ['Hot', '≥ 27 °C'],
  };
  const REASONS = {
    duration_too_short: 'Trip shorter than 60 seconds',
    duration_too_long: 'Trip longer than 24 hours',
    non_positive_duration: 'End time not after start time',
    missing_start_station: 'No start station',
    duplicate_ride_id: 'Same ride id twice (duplicate)',
    missing_ride_id: 'No ride id',
    invalid_timestamp: 'Unreadable start or end time',
    invalid_rider_type: 'Unknown rider type',
    start_outside_service_area: 'Start point outside the service area',
  };

  // ---------- small helpers ----------
  function rowsOf(table) {
    return table.rows.map((r) => Object.fromEntries(table.columns.map((c, i) => [c, r[i]])));
  }

  function el(tag, attrs, parent, text) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'class') node.className = v;
      else if (k === 'style') node.style.cssText = v;
      else node.setAttribute(k, v);
    }
    if (text !== undefined) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }

  function svg(tag, attrs, parent, text) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }

  const utc = (iso) => new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso);
  const fmtDate = (iso, opts) => utc(iso).toLocaleDateString('en-GB', Object.assign({ timeZone: 'UTC' }, opts));
  const longDate = (iso) => fmtDate(iso, { day: 'numeric', month: 'long', year: 'numeric' });
  const monthYear = (iso) => fmtDate(iso, { month: 'long', year: 'numeric' });
  const shortMonth = (iso) => fmtDate(iso, { month: 'short', year: 'numeric' });
  const pct = (part, whole, digits) => ((100 * part) / whole).toFixed(digits) + '%';

  function scale(d0, d1, r0, r1) {
    const k = (r1 - r0) / (d1 - d0 || 1);
    return (v) => r0 + (v - d0) * k;
  }

  function niceTicks(min, max, count) {
    const raw = (max - min) / Math.max(1, count);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const r = raw / mag;
    const step = (r > 5 ? 10 : r > 2 ? 5 : r > 1 ? 2 : 1) * mag;
    const out = [];
    const end = Math.ceil(max / step - 1e-9) * step;
    for (let v = Math.floor(min / step + 1e-9) * step; v <= end + step / 2; v += step) out.push(+v.toFixed(10));
    return out;
  }

  function axisFormat(maxTick) {
    if (maxTick >= 10000) return (v) => (v === 0 ? '0' : nf.format(v / 1000) + 'K');
    if (maxTick < 10) return (v) => String(+v.toFixed(2));
    return (v) => nf.format(v);
  }

  function yAxis(g, ticks, y, width, fmt) {
    for (const t of ticks) {
      svg('line', { class: t === 0 ? 'baseline' : 'gridline', x1: 0, x2: width, y1: y(t), y2: y(t) }, g);
      svg('text', { x: -8, y: y(t), 'text-anchor': 'end', 'dominant-baseline': 'middle' }, g, fmt(t));
    }
  }

  function columnUp(x0, base, w, h, r) {
    r = Math.min(r, h, w / 2);
    const top = base - h;
    return `M${x0},${base}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x0 + w - r}Q${x0 + w},${top} ${x0 + w},${top + r}V${base}Z`;
  }

  function barRight(x0, y0, w, h, r) {
    r = Math.min(r, w, h / 2);
    return `M${x0},${y0}H${x0 + w - r}Q${x0 + w},${y0} ${x0 + w},${y0 + r}V${y0 + h - r}Q${x0 + w},${y0 + h} ${x0 + w - r},${y0 + h}H${x0}Z`;
  }

  function legend(parent, items, before) {
    const ul = el('ul', { class: 'legend' });
    for (const it of items) {
      const li = el('li', {}, ul);
      el('span', { class: 'key ' + (it.kind || ''), style: it.color ? `background:${it.color}` : '' }, li);
      li.appendChild(document.createTextNode(it.name));
    }
    parent.insertBefore(ul, before || null);
    return ul;
  }

  function plotIn(card) {
    return el('div', { class: 'plot' }, card);
  }

  function freshSvg(plot, height, label) {
    plot.textContent = '';
    const width = Math.max(260, Math.floor(plot.clientWidth));
    const root = svg('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': label }, plot);
    return { root, width };
  }

  function tableView(card, summary, headers, rows, numeric) {
    const details = el('details', { class: 'table-view' }, card);
    el('summary', {}, details, summary);
    const scroll = el('div', { class: 'table-scroll' }, details);
    const table = el('table', {}, scroll);
    const head = el('tr', {}, el('thead', {}, table));
    headers.forEach((h, i) => el('th', { scope: 'col', class: numeric[i] ? 'num' : '' }, head, h));
    const body = el('tbody', {}, table);
    for (const row of rows) {
      const tr = el('tr', {}, body);
      row.forEach((v, i) => el('td', { class: numeric[i] ? 'num' : '' }, tr, v));
    }
  }

  // ---------- tooltip ----------
  function showTip(evt, title, lines) {
    tooltip.textContent = '';
    el('div', { class: 'tt-title' }, tooltip, title);
    for (const [name, value, color] of lines) {
      const row = el('div', { class: 'tt-row' }, tooltip);
      const left = el('span', {}, row);
      if (color) el('span', { class: 'key', style: `background:${color}` }, left);
      left.appendChild(document.createTextNode(name));
      el('b', {}, row, value);
    }
    tooltip.hidden = false;
    const pad = 14;
    const w = tooltip.offsetWidth;
    const h = tooltip.offsetHeight;
    let x = evt.clientX + pad;
    let y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - pad - w;
    if (y + h > window.innerHeight - 8) y = evt.clientY - pad - h;
    tooltip.style.left = Math.max(8, x) + 'px';
    tooltip.style.top = Math.max(8, y) + 'px';
  }

  function hover(target, onMove, onClear) {
    const clear = () => {
      tooltip.hidden = true;
      if (onClear) onClear();
      if (activeClear === clear) activeClear = null;
    };
    const move = (evt) => {
      if (activeClear && activeClear !== clear) activeClear();
      activeClear = clear;
      onMove(evt);
    };
    target.style.touchAction = 'pan-y';
    target.addEventListener('pointermove', move);
    target.addEventListener('pointerdown', move);
    target.addEventListener('pointerleave', (evt) => {
      if (evt.pointerType === 'mouse') clear();
    });
  }

  document.addEventListener('pointerdown', (evt) => {
    if (activeClear && !evt.target.closest('.plot')) activeClear();
  });
  window.addEventListener('scroll', () => activeClear && activeClear(), { passive: true });

  // ---------- chart: lines over an index ----------
  function lineChart(plot, opt) {
    const height = opt.height || 260;
    const { root, width } = freshSvg(plot, height, opt.label);
    const endLabels = width >= 560;
    const m = { top: 12, right: endLabels ? 104 : 14, bottom: 26, left: 46 };
    const iw = width - m.left - m.right;
    const ih = height - m.top - m.bottom;
    const g = svg('g', { transform: `translate(${m.left},${m.top})` }, root);
    const pts = opt.points;
    const n = pts.length;
    const x = scale(0, n - 1, 0, iw);
    const maxV = Math.max(...pts.flatMap((p) => opt.series.map((sr) => p[sr.key] || 0)));
    const yt = niceTicks(0, maxV, 5);
    const y = scale(0, yt[yt.length - 1], ih, 0);
    yAxis(g, yt, y, iw, axisFormat(yt[yt.length - 1]));
    for (const t of opt.xTicks(iw)) {
      svg('text', { x: x(t.i), y: ih + 18, 'text-anchor': 'middle' }, g, t.label);
    }
    for (const sr of opt.series) {
      let d = '';
      let pen = false;
      pts.forEach((p, i) => {
        const v = p[sr.key];
        if (v == null) { pen = false; return; }
        d += (pen ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1);
        pen = true;
      });
      svg('path', { class: 'series', d, style: `stroke:${sr.color}` }, g);
    }
    if (endLabels) {
      const last = pts[n - 1];
      const ys = opt.series.map((sr) => y(last[sr.key]));
      const apart = ys.every((a, i) => ys.every((b, j) => i === j || Math.abs(a - b) >= 16));
      if (apart) {
        opt.series.forEach((sr, k) => {
          svg('circle', { cx: x(n - 1), cy: ys[k], r: 4, class: 'dot-ring', style: `fill:${sr.color}` }, g);
          svg('text', { x: x(n - 1) + 10, y: ys[k], 'dominant-baseline': 'middle', class: 'label' }, g, sr.name);
        });
      }
    }
    const cross = svg('line', { class: 'crosshair', y1: 0, y2: ih, visibility: 'hidden' }, g);
    const dots = opt.series.map((sr) => svg('circle', { r: 4.5, class: 'dot-ring', style: `fill:${sr.color}`, visibility: 'hidden' }, g));
    const hit = svg('rect', { class: 'hit', x: -6, y: 0, width: iw + 12, height: ih }, g);
    hover(hit, (evt) => {
      const box = hit.getBoundingClientRect();
      const px = evt.clientX - box.left - 6;
      const i = Math.max(0, Math.min(n - 1, Math.round((px / iw) * (n - 1))));
      const p = pts[i];
      cross.setAttribute('x1', x(i));
      cross.setAttribute('x2', x(i));
      cross.setAttribute('visibility', 'visible');
      opt.series.forEach((sr, k) => {
        const v = p[sr.key];
        dots[k].setAttribute('visibility', v == null ? 'hidden' : 'visible');
        if (v != null) { dots[k].setAttribute('cx', x(i)); dots[k].setAttribute('cy', y(v)); }
      });
      showTip(evt, opt.tipTitle(p), opt.series.map((sr) => [sr.name, p[sr.key] == null ? '–' : opt.tipValue(p[sr.key]), sr.color]));
    }, () => {
      cross.setAttribute('visibility', 'hidden');
      dots.forEach((d) => d.setAttribute('visibility', 'hidden'));
    });
  }

  function monthTicks(points) {
    return (iw) => {
      const every = iw < 420 ? 2 : 1;
      return points
        .map((p, i) => ({ i, date: utc(p.ride_month) }))
        .filter((t) => t.date.getUTCMonth() === 0 && t.date.getUTCFullYear() % every === 0)
        .map((t) => ({ i: t.i, label: String(t.date.getUTCFullYear()) }));
    };
  }

  // ---------- chart: top stations ----------
  function stationBars(plot, items) {
    const rowH = 42;
    const height = rowH * items.length;
    const { root, width } = freshSvg(plot, height, 'Top 10 start stations by trips started');
    const room = 70;
    const x = scale(0, Math.max(...items.map((d) => d.trips)), 0, width - room);
    items.forEach((d, k) => {
      const y0 = k * rowH;
      const name = svg('text', { x: 0, y: y0 + 13, class: 'label' }, root, `${d.rank}. ${d.name}`);
      let text = name.textContent;
      while (name.getComputedTextLength() > width - 4 && text.length > 8) {
        text = text.slice(0, -2);
        name.textContent = text + '…';
      }
      const w = Math.max(2, x(d.trips));
      svg('path', { d: barRight(0, y0 + 20, w, 16, 4), style: `fill:${AREAS[d.area] || 'var(--s3)'}` }, root);
      svg('text', { x: w + 6, y: y0 + 28.5, 'dominant-baseline': 'middle', class: 'value' }, root, nf.format(d.trips));
      const hit = svg('rect', { class: 'hit', x: 0, y: y0, width, height: rowH }, root);
      hover(hit, (evt) => showTip(evt, d.name, [['Area', d.area, AREAS[d.area]], ['Trips started', nf.format(d.trips)]]));
    });
  }

  // ---------- chart: weather index ----------
  function weatherBars(plot, groups) {
    const height = 270;
    const { root, width } = freshSvg(plot, height, 'Ridership index by temperature band, dry days and wet days');
    const m = { top: 10, right: 6, bottom: 42, left: 38 };
    const iw = width - m.left - m.right;
    const ih = height - m.top - m.bottom;
    const g = svg('g', { transform: `translate(${m.left},${m.top})` }, root);
    const maxV = Math.max(1.2, ...groups.flatMap((d) => [d.dry || 0, d.wet || 0]));
    const yt = niceTicks(0, maxV, 6);
    const y = scale(0, yt[yt.length - 1], ih, 0);
    yAxis(g, yt, y, iw, (v) => (v === 0 ? '0' : v.toFixed(1)));
    svg('line', { class: 'ref', x1: 0, x2: iw, y1: y(1), y2: y(1) }, g);
    const band = iw / groups.length;
    const barW = Math.max(8, Math.min(24, (band - 20) / 2));
    groups.forEach((d, k) => {
      const cx = band * (k + 0.5);
      svg('text', { x: cx, y: ih + 17, 'text-anchor': 'middle', class: 'label' }, g, d.name);
      svg('text', { x: cx, y: ih + 32, 'text-anchor': 'middle' }, g, d.range);
      [['dry', cx - barW - 1], ['wet', cx + 1]].forEach(([key, x0]) => {
        const v = d[key];
        if (v == null) return;
        svg('path', { d: columnUp(x0, y(0), barW, y(0) - y(v), 4), style: `fill:${SERIES[key].color}` }, g);
        const hit = svg('rect', { class: 'hit', x: x0 - 3, y: 0, width: barW + 4, height: ih }, g);
        const change = Math.round((v - 1) * 100);
        const words = change === 0 ? 'Same as a normal day' : `${Math.abs(change)}% ${change < 0 ? 'fewer' : 'more'} trips than normal`;
        hover(hit, (evt) => showTip(evt, `${d.name} (${d.range})`, [
          [SERIES[key].name, v.toFixed(3), SERIES[key].color],
          [words, ''],
        ]));
      });
    });
  }

  // ---------- chart: daily scatter ----------
  function scatter(plot, pts) {
    const height = 320;
    const { root, width } = freshSvg(plot, height, 'Trips per day against the mean temperature of the day');
    const m = { top: 12, right: 14, bottom: 30, left: 46 };
    const iw = width - m.left - m.right;
    const ih = height - m.top - m.bottom;
    const g = svg('g', { transform: `translate(${m.left},${m.top})` }, root);
    const temps = pts.map((p) => p.temp);
    const xt = niceTicks(Math.min(...temps), Math.max(...temps), iw < 420 ? 5 : 9);
    const x = scale(xt[0], xt[xt.length - 1], 0, iw);
    const yt = niceTicks(0, Math.max(...pts.map((p) => p.trips)), 5);
    const y = scale(0, yt[yt.length - 1], ih, 0);
    yAxis(g, yt, y, iw, axisFormat(yt[yt.length - 1]));
    for (const t of xt) {
      svg('text', { x: x(t), y: ih + 18, 'text-anchor': 'middle' }, g, `${t} °C`);
    }
    for (const key of ['dry', 'wet']) {
      const layer = svg('g', { style: `fill:${SERIES[key].color}`, 'fill-opacity': 0.55 }, g);
      for (const p of pts) {
        if ((p.wet ? 'wet' : 'dry') === key) svg('circle', { cx: x(p.temp).toFixed(1), cy: y(p.trips).toFixed(1), r: 2.8 }, layer);
      }
    }
    const mark = svg('circle', { r: 5.5, class: 'dot-ring', visibility: 'hidden' }, g);
    const hit = svg('rect', { class: 'hit', x: 0, y: 0, width: iw, height: ih }, g);
    hover(hit, (evt) => {
      const box = hit.getBoundingClientRect();
      const px = evt.clientX - box.left;
      const py = evt.clientY - box.top;
      let best = null;
      let bestD = 20 * 20;
      for (const p of pts) {
        const dx = x(p.temp) - px;
        const dy = y(p.trips) - py;
        const d2 = dx * dx + dy * dy;
        if (d2 < bestD) { bestD = d2; best = p; }
      }
      if (!best) { mark.setAttribute('visibility', 'hidden'); tooltip.hidden = true; return; }
      const key = best.wet ? 'wet' : 'dry';
      mark.setAttribute('cx', x(best.temp));
      mark.setAttribute('cy', y(best.trips));
      mark.setAttribute('style', `fill:${SERIES[key].color}`);
      mark.setAttribute('visibility', 'visible');
      showTip(evt, fmtDate(best.date, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }), [
        ['Trips', nf.format(best.trips)],
        ['Mean temperature', `${best.temp.toFixed(1)} °C`],
        [SERIES[key].name, '', SERIES[key].color],
      ]);
    }, () => mark.setAttribute('visibility', 'hidden'));
  }

  // ---------- page sections ----------
  function renderIntro(data) {
    const meta = data.meta;
    const k = rowsOf(data.datasets.ds_kpis)[0];
    // the export time is UTC; show the date in the reader's own time zone
    const exported = new Date(meta.exported_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    const note = document.getElementById('demo-note');
    note.textContent = '';
    el('strong', {}, note, 'About this demo: ');
    note.appendChild(document.createTextNode(
      `the numbers were exported from the project's gold tables on ${exported} and saved with this page. ` +
      'The page never contacts Databricks.'));
    document.getElementById('period').textContent =
      `Accepted trips from ${longDate(meta.first_day)} to ${longDate(meta.last_day)}.`;
    document.getElementById('foot-export').textContent =
      `Data file: data/demo.json, made by scripts/export_demo_data.py on ${exported}.`;

    const stats = document.getElementById('stats');
    const tiles = [
      ['Total trips', nf.format(k.total_trips), `${shortMonth(meta.first_day)} to ${shortMonth(meta.last_day)}`],
      ['Average trips per day', nf.format(k.avg_trips_per_day), `Busiest: ${longDate(meta.busiest_day)}, ${nf.format(meta.busiest_day_trips)}`],
      ['Trips by members', k.member_share_pct.toFixed(1) + '%', 'The rest are casual riders'],
      ['Trips on electric bikes', k.electric_share_pct.toFixed(1) + '%', 'The rest are classic or docked bikes'],
    ];
    for (const [label, value, sub] of tiles) {
      const tile = el('div', { class: 'card stat' }, stats);
      el('p', { class: 'label' }, tile, label);
      el('p', { class: 'value' }, tile, value);
      el('p', { class: 'sub' }, tile, sub);
    }
  }

  function setupMonthly(data) {
    const card = document.getElementById('chart-monthly');
    const points = rowsOf(data.datasets.ds_monthly);
    legend(card, [SERIES.member, SERIES.casual].map((s) => ({ ...s, kind: 'line' })));
    const plot = plotIn(card);
    const years = rowsOf(data.yearly);
    const first = data.meta.first_day;
    const last = data.meta.last_day;
    const yearLine = el('p', { class: 'years' }, card);
    el('span', { class: 'years-title' }, yearLine, 'Trips per year');
    years.forEach((r, i) => {
      let part = '';
      if (String(r.ride_year) === first.slice(0, 4) && !first.endsWith('-01-01')) part = ` (from ${fmtDate(first, { month: 'short' })})`;
      if (String(r.ride_year) === last.slice(0, 4) && !last.endsWith('-12-31')) part = ` (to ${fmtDate(last, { month: 'short' })})`;
      const item = el('span', { class: 'year' }, yearLine, `${r.ride_year}${part} `);
      el('b', {}, item, nf.format(r.trips));
    });
    tableView(card, 'Show the numbers', ['Month', 'Members', 'Casual riders', 'Total'],
      points.map((p) => [monthYear(p.ride_month), nf.format(p.member_trips), nf.format(p.casual_trips), nf.format(p.member_trips + p.casual_trips)]),
      [false, true, true, true]);
    drawers.push(() => lineChart(plot, {
      points,
      label: 'Trips per month by members and casual riders',
      series: [{ key: 'member_trips', ...SERIES.member }, { key: 'casual_trips', ...SERIES.casual }],
      xTicks: monthTicks(points),
      tipTitle: (p) => monthYear(p.ride_month),
      tipValue: (v) => nf.format(v) + ' trips',
    }));
  }

  function setupStations(data) {
    const card = document.getElementById('chart-stations');
    const items = rowsOf(data.datasets.ds_top_stations).map((r) => {
      const match = /^(\d+)\s+(.*)$/.exec(r.station);
      return { rank: match ? +match[1] : '', name: match ? match[2] : r.station, area: r.area, trips: r.trips_started };
    });
    const areas = [...new Set(items.map((d) => d.area))].sort((a, b) => (a === 'Jersey City' ? -1 : b === 'Jersey City' ? 1 : a.localeCompare(b)));
    legend(card, areas.map((a) => ({ name: a, color: AREAS[a] || 'var(--s3)' })));
    const plot = plotIn(card);
    tableView(card, 'Show the numbers', ['Rank', 'Station', 'Area', 'Trips started'],
      items.map((d) => [String(d.rank), d.name, d.area, nf.format(d.trips)]), [true, false, false, true]);
    drawers.push(() => stationBars(plot, items));
  }

  function setupHours(data) {
    const card = document.getElementById('chart-hours');
    const points = rowsOf(data.datasets.ds_peak_hours).sort((a, b) => a.started_hour - b.started_hour);
    legend(card, [SERIES.weekday, SERIES.weekend].map((s) => ({ ...s, kind: 'line' })));
    const plot = plotIn(card);
    const hour = (h) => String(h).padStart(2, '0') + ':00';
    tableView(card, 'Show the numbers', ['Hour', 'Typical weekday', 'Typical weekend day'],
      points.map((p) => [hour(p.started_hour), p.weekday_trips.toFixed(1), p.weekend_trips.toFixed(1)]), [false, true, true]);
    drawers.push(() => lineChart(plot, {
      points,
      label: 'Trips per hour on a typical weekday and weekend day',
      height: window.innerWidth > 760 ? 400 : 260,
      series: [{ key: 'weekday_trips', ...SERIES.weekday }, { key: 'weekend_trips', ...SERIES.weekend }],
      xTicks: (iw) => points.filter((p) => p.started_hour % (iw < 360 ? 6 : 3) === 0).map((p, j) => ({ i: points.indexOf(p), label: hour(p.started_hour) })),
      tipTitle: (p) => `${hour(p.started_hour)} to ${hour((p.started_hour + 1) % 24)}`,
      tipValue: (v) => v.toFixed(1) + ' trips',
    }));
  }

  function setupDuration(data) {
    const card = document.getElementById('chart-duration');
    const points = rowsOf(data.datasets.ds_duration);
    legend(card, [SERIES.member, SERIES.casual].map((s) => ({ ...s, kind: 'line' })));
    const plot = plotIn(card);
    const min = (v) => (v == null ? '–' : v.toFixed(1));
    tableView(card, 'Show the numbers', ['Month', 'Members (min)', 'Casual riders (min)'],
      points.map((p) => [monthYear(p.ride_month), min(p.member_median_minutes), min(p.casual_median_minutes)]), [false, true, true]);
    drawers.push(() => lineChart(plot, {
      points,
      label: 'Median trip length in minutes per month, members and casual riders',
      series: [{ key: 'member_median_minutes', ...SERIES.member }, { key: 'casual_median_minutes', ...SERIES.casual }],
      xTicks: monthTicks(points),
      tipTitle: (p) => monthYear(p.ride_month),
      tipValue: (v) => v.toFixed(1) + ' min',
    }));
  }

  function setupWeather(data) {
    const card = document.getElementById('chart-weather');
    const byBand = {};
    for (const r of rowsOf(data.datasets.ds_weather)) {
      const id = parseInt(r.temperature, 10);
      const [name, range] = TEMPERATURE_BANDS[id] || [r.temperature, ''];
      byBand[id] = byBand[id] || { id, name, range };
      byBand[id][r.conditions.startsWith('Wet') ? 'wet' : 'dry'] = r.ridership_index;
    }
    const groups = Object.values(byBand).sort((a, b) => a.id - b.id);
    legend(card, [SERIES.dry, SERIES.wet, { name: '1.0 = a normal day', kind: 'ref' }]);
    const plot = plotIn(card);
    const idx = (v) => (v == null ? '–' : v.toFixed(3));
    tableView(card, 'Show the numbers', ['Temperature', 'Dry day', 'Wet day'],
      groups.map((d) => [`${d.name} (${d.range})`, idx(d.dry), idx(d.wet)]), [false, true, true]);
    drawers.push(() => weatherBars(plot, groups));
  }

  function setupScatter(data) {
    const card = document.getElementById('chart-scatter');
    const pts = rowsOf(data.datasets.ds_daily_weather).map((r) => ({
      date: r.ride_date, temp: r.temperature_mean_c, trips: r.trips, wet: r.conditions.startsWith('Wet'),
    }));
    legend(card, [SERIES.dry, SERIES.wet]);
    const plot = plotIn(card);
    const note = el('p', { class: 'table-note' }, card);
    note.appendChild(document.createTextNode(`${nf.format(pts.length)} days. The values for every day are in `));
    el('a', { href: 'data/demo.json' }, note, 'data/demo.json');
    note.appendChild(document.createTextNode('.'));
    drawers.push(() => scatter(plot, pts));
  }

  function renderQuality(data) {
    const q = data.quality;
    const totals = document.getElementById('quality-totals');
    const figures = [
      ['Rows in bronze', nf.format(q.bronze_rows), 'Trip rows loaded from the files'],
      ['Accepted', nf.format(q.accepted_rows), pct(q.accepted_rows, q.bronze_rows, 2) + ' of bronze rows'],
      ['Set aside (quarantined)', nf.format(q.quarantined_rows), pct(q.quarantined_rows, q.bronze_rows, 2) + ', each with a reason'],
      ['Rows lost', nf.format(q.bronze_rows - q.accepted_rows - q.quarantined_rows), 'Checked by a dbt test'],
    ];
    for (const [label, value, sub] of figures) {
      const box = el('div', {}, totals);
      el('p', { class: 'label' }, box, label);
      el('p', { class: 'value' }, box, value);
      el('p', { class: 'sub' }, box, sub);
    }
    const bar = document.getElementById('quality-bar');
    bar.setAttribute('aria-label', `${pct(q.accepted_rows, q.bronze_rows, 2)} of rows accepted, ${pct(q.quarantined_rows, q.bronze_rows, 2)} set aside`);
    const ok = el('div', { style: `flex:${q.accepted_rows} 1 0;background:var(--s1)` }, bar, `${pct(q.accepted_rows, q.bronze_rows, 2)} accepted`);
    ok.title = `Accepted: ${nf.format(q.accepted_rows)} rows`;
    const bad = el('div', { style: `flex:${q.quarantined_rows} 1 0;background:var(--s2)` }, bar);
    bad.title = `Set aside: ${nf.format(q.quarantined_rows)} rows`;
    const lg = document.getElementById('quality-legend');
    for (const [name, color] of [['Accepted into fct_trips', 'var(--s1)'], ['Set aside in trips_quarantine', 'var(--s2)']]) {
      const li = el('li', {}, lg);
      el('span', { class: 'key', style: `background:${color}` }, li);
      li.appendChild(document.createTextNode(name));
    }
    const tbody = document.querySelector('#quality-reasons tbody');
    for (const r of rowsOf(q.reasons)) {
      const tr = el('tr', {}, tbody);
      el('td', {}, tr, REASONS[r.rejection_reason] || r.rejection_reason);
      el('td', { class: 'num' }, tr, nf.format(r.row_count));
    }
    const foot = el('tr', {}, el('tfoot', {}, document.getElementById('quality-reasons')));
    el('td', {}, foot, 'Total set aside');
    el('td', { class: 'num' }, foot, nf.format(q.quarantined_rows));
  }

  function drawAll() {
    activeClear = null;
    tooltip.hidden = true;
    drawers.forEach((draw) => draw());
  }

  function start(data) {
    renderIntro(data);
    setupMonthly(data);
    setupStations(data);
    setupHours(data);
    setupDuration(data);
    setupWeather(data);
    setupScatter(data);
    renderQuality(data);
    drawAll();
    let lastWidth = window.innerWidth;
    let timer = null;
    window.addEventListener('resize', () => {
      if (window.innerWidth === lastWidth) return;
      lastWidth = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(drawAll, 120);
    });
  }

  fetch('data/demo.json')
    .then((r) => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(start)
    .catch((err) => {
      const box = el('p', { class: 'note' }, null, `The demo data could not be loaded (${err.message}).`);
      document.getElementById('stats').replaceWith(box);
    });
})();
