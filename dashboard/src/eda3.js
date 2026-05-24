import * as d3 from 'd3';
import { loadData } from './data.js';
import { drawDonut, drawScatter } from './charts.js';

async function main() {
  const { plans } = await loadData();

  // Plans with Malaysia data (data_gb_malaysia > 0)
  const myPlans = plans.filter(p => p.data_gb_malaysia > 0);

  // ── Donut: calls breakdown ─────────────────────────────────────────────────
  const callsCounts = d3.rollup(myPlans, v => v.length, d => d.calls);
  const callsData = [
    { label: 'Unlimited', value: callsCounts.get('Unlimited') || 0 },
    { label: 'No',        value: callsCounts.get('No')        || 0 },
    { label: 'Yes',       value: (callsCounts.get('Yes') || 0) + (callsCounts.get('15min/day') || 0) + (callsCounts.get('30min/day') || 0) },
  ].filter(d => d.value > 0);
  const callsColors = { Unlimited: '#4db6e4', No: '#1a237e', Yes: '#E64A19' };
  drawDonut(document.getElementById('donut-calls'), callsData, { colorMap: callsColors });

  // ── Donut: hotspot breakdown ───────────────────────────────────────────────
  const hotspotCounts = d3.rollup(myPlans, v => v.length, d => d.hotspot);
  const hotspotData = [
    { label: 'Unlimited',   value: hotspotCounts.get('Unlimited')   || 0 },
    { label: 'Enabled',     value: hotspotCounts.get('Enabled')     || 0 },
    { label: 'No',          value: hotspotCounts.get('No')          || 0 },
    { label: '10GB 4G/5G',  value: hotspotCounts.get('10GB 4G/5G') || 0 },
  ].filter(d => d.value > 0);
  const hotspotColors = { Unlimited: '#4db6e4', Enabled: '#4a148c', No: '#E64A19', '10GB 4G/5G': '#E64A19' };
  drawDonut(document.getElementById('donut-hotspot'), hotspotData, { colorMap: hotspotColors });

  // ── Scatter: Malaysia data vs price ───────────────────────────────────────
  drawScatter(document.getElementById('scatter-data-my'), myPlans, {
    xKey: 'price_myr', yKey: 'data_gb_malaysia',
    colorKey: 'brand', xLabel: 'price_myr', yLabel: 'data_gb_malaysia',
  });

  // ── Scatter: validity days vs price ───────────────────────────────────────
  drawScatter(document.getElementById('scatter-validity-my'), myPlans, {
    xKey: 'price_myr', yKey: 'validity_days',
    colorKey: 'brand', xLabel: 'price_myr', yLabel: 'validity_days',
  });

  // ── Donut: prepaid/postpaid (Malaysia plans) ──────────────────────────────
  const ppCounts = d3.rollup(myPlans, v => v.length, d => d.prepaid_postpaid);
  const ppData = [
    { label: 'prepaid',  value: ppCounts.get('prepaid')  || 0 },
    { label: 'postpaid', value: ppCounts.get('postpaid') || 0 },
  ].filter(d => d.value > 0);
  const ppColors = { prepaid: '#4db6e4', postpaid: '#1a237e' };
  drawDonut(document.getElementById('donut-pp-my'), ppData, { colorMap: ppColors });
}

main();
