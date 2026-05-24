import * as d3 from 'd3';
import { loadData } from './data.js';
import { drawDonut, drawVBar } from './charts.js';

async function main() {
  const { plans } = await loadData();

  // ── Donut: proportion of prepaid/postpaid ─────────────────────────────────
  const ppCounts = d3.rollup(plans, v => v.length, d => d.prepaid_postpaid);
  const ppData = [
    { label: 'prepaid',  value: ppCounts.get('prepaid')  || 0 },
    { label: 'postpaid', value: ppCounts.get('postpaid') || 0 },
    { label: 'both',     value: ppCounts.get('both')     || 0 },
  ].filter(d => d.value > 0);

  const ppColors = { prepaid: '#4db6e4', postpaid: '#1a237e', both: '#E64A19' };
  drawDonut(document.getElementById('donut-pp'), ppData, { colorMap: ppColors });

  // ── Helper: avg metric by pp category ────────────────────────────────────
  function avgByPP(metric) {
    return ['prepaid', 'postpaid', 'both']
      .map(cat => ({
        label: cat,
        value: +d3.mean(plans.filter(p => p.prepaid_postpaid === cat), d => d[metric]).toFixed(2) || 0,
      }))
      .filter(d => d.value > 0);
  }

  const ppColor = d => ppColors[d.label] || '#4db6e4';

  drawVBar(document.getElementById('bar-price'),
    avgByPP('price_myr'),
    { yLabel: 'Average of price_myr', fmt: 'rm', xKey: 'label', yKey: 'value', color: ppColor });

  drawVBar(document.getElementById('bar-roaming'),
    avgByPP('data_gb_roaming'),
    { yLabel: 'Average of data_gb_roaming', xKey: 'label', yKey: 'value', color: ppColor });

  drawVBar(document.getElementById('bar-malaysia'),
    avgByPP('data_gb_malaysia'),
    { yLabel: 'Average of data_gb_malaysia', xKey: 'label', yKey: 'value', color: ppColor });
}

main();
