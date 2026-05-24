import * as d3 from 'd3';
import * as topojson from 'topojson-client';
import worldData from 'world-atlas/countries-110m.json';
import { BRAND_COLORS, ALPHA3_TO_NUM, NUM_TO_ALPHA3 } from './data.js';

// ── Shared tooltip ────────────────────────────────────────────────────────────
let _tip = null;
function tip() {
  if (!_tip) {
    _tip = d3.select('body').append('div').attr('class', 'd3-tooltip').style('opacity', 0);
  }
  return _tip;
}
function showTip(html, event) {
  tip().style('opacity', 1).html(html)
    .style('left', (event.clientX + 14) + 'px')
    .style('top', (event.clientY - 28) + 'px');
}
function hideTip() { tip().style('opacity', 0); }

// ── CHOROPLETH MAP ────────────────────────────────────────────────────────────
// Keep a module-level zoom instance so transitions survive re-renders
let _mapZoom = null;
let _mapSvg = null;

export function drawChoropleth(container, planCountByAlpha3, numToCountryName, onCountryClick, selectedCountryName) {
  const W = container.clientWidth || 680;
  const H = container.clientHeight || 340;

  // Only do a full DOM rebuild when the container is empty (first draw).
  // On subsequent calls we just update fills/strokes and animate the zoom.
  const alreadyDrawn = !!container.querySelector('svg');

  if (!alreadyDrawn) {
    d3.select(container).selectAll('*').remove();
    _mapSvg = null;
    _mapZoom = null;
  }

  const proj = d3.geoNaturalEarth1()
    .scale(W / 6.3)
    .translate([W / 2, H / 2 + 10]);
  const pathGen = d3.geoPath(proj);

  const maxCount = Math.max(...planCountByAlpha3.values(), 1);
  const colorScale = d3.scaleSequential([1, maxCount], d3.interpolateLab('#00bcd4', '#4a148c'));

  const countByNum = new Map();
  planCountByAlpha3.forEach((cnt, a3) => {
    const num = ALPHA3_TO_NUM[a3];
    if (num) countByNum.set(num, cnt);
  });

  // Resolve selected feature numeric id
  let selectedNum = null;
  if (selectedCountryName) {
    numToCountryName.forEach((name, num) => {
      if (name === selectedCountryName) selectedNum = num;
    });
  }

  const features = topojson.feature(worldData, worldData.objects.countries).features;
  const borders  = topojson.mesh(worldData, worldData.objects.countries, (a, b) => a !== b);

  // ── First-time DOM build ──────────────────────────────────────────────────
  if (!alreadyDrawn) {
    _mapSvg = d3.select(container).append('svg')
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('width', '100%').style('height', '100%');

    _mapSvg.append('rect').attr('class', 'ocean').attr('width', W).attr('height', H).attr('fill', '#e8f4f8');

    // Clip so zoomed paths don't spill outside the map area
    _mapSvg.append('defs').append('clipPath').attr('id', 'map-clip')
      .append('rect').attr('width', W).attr('height', H);

    const mapG = _mapSvg.append('g').attr('class', 'map-g').attr('clip-path', 'url(#map-clip)');

    mapG.selectAll('.country')
      .data(features)
      .join('path')
      .attr('class', 'country')
      .attr('d', pathGen);

    mapG.append('path').attr('class', 'borders').datum(borders)
      .attr('d', pathGen).attr('fill', 'none').attr('stroke', 'white').attr('stroke-width', 0.3);

    // Legend (outside clip, not affected by zoom)
    const lW = 120, lH = 8, lX = 12, lY = H - 24;
    const defs2 = _mapSvg.select('defs');
    const grad = defs2.append('linearGradient').attr('id', 'map-grad');
    grad.append('stop').attr('offset', '0%').attr('stop-color', '#00bcd4');
    grad.append('stop').attr('offset', '100%').attr('stop-color', '#4a148c');
    _mapSvg.append('rect').attr('x', lX).attr('y', lY).attr('width', lW).attr('height', lH)
      .attr('fill', 'url(#map-grad)').attr('rx', 2);
    _mapSvg.append('text').attr('x', lX).attr('y', lY - 3).attr('font-size', 9).attr('fill', '#555').text('Fewer plans');
    _mapSvg.append('text').attr('x', lX + lW).attr('y', lY - 3).attr('font-size', 9).attr('fill', '#555')
      .attr('text-anchor', 'end').text('More plans');

    // Reset-zoom button (appears when zoomed in)
    _mapSvg.append('text').attr('class', 'zoom-reset')
      .attr('x', W - 8).attr('y', 16).attr('text-anchor', 'end')
      .attr('font-size', 11).attr('fill', '#0078d4').attr('cursor', 'pointer')
      .style('display', 'none')
      .text('↩ Reset zoom')
      .on('click', () => { if (onCountryClick) onCountryClick(null); });

    // ── Zoom behavior ───────────────────────────────────────────────────────
    _mapZoom = d3.zoom()
      .scaleExtent([1, 20])
      .on('zoom', event => {
        mapG.attr('transform', event.transform);
        // Thin borders when zoomed in
        const s = event.transform.k;
        mapG.selectAll('.country').attr('stroke-width', Math.max(0.15, 0.5 / s));
        mapG.select('.borders').attr('stroke-width', Math.max(0.1, 0.3 / s));
      });

    _mapSvg.call(_mapZoom).on('dblclick.zoom', null); // disable dblclick reset
  }

  const svg = _mapSvg;

  // ── Update fill/stroke on every call ─────────────────────────────────────
  svg.select('.map-g').selectAll('.country')
    .attr('fill', d => {
      const cnt = countByNum.get(d.id);
      return cnt ? colorScale(cnt) : '#cfd8dc';
    })
    .attr('stroke', d => d.id === selectedNum ? '#ff6b35' : 'white')
    .attr('stroke-width', d => d.id === selectedNum ? 2 : 0.4)
    .style('cursor', d => countByNum.has(d.id) ? 'pointer' : 'default')
    .on('mouseover', (event, d) => {
      const cnt = countByNum.get(d.id);
      const name = numToCountryName.get(d.id) || 'Unknown';
      if (cnt) showTip(`<strong>${name}</strong><br>${cnt} plan(s) available`, event);
    })
    .on('mousemove', (event, d) => {
      if (countByNum.has(d.id)) tip().style('left', (event.clientX + 14) + 'px').style('top', (event.clientY - 28) + 'px');
    })
    .on('mouseout', hideTip)
    .on('click', (event, d) => {
      const name = numToCountryName.get(d.id);
      if (name && countByNum.has(d.id) && onCountryClick) onCountryClick(name);
    });

  // ── Zoom to selected country (or reset) ───────────────────────────────────
  if (selectedNum !== null) {
    const feat = features.find(f => f.id === selectedNum);
    if (feat) {
      const [[x0, y0], [x1, y1]] = pathGen.bounds(feat);
      const dx = x1 - x0 || 4;   // guard against point-like features
      const dy = y1 - y0 || 4;

      // Padding factor: 0.75 leaves breathing room around the country
      const scale = Math.min(15, 0.75 / Math.max(dx / W, dy / H));
      const tx = W / 2 - scale * (x0 + x1) / 2;
      const ty = H / 2 - scale * (y0 + y1) / 2;

      svg.transition().duration(750).ease(d3.easeCubicInOut)
        .call(_mapZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));

      svg.select('.zoom-reset').style('display', null);
    }
  } else {
    // No selection → smoothly reset to world view
    svg.transition().duration(600).ease(d3.easeCubicInOut)
      .call(_mapZoom.transform, d3.zoomIdentity);

    svg.select('.zoom-reset').style('display', 'none');
  }
}

