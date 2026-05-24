# Malaysian Telco IDD Rate Scraper

Collects International Direct Dial (IDD) call and SMS rates from 8 Malaysian telecom brands into a single unified dataset (`data/idd.csv`).

## Brands covered

| Brand | Script | Method |
|---|---|---|
| Yes | `extract_yes_idd.py` | Static JSON embedded in HTML |
| Hotlink | `run_hotlink_idd.py` | Playwright — Bootstrap tab navigation |
| Maxis | `run_maxis_idd.py` | Playwright |
| Redone | `run_redone_idd.py` | Playwright |
| U Mobile | `run_umobile_idd.py` | Playwright |
| CelcomDigi / Unifi | `scrape_celcomdigi_unifi_roaming.py` | Playwright |
| Others (remaining) | `scrape_idd_remaining.py` | Playwright |

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

## Setup

```bash
pip install playwright pandas beautifulsoup4
playwright install chromium
```

## Usage

Run each brand's script individually:

```bash
python extract_yes_idd.py
python run_hotlink_idd.py
python run_maxis_idd.py
python run_redone_idd.py
python run_umobile_idd.py
python scrape_celcomdigi_unifi_roaming.py
python scrape_idd_remaining.py
```

Then consolidate all brand CSVs into the final dataset:

```bash
python consolidate_idd.py
```

## Data files

- `data/idd.csv` — consolidated output (~3 000+ rows)
- `data/countries.csv` — country → region lookup table
- `data/travelplans.csv.csv` — travel/roaming plan data
- `data/html_debug/` — static HTML snapshots used for offline country-list extraction
- `data/source/` — per-brand intermediate CSVs

See [METHODOLOGY.txt](METHODOLOGY.txt) for a detailed per-brand scraping methodology.
