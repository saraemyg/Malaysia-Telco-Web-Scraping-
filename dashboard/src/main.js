import { loadData, getPricePerGBByBrand, getRecommendedPlan, getCheapestIDD, PERSONAS, BRAND_COLORS } from './data.js';
import { drawChoropleth, drawHBar, drawScatter } from './charts.js';

// ── App state ─────────────────────────────────────────────────────────────────
const state = { country: '', persona: '', tripDays: 1 };

async function main() {
  const data = await loadData();
  const { plans, countries, idd, destCountries, planCountByAlpha3, numToCountryName, countryByName } = data;

  // ── Populate country dropdown ───────────────────────────────────────────────
  const sel = document.getElementById('country-select');
  destCountries.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c; opt.textContent = c;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', () => { state.country = sel.value; update(); });

  // ── Trip Days slider ────────────────────────────────────────────────────────
  const slider = document.getElementById('trip-slider');
  const numInput = document.getElementById('trip-input');
  slider.addEventListener('input', () => { numInput.value = slider.value; state.tripDays = +slider.value; update(); });
  numInput.addEventListener('change', () => { slider.value = numInput.value; state.tripDays = +numInput.value; update(); });

  // ── Persona buttons ─────────────────────────────────────────────────────────
  const personaGrid = document.getElementById('persona-grid');
  PERSONAS.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'persona-btn'; btn.dataset.persona = p; btn.textContent = p;
    btn.addEventListener('click', () => {
      state.persona = state.persona === p ? '' : p;
      document.querySelectorAll('.persona-btn').forEach(b => b.classList.toggle('active', b.dataset.persona === state.persona));
      update();
    });
    personaGrid.appendChild(btn);
  });

  // ── Map click handler ───────────────────────────────────────────────────────
  function onMapCountryClick(countryName) {
    if (state.country === countryName) {
      state.country = '';
      sel.value = '';
    } else {
      state.country = countryName;
      sel.value = countryName;
    }
    update();
  }

  // ── Initial render ──────────────────────────────────────────────────────────
  update();

  // ── Main update function ────────────────────────────────────────────────────
  function update() {
    const { country, persona, tripDays } = state;

    // Filter plans for charts
    let filtered = plans.slice();
    if (country) filtered = filtered.filter(p => p.countries_arr.includes(country));
    if (persona) filtered = filtered.filter(p => p.best_for_persona === persona);

    // Dynamic title
    document.getElementById('dynamic-title').textContent = country
      ? `Travel to ${country} — Best Plans for Malaysians`
      : 'Pack Your SIM — Best Travel Plans for Malaysians';

    // KPI cards
    const uniqueBrands = new Set(filtered.map(p => p.brand));
    document.getElementById('kpi-plans').textContent = filtered.length;
    document.getElementById('kpi-brands').textContent = uniqueBrands.size;

    // ── Choropleth ────────────────────────────────────────────────────────────
    const mapEl = document.getElementById('map-container');
    drawChoropleth(mapEl, planCountByAlpha3, numToCountryName, onMapCountryClick, country || null);

    // ── Bar chart: cost per GB by brand ───────────────────────────────────────
    const barData = getPricePerGBByBrand(filtered);
    const barEl = document.getElementById('bar-chart');
    const barH = barData.length * 28 + 48;
    barEl.style.height = barH + 'px';
    drawHBar(barEl, barData, { fmt: d => `RM${d.toFixed(2)}` });

    // ── Scatter: TVS vs Price ─────────────────────────────────────────────────
    const scatterEl = document.getElementById('scatter-chart');
    drawScatter(scatterEl, filtered, {
      xKey: 'tvs', yKey: 'price_myr', colorKey: 'brand',
      xLabel: 'Travel Value Score', yLabel: 'Price (MYR)',
      showQuadrant: true, quadrantX: 70, quadrantY: 75,
      colorMap: BRAND_COLORS,
      onDotClick: (plan) => updateDecisionWithPlan(plan, idd, countryByName, country),
    });

    // ── Decision panel ────────────────────────────────────────────────────────
    const rec = getRecommendedPlan(filtered, country, persona, tripDays);
    updateDecisionWithPlan(rec, idd, countryByName, country);
  }

  function updateDecisionWithPlan(plan, idd, countryByName, country) {
    const recEl = document.getElementById('rec-plan-val');
    if (plan) {
      recEl.innerHTML = `<strong>${plan.plan_name}</strong><br>RM${plan.price_myr} / ${plan.validity_days}d · ${plan.brand}`;
    } else {
      recEl.innerHTML = '<span style="color:#aaa">No matching plan</span>';
    }

    // Countries reachable = plan.country_count of recommended plan
    document.getElementById('countries-reach-val').textContent = plan ? plan.country_count : '—';

    // Cheapest IDD
    const cheapIdd = getCheapestIDD(idd, country || null);
    const iddEl = document.getElementById('idd-val');
    if (cheapIdd) {
      iddEl.innerHTML = `
        <div class="ic-idd-brand">${cheapIdd.brand} (Global Leader)</div>
        <div class="ic-idd-rate">• Avg Mobile Rate: RM${cheapIdd.avgMobile}/min</div>
        <div class="ic-idd-rate">• Avg Fixed Rate: RM${cheapIdd.avgFixed}/min</div>
        <div class="ic-idd-rate">• Avg SMS Rate: RM${cheapIdd.avgSMS}/sms</div>`;
    } else {
      iddEl.innerHTML = '<span style="color:#aaa">—</span>';
    }

    // Network operators
    const netEl = document.getElementById('net-ops-val');
    if (country) {
      const cobj = countryByName.get(country.toLowerCase());
      netEl.textContent = cobj ? (cobj.network_operators || '—') : '—';
    } else {
      netEl.textContent = 'Select a country';
    }
  }
}

main();