// ── HORIZONTAL BAR CHART ──────────────────────────────────────────────────────
export function drawHBar(container, data, { xLabel = '', fmt = d => d } = {}) {
  // data: [{ brand, avg }] sorted cheapest first
  const W = container.clientWidth || 420;
  const margin = { top: 8, right: 80, bottom: 30, left: 80 };
  const barH = 22, gap = 6;
  const H = data.length * (barH + gap) + margin.top + margin.bottom;

  d3.select(container).selectAll('*').remove();
  const svg = d3.select(container).append('svg')
    .attr('width', W).attr('height', H);

  const innerW = W - margin.left - margin.right;
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  const xMax = d3.max(data, d => d.avg) * 1.15;
  const x = d3.scaleLinear([0, xMax], [0, innerW]);
  const y = d3.scaleBand(data.map(d => d.brand), [0, data.length * (barH + gap)]).paddingInner(0.25);

  // X axis
  const xAxis = d3.axisBottom(x).ticks(4).tickFormat(d => `RM${d}`);
  g.append('g').attr('class', 'axis').attr('transform', `translate(0,${H - margin.top - margin.bottom})`)
    .call(xAxis);

  // Gridlines
  g.append('g').attr('class', 'grid')
    .attr('transform', `translate(0,${H - margin.top - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(4).tickSize(-(H - margin.top - margin.bottom)).tickFormat(''))
    .select('.domain').remove();

  // Bars
  data.forEach((d, i) => {
    const yPos = i * (barH + gap);
    const color = BRAND_COLORS[d.brand] || '#aaa';

    g.append('rect')
      .attr('x', 0).attr('y', yPos)
      .attr('width', x(d.avg)).attr('height', barH)
      .attr('fill', color).attr('rx', 1);

    // Brand label (left)
    g.append('text')
      .attr('x', -6).attr('y', yPos + barH / 2)
      .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
      .attr('font-size', 11).attr('fill', '#252423')
      .text(d.brand);

    // Value label (right of bar)
    g.append('text')
      .attr('x', x(d.avg) + 5).attr('y', yPos + barH / 2)
      .attr('dominant-baseline', 'middle')
      .attr('font-size', 11).attr('fill', '#252423')
      .text(fmt(d.avg));
  });
}

// ── VERTICAL BAR CHART ────────────────────────────────────────────────────────
export function drawVBar(container, data, { yLabel = '', fmt = d => d, color = '#4db6e4', xKey = 'label', yKey = 'value' } = {}) {
  const W = container.clientWidth || 300;
  const H = container.clientHeight || 220;
  const margin = { top: 20, right: 10, bottom: 52, left: 48 };

  d3.select(container).selectAll('*').remove();
  const svg = d3.select(container).append('svg').attr('width', W).attr('height', H);
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const x = d3.scaleBand(data.map(d => d[xKey]), [0, innerW]).padding(0.25);
  const yMax = d3.max(data, d => d[yKey]);
  const y = d3.scaleLinear([0, yMax * 1.1], [innerH, 0]);

  // Gridlines
  g.append('g').attr('class', 'grid')
    .call(d3.axisLeft(y).ticks(4).tickSize(-innerW).tickFormat(''))
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick line').attr('stroke', '#f0f0f0'));

  // Axes
  g.append('g').attr('class', 'axis domain-hidden').attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickSize(0))
    .selectAll('text')
    .attr('transform', 'rotate(-30)').attr('text-anchor', 'end')
    .attr('dy', '0.5em').attr('dx', '-0.3em');

  g.append('g').attr('class', 'axis')
    .call(d3.axisLeft(y).ticks(4).tickFormat(d => `${fmt === 'rm' ? 'RM' : ''}${d}`));

  // Bars
  data.forEach(d => {
    const fill = typeof color === 'function' ? color(d) : color;
    g.append('rect')
      .attr('x', x(d[xKey])).attr('y', y(d[yKey]))
      .attr('width', x.bandwidth()).attr('height', innerH - y(d[yKey]))
      .attr('fill', fill).attr('rx', 1)
      .on('mouseover', ev => showTip(`<strong>${d[xKey]}</strong>: ${typeof fmt === 'function' ? fmt(d[yKey]) : d[yKey]}`, ev))
      .on('mouseout', hideTip);
  });

  if (yLabel) {
    svg.append('text').attr('transform', `rotate(-90)`).attr('x', -(H / 2)).attr('y', 12)
      .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#888').text(yLabel);
  }
}

// ── SCATTER PLOT ──────────────────────────────────────────────────────────────
export function drawScatter(container, plans, { xKey = 'tvs', yKey = 'price_myr', colorKey = 'brand',
  xLabel = 'Travel Value Score', yLabel = 'Price (MYR)',
  showQuadrant = false, quadrantX = 70, quadrantY = 75,
  colorMap = BRAND_COLORS, onDotClick = null } = {}) {

  const W = container.clientWidth || 420;
  const H = container.clientHeight || 300;
  const margin = { top: 10, right: 14, bottom: 40, left: 56 };

  d3.select(container).selectAll('*').remove();
  const svg = d3.select(container).append('svg').attr('width', W).attr('height', H);
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const xVals = plans.map(d => +d[xKey]).filter(v => isFinite(v));
  const yVals = plans.map(d => +d[yKey]).filter(v => isFinite(v));
  const xMax = d3.max(xVals) * 1.08 || 100;
  const yMax = d3.max(yVals) * 1.1 || 200;

  const x = d3.scaleLinear([0, xMax], [0, innerW]);
  const y = d3.scaleLinear([0, yMax], [innerH, 0]);

  // Grid
  g.append('g').attr('class', 'grid')
    .call(d3.axisLeft(y).ticks(5).tickSize(-innerW).tickFormat(''))
    .call(g => g.select('.domain').remove())
    .call(g => g.selectAll('.tick line').attr('stroke', '#f0f0f0'));

  // Sweet-spot quadrant shading
  if (showQuadrant) {
    g.append('rect')
      .attr('class', 'sweet-spot-bg')
      .attr('x', x(quadrantX)).attr('y', y(quadrantY))
      .attr('width', innerW - x(quadrantX))
      .attr('height', innerH - y(quadrantY));

    g.append('line').attr('class', 'quadrant-line')
      .attr('x1', x(quadrantX)).attr('x2', x(quadrantX))
      .attr('y1', 0).attr('y2', innerH);
    g.append('line').attr('class', 'quadrant-line')
      .attr('x1', 0).attr('x2', innerW)
      .attr('y1', y(quadrantY)).attr('y2', y(quadrantY));
  }

  // Axes
  g.append('g').attr('class', 'axis').attr('transform', `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(5));
  g.append('g').attr('class', 'axis')
    .call(d3.axisLeft(y).ticks(5).tickFormat(d => `RM${d}`));

  // Axis labels
  svg.append('text').attr('x', margin.left + innerW / 2).attr('y', H - 4)
    .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#888').text(xLabel);
  svg.append('text').attr('transform', 'rotate(-90)')
    .attr('x', -(margin.top + innerH / 2)).attr('y', 14)
    .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#888').text(yLabel);

  // Dots
  plans.forEach(d => {
    const xv = +d[xKey], yv = +d[yKey];
    if (!isFinite(xv) || !isFinite(yv)) return;
    const color = colorMap[d[colorKey]] || '#aaa';
    const inSweetSpot = showQuadrant && xv >= quadrantX && yv <= quadrantY;
    const r = inSweetSpot ? 7 : 4.5;

    const circle = g.append('circle')
      .attr('class', 'scatter-dot')
      .attr('cx', x(xv)).attr('cy', y(yv)).attr('r', r)
      .attr('fill', color).attr('fill-opacity', 0.82)
      .attr('stroke', inSweetSpot ? 'white' : 'none').attr('stroke-width', 1.5);

    if (onDotClick) circle.on('click', () => onDotClick(d));

    circle
      .on('mouseover', ev => {
        showTip(
          `<strong>${d.plan_name || d[colorKey]}</strong><br>${d[colorKey]}<br>${xLabel}: ${xv.toFixed(1)}<br>Price: RM${yv}`,
          ev
        );
      })
      .on('mouseout', hideTip);
  });

  // Legend (brands or persona)
  const legendKeys = [...new Set(plans.map(d => d[colorKey]).filter(Boolean))].sort();
  const lG = svg.append('g').attr('transform', `translate(${margin.left + 4}, ${margin.top + 2})`);
  let lx = 0;
  legendKeys.forEach(k => {
    const lItem = lG.append('g').attr('transform', `translate(${lx},0)`);
    lItem.append('circle').attr('r', 4).attr('cy', 4).attr('fill', colorMap[k] || '#aaa');
    lItem.append('text').attr('x', 8).attr('y', 8).attr('font-size', 9).attr('fill', '#555').text(k);
    lx += k.length * 5.8 + 18;
    if (lx > innerW - 60) lx = 0; // wrap
  });
}

