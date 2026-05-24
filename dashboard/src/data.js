import * as d3 from 'd3';

// ── Brand name normalization ──────────────────────────────────────────────────
const BRAND_NORM = { TuneTalk: 'Tune Talk', umobile: 'U Mobile', unifi: 'Unifi', redOne: 'redONE' };
export function normalizeBrand(b) { return BRAND_NORM[b] || b; }

export const BRAND_COLORS = {
  CelcomDigi: '#F5A623', Hotlink: '#C2185B', Maxis: '#388E3C',
  redONE: '#D32F2F', 'Tune Talk': '#0097A7', 'U Mobile': '#E64A19',
  Unifi: '#1A237E', Yes: '#F9A825'
};

export const PERSONA_COLORS = {
  'Casual Roamer': '#1565C0', 'Frequent ASEAN Traveller': '#AD1457',
  'Global Executive': '#E65100', 'Hajj/Umrah Pilgrim': '#2E7D32',
  'Inbound Tourist': '#4527A0', 'Regional Hopper': '#006064'
};

export const PERSONAS = [
  'Casual Roamer', 'Global Executive', 'Inbound Tourist',
  'Frequent ASEAN Traveller', 'Hajj/Umrah Pilgrim', 'Regional Hopper'
];

// ── Score helpers ─────────────────────────────────────────────────────────────
function callsScore(c) {
  if (c === 'Unlimited') return 1;
  if (c === '30min/day') return 0.5;
  if (c === '15min/day') return 0.25;
  return 0;
}
function hotspotScore(h) {
  if (h === 'Unlimited') return 1;
  if (h === 'Enabled') return 0.5;
  if (h === '10GB 4G/5G') return 0.25;
  return 0;
}

// ── ISO alpha-3 → ISO numeric (world-atlas feature IDs) ──────────────────────
export const ALPHA3_TO_NUM = {
  ABW:533,AFG:4,AGO:24,ALB:8,AND:20,ARE:784,ARG:32,ARM:51,
  ASM:16,ATG:28,AUS:36,AUT:40,AZE:31,BDI:108,BEL:56,BEN:204,
  BFA:854,BGD:50,BGR:100,BHR:48,BHS:44,BIH:70,BLR:112,BLZ:84,
  BMU:60,BOL:68,BRA:76,BRB:52,BRN:96,BTN:64,BWA:72,CAF:140,
  CAN:124,CHE:756,CHL:152,CHN:156,CIV:384,CMR:120,COD:180,COG:178,
  COK:184,COL:170,COM:174,CPV:132,CRI:188,CUB:192,CYM:136,CYP:196,
  CZE:203,DEU:276,DJI:262,DMA:212,DNK:208,DOM:214,DZA:12,ECU:218,
  EGY:818,ERI:232,ESP:724,EST:233,ETH:231,FIN:246,FJI:242,FLK:238,
  FRA:250,FSM:583,GAB:266,GBR:826,GEO:268,GHA:288,GIN:324,GMB:270,
  GNB:624,GNQ:226,GRC:300,GRD:308,GRL:304,GTM:320,GUY:328,HKG:344,
  HND:340,HRV:191,HTI:332,HUN:348,IDN:360,IND:356,IRL:372,IRN:364,
  IRQ:368,ISL:352,ISR:376,ITA:380,JAM:388,JOR:400,JPN:392,KAZ:398,
  KEN:404,KGZ:417,KHM:116,KIR:296,KNA:659,KOR:410,KWT:414,LAO:418,
  LBN:422,LBR:430,LBY:434,LCA:662,LIE:438,LKA:144,LSO:426,LTU:440,
  LUX:442,LVA:428,MAC:446,MAR:504,MCO:492,MDA:498,MDG:450,MDV:462,
  MEX:484,MHL:584,MKD:807,MLI:466,MLT:470,MMR:104,MNE:499,MNG:496,
  MOZ:508,MRT:478,MUS:480,MWI:454,MYS:458,MYT:175,NAM:516,NCL:540,
  NER:562,NGA:566,NIC:558,NLD:528,NOR:578,NPL:524,NRU:520,NZL:554,
  OMN:512,PAK:586,PAN:591,PER:604,PHL:608,PLW:585,PNG:598,POL:616,
  PRK:408,PRT:620,PRY:600,PSE:275,QAT:634,ROU:642,RUS:643,RWA:646,
  SAU:682,SDN:729,SEN:686,SGP:702,SLB:90,SLE:694,SLV:222,SMR:674,
  SOM:706,SRB:688,SSD:728,STP:678,SUR:740,SVK:703,SVN:705,SWE:752,
  SWZ:748,SYC:690,SYR:760,TCD:148,TGO:768,THA:764,TJK:762,TKM:795,
  TLS:626,TON:776,TTO:780,TUN:788,TUR:792,TUV:798,TWN:158,TZA:834,
  UGA:800,UKR:804,URY:858,USA:840,UZB:860,VAT:336,VCT:670,VEN:862,
  VNM:704,VUT:548,WSM:882,YEM:887,ZAF:710,ZMB:894,ZWE:716,
  // Territories that appear in our data
  GLP:312,MTQ:474,REU:638,PYF:258,ATF:260,SPM:666,WLF:876,
  COK:184,NIU:570,NFK:574,CXR:162,CCK:166,
};

