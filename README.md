# Malaysian Telco IDD Rate Scraper

Collects International Direct Dial (IDD) call and SMS rates from 8 Malaysian telecom brands into a single unified dataset (`data/idd.csv`), and visualises the results in an interactive D3.js dashboard.

## Repository structure

```
scraping/        Python scripts that scrape each telco brand
data/            Output CSVs, per-brand source files, and HTML snapshots
dashboard/       Interactive D3.js + Vite visualisation
METHODOLOGY.txt  Detailed per-brand scraping methodology
```

## Brands covered

| Brand | Script | Method |
|---|---|---|
| Yes | `scraping/extract_yes_idd.py` | Static JSON embedded in HTML |
| Hotlink | `scraping/run_hotlink_idd.py` | Playwright — Bootstrap tab navigation |
| Maxis | `scraping/run_maxis_idd.py` | Playwright |
| redONE | `scraping/run_redone_idd.py` | Playwright |
| U Mobile | `scraping/run_umobile_idd.py` | Playwright |
| CelcomDigi / Unifi | `scraping/scrape_celcomdigi_unifi_roaming.py` | Playwright |
| Others | `scraping/scrape_idd_remaining.py` | Playwright |

## Output schema (`data/idd.csv`)

| Column | Description |
|---|---|
| `record_id` | Sequential row number |
| `brand` | Telecom brand name |
| `country` | Destination country (normalised canonical name) |
| `region` | Geographic region (from `data/countries.csv` lookup) |
| `plan_type` | `prepaid`, `postpaid`, or `roaming` |
| `rate_per_min_myr` | Call rate to mobile, RM/min |
| `rate_fixed_per_min_myr` | Call rate to fixed/landline, RM/min |
| `rate_per_sms_myr` | SMS rate, RM/SMS |
| `notes` | Supplementary info (IDD codes, video call, MMS, dial instructions) |
| `source_url` | URL scraped |
| `scraped_at` | ISO 8601 scrape timestamp |

## Scraping setup

```bash
pip install playwright pandas beautifulsoup4
playwright install chromium
```

Run each brand's script, then consolidate:

```bash
cd scraping
python extract_yes_idd.py
python run_hotlink_idd.py
python run_maxis_idd.py
python run_redone_idd.py
python run_umobile_idd.py
python scrape_celcomdigi_unifi_roaming.py
python scrape_idd_remaining.py
python consolidate_idd.py
```

## Dashboard (D3.js)

```bash
cd dashboard
npm install
npm run dev      # opens at http://localhost:5173
```

4 pages mirroring the Power BI report:
- **Main dashboard** — world choropleth map, cost-per-GB bar chart, value vs price scatter, decision panel
- **EDA Q1** — Postpaid vs Prepaid comparison
- **EDA Q2** — Persona analysis
- **EDA Q3** — Malaysia plans characteristics

## Data files

- `data/idd.csv` — consolidated IDD rates (~3 000+ rows)
- `data/travelplans.csv.csv` — travel/roaming plan data (65 plans, 8 brands)
- `data/countries.csv` — country → region + network operators lookup
- `data/source/` — per-brand intermediate CSVs
- `data/html_debug/` — static HTML snapshots for offline country-list extraction

See [METHODOLOGY.txt](METHODOLOGY.txt) for detailed per-brand scraping notes.
