import * as d3 from 'd3';
import { loadData, PERSONA_COLORS, PERSONAS } from './data.js';
import { drawVBar, drawScatter } from './charts.js';

async function main() {
  const { plans } = await loadData();

  // ── Bar: count of plans per persona ──────────────────────────────────────
  const countByPersona = PERSONAS.map(p => ({
    label: p,
    value: plans.filter(pl => pl.best_for_persona === p).length,
  }));
  drawVBar(document.getElementById('bar-count-persona'), countByPersona, {
    yLabel: 'Count of plan_name', xKey: 'label', yKey: 'value',
    color: d => PERSONA_COLORS[d.label] || '#4db6e4',
  });

  // ── Bar: avg price per persona ────────────────────────────────────────────
  const avgPriceByPersona = PERSONAS.map(p => {
    const ps = plans.filter(pl => pl.best_for_persona === p);
    return { label: p, value: +d3.mean(ps, d => d.price_myr).toFixed(2) || 0 };
  });
  drawVBar(document.getElementById('bar-avg-price-persona'), avgPriceByPersona, {
    yLabel: 'Average of price_myr', fmt: 'rm', xKey: 'label', yKey: 'value',
    color: d => PERSONA_COLORS[d.label] || '#4db6e4',
  });

  // ── Scatter plots (color by persona) ─────────────────────────────────────
  const plansWithPersona = plans.filter(p => p.best_for_persona);

  drawScatter(document.getElementById('scatter-roaming'), plansWithPersona, {
    xKey: 'price_myr', yKey: 'data_gb_roaming',
    colorKey: 'best_for_persona', colorMap: PERSONA_COLORS,
    xLabel: 'price_myr', yLabel: 'data_gb_roaming',
  });

  drawScatter(document.getElementById('scatter-country'), plansWithPersona, {
    xKey: 'price_myr', yKey: 'country_count',
    colorKey: 'best_for_persona', colorMap: PERSONA_COLORS,
    xLabel: 'price_myr', yLabel: 'country_count',
  });

  drawScatter(document.getElementById('scatter-validity'), plansWithPersona, {
    xKey: 'price_myr', yKey: 'validity_days',
    colorKey: 'best_for_persona', colorMap: PERSONA_COLORS,
    xLabel: 'price_myr', yLabel: 'validity_days',
  });
}

main();