// Build reverse: numeric → alpha3
export const NUM_TO_ALPHA3 = Object.fromEntries(
  Object.entries(ALPHA3_TO_NUM).map(([a3, num]) => [num, a3])
);

// ── Data cache ────────────────────────────────────────────────────────────────
let _cache = null;

export async function loadData() {
  if (_cache) return _cache;

  const [rawPlans, rawCountries, rawIdd] = await Promise.all([
    d3.csv('/data/travelplans.csv.csv'),
    d3.csv('/data/countries.csv'),
    d3.csv('/data/idd.csv'),
  ]);

  // ── Process travelplans ───────────────────────────────────────────────────
  const plans = rawPlans.map(d => {
    const brand = normalizeBrand(d.brand);
    const pp = (d['prepaid/postpaud'] || '').toLowerCase();
    const prepaidPostpaid = pp === 'postpaid' ? 'postpaid' : pp === 'both' ? 'both' : 'prepaid';
    const countriesArr = d.countries_covered
      ? d.countries_covered.split('|').map(c => c.trim()).filter(Boolean)
      : [];
    return {
      travel_plan_id: d.travel_plan_id,
      brand,
      plan_name: d.plan_name,
      direction: d.direction,
      price_myr: +d.price_myr || 0,
      validity_days: +d.validity_days || 0,
      data_gb_malaysia: +d.data_gb_malaysia || 0,
      data_gb_roaming: +d.data_gb_roaming || 0,
      prepaid_postpaid: prepaidPostpaid,
      countries_covered: d.countries_covered,
      countries_arr: countriesArr,
      country_count: +d.country_count || countriesArr.length,
      hotspot: d.hotspot || 'No',
      calls: d.calls || 'No',
      includes_travel_insurance: d.includes_travel_insurance || 'No',
      unique_benefits: d.unique_benefits || '',
      best_for_persona: d.best_for_persona,
      source_url: d.source_url,
    };
  });

  // Compute normalisation maxima
  const maxData = d3.max(plans, d => d.data_gb_roaming) || 1;
  const maxCountries = d3.max(plans, d => d.country_count) || 1;
  const maxValidity = d3.max(plans, d => d.validity_days) || 1;

  // Derived metrics
  plans.forEach(p => {
    p.price_per_gb = p.data_gb_roaming > 0 ? +(p.price_myr / p.data_gb_roaming).toFixed(2) : null;
    p.price_per_day = p.validity_days > 0 ? +(p.price_myr / p.validity_days).toFixed(2) : null;
    p.tvs = +(
      Math.min(p.data_gb_roaming / maxData, 1) * 30 +
      Math.min(p.country_count / maxCountries, 1) * 25 +
      callsScore(p.calls) * 15 +
      Math.min(p.validity_days / maxValidity, 1) * 15 +
      hotspotScore(p.hotspot) * 10 +
      (p.includes_travel_insurance === 'Yes' ? 1 : 0) * 5
    ).toFixed(1);
  });

  // ── Process countries ─────────────────────────────────────────────────────
  const countries = rawCountries.map(d => ({ ...d }));
  const countryByName = new Map();
  countries.forEach(c => {
    countryByName.set(c.country.toLowerCase(), c);
    // common aliases
    if (c.country === 'Viet Nam') countryByName.set('vietnam', c);
    if (c.country === 'Lao PDR' || c.country === "Lao People's Democratic Republic") countryByName.set('laos', c);
    if (c.country === 'Republic of Korea' || c.country === 'Korea, Republic of') countryByName.set('south korea', c);
    if (c.country === 'Macao') countryByName.set('macau', c);
    if (c.country === 'Brunei Darussalam') countryByName.set('brunei', c);
    if (c.country === 'Taiwan, Province of China') countryByName.set('taiwan', c);
    if (c.country === "Côte d'Ivoire") countryByName.set("ivory coast", c);
    if (c.country === 'Syrian Arab Republic') countryByName.set('syria', c);
    if (c.country === "Democratic Republic of the Congo") countryByName.set('dr congo', c);
    if (c.country === "Iran, Islamic Republic of") countryByName.set('iran', c);
    if (c.country === "Russian Federation") countryByName.set('russia', c);
    if (c.country === "United Kingdom") countryByName.set('uk', c);
    if (c.country === "United States") countryByName.set('usa', c);
    if (c.country === "Bolivia (Plurinational State of)") countryByName.set('bolivia', c);
    if (c.country === "Venezuela (Bolivarian Republic of)") countryByName.set('venezuela', c);
    if (c.country === "Tanzania, United Republic of") countryByName.set('tanzania', c);
    if (c.country === "Myanmar") countryByName.set('burma', c);
    if (c.country === "North Macedonia") countryByName.set('macedonia', c);
    if (c.country === "Timor-Leste") countryByName.set('east timor', c);
    if (c.country === "Türkiye") countryByName.set('turkey', c);
    if (c.country === "Eswatini") countryByName.set('swaziland', c);
  });

  // ── Process IDD ───────────────────────────────────────────────────────────
  const idd = rawIdd.map(d => ({
    ...d,
    brand: normalizeBrand(d.brand),
    rate_mobile: +d.rate_per_min_myr || 0,
    rate_fixed: +d.rate_fixed_per_min_myr || 0,
    rate_sms: +d.rate_per_sms_myr || 0,
  }));

  // ── Bridge table: plan_id ↔ country ──────────────────────────────────────
  const bridge = [];
  plans.forEach(p => {
    p.countries_arr.forEach(country => {
      bridge.push({ travel_plan_id: p.travel_plan_id, country, brand: p.brand });
    });
  });

  // Count plans per country name
  const planCountByCountry = new Map();
  bridge.forEach(r => {
    planCountByCountry.set(r.country, (planCountByCountry.get(r.country) || 0) + 1);
  });

  // Map country name → iso_alpha3 → numeric, for choropleth
  const planCountByAlpha3 = new Map();
  planCountByCountry.forEach((count, name) => {
    const cobj = countryByName.get(name.toLowerCase());
    if (cobj && cobj.iso_alpha3) {
      planCountByAlpha3.set(cobj.iso_alpha3, (planCountByAlpha3.get(cobj.iso_alpha3) || 0) + count);
    }
  });

  // numeric → country name (for map click → name lookup)
  const numToCountryName = new Map();
  countries.forEach(c => {
    if (c.iso_alpha3 && ALPHA3_TO_NUM[c.iso_alpha3]) {
      numToCountryName.set(ALPHA3_TO_NUM[c.iso_alpha3], c.country);
    }
  });

  // All unique destination country names (for dropdown)
  const destCountries = [...new Set(bridge.map(r => r.country))].sort();

  _cache = { plans, countries, idd, bridge, countryByName, planCountByCountry, planCountByAlpha3, numToCountryName, destCountries };
  return _cache;
}