// ── DONUT CHART ───────────────────────────────────────────────────────────────
export function drawDonut(container, data, { colorMap = null, title = '' } = {}) {
  // data: [{ label, value }]
  const W = container.clientWidth || 240;
  const H = container.clientHeight || 200;
  const radius = Math.min(W * 0.45, H * 0.42);
  const cx = W * 0.42, cy = H / 2;

  d3.select(container).selectAll('*').remove();
  const svg = d3.select(container).append('svg').attr('width', W).attr('height', H);

  const colors = colorMap
    ? d => colorMap[d.data.label] || '#ccc'
    : d3.scaleOrdinal(d3.schemeTableau10);

  const pie = d3.pie().sort(null).value(d => d.value)(data);
  const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
  const arcHover = d3.arc().innerRadius(radius * 0.55).outerRadius(radius * 1.04);

  const g = svg.append('g').attr('transform', `translate(${cx},${cy})`);

  const total = d3.sum(data, d => d.value);

  g.selectAll('.arc')
    .data(pie)
    .join('path')
    .attr('class', 'arc')
    .attr('d', arc)
    .attr('fill', typeof colors === 'function' ? colors : d => colors(d.data.label))
    .attr('stroke', 'white').attr('stroke-width', 2)
    .on('mouseover', function(event, d) {
      d3.select(this).attr('d', arcHover);
      const pct = ((d.data.value / total) * 100).toFixed(1);
      showTip(`<strong>${d.data.label}</strong><br>${d.data.value} (${pct}%)`, event);
    })
    .on('mousemove', ev => tip().style('left', (ev.clientX + 14) + 'px').style('top', (ev.clientY - 28) + 'px'))
    .on('mouseout', function() { d3.select(this).attr('d', arc); hideTip(); });

  // Center label
  if (title) {
    g.append('text').attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', 11).attr('fill', '#666').text(title);
  }

  // Legend (right side)
  const legendX = cx + radius + 14;
  const lineH = 16;
  const startY = cy - (data.length * lineH) / 2;

  data.forEach((d, i) => {
    const pct = ((d.value / total) * 100).toFixed(1);
    const fillColor = typeof colors === 'function' ? colors(pie[i]) : colors(d.label);
    const gy = startY + i * lineH;

    svg.append('circle').attr('cx', legendX + 5).attr('cy', gy + 5).attr('r', 5).attr('fill', fillColor);
    svg.append('text').attr('x', legendX + 14).attr('y', gy + 9).attr('font-size', 10).attr('fill', '#252423')
      .text(d.label);
    svg.append('text').attr('x', legendX + 14).attr('y', gy + 20).attr('font-size', 9).attr('fill', '#888')
      .text(`${d.value} (${pct}%)`);
  });
}