// ── Aggregation helpers ───────────────────────────────────────────────────────

export function getPricePerGBByBrand(plans) {
  const grouped = d3.group(plans.filter(p => p.price_per_gb != null), d => d.brand);
  return Array.from(grouped, ([brand, ps]) => ({
    brand,
    avg: +d3.mean(ps, d => d.price_per_gb).toFixed(2),
  })).sort((a, b) => a.avg - b.avg); // cheapest first (appears at top)
}

export function getRecommendedPlan(plans, selectedCountry, selectedPersona, tripDays) {
  let pool = plans.slice();
  if (selectedCountry) pool = pool.filter(p => p.countries_arr.includes(selectedCountry));
  if (selectedPersona) pool = pool.filter(p => p.best_for_persona === selectedPersona);

  if (tripDays > 1) {
    const valid = pool.filter(p => p.validity_days >= tripDays);
    if (valid.length > 0) {
      const minV = d3.min(valid, d => d.validity_days);
      pool = valid.filter(p => p.validity_days === minV);
    }
  }

  if (!pool.length) return null;
  return pool.reduce((best, p) => (!best || p.tvs > best.tvs || (p.tvs === best.tvs && p.price_myr < best.price_myr)) ? p : best, null);
}

export function getCheapestIDD(idd, selectedCountry) {
  const relevant = selectedCountry ? idd.filter(d => d.country === selectedCountry) : idd;
  if (!relevant.length) return null;
  const grouped = d3.group(relevant.filter(d => d.rate_mobile > 0), d => d.brand);
  const stats = Array.from(grouped, ([brand, rows]) => ({
    brand,
    avgMobile: +d3.mean(rows, d => d.rate_mobile).toFixed(2),
    avgFixed:  +d3.mean(rows, d => d.rate_fixed).toFixed(2),
    avgSMS:    +d3.mean(rows, d => d.rate_sms).toFixed(2),
  })).filter(d => d.avgMobile > 0);
  if (!stats.length) return null;
  return stats.sort((a, b) => a.avgMobile - b.avgMobile)[0];
}
