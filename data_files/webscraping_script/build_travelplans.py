"""
Build travelplans.csv + pass_country_bridge.csv from all harvested sources.
Also writes maxis_roaming_by_country.csv as a side output.

Run:
  python build_travelplans.py
"""

import re
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

HARVESTED = Path("harvested")
DEBUG = Path("debug")
NOW = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

TP_COLS = [
    "travel_plan_id", "brand", "plan_name", "plan_type", "direction",
    "price_myr", "validity_days", "data_gb_roaming",
    "country_count_marketed", "calls", "sms", "priority_pass_visits",
    "unique_benefits", "best_for_persona", "source_url",
]

BRIDGE_COLS = ["travel_plan_id", "country", "region"]

ROAMING_COLS = [
    "record_id", "brand", "pass_name", "country", "region",
    "price_myr", "duration_days", "data_gb", "data_speed_mbps",
    "calls_minutes", "sms_count", "is_unlimited_data", "pass_type",
    "roaming_operator", "source_url", "scraped_at",
]

REGION = {
    "Singapore": "Southeast Asia", "Thailand": "Southeast Asia",
    "Indonesia": "Southeast Asia", "Philippines": "Southeast Asia",
    "Vietnam": "Southeast Asia", "Myanmar": "Southeast Asia",
    "Cambodia": "Southeast Asia", "Laos": "Southeast Asia",
    "Brunei": "Southeast Asia", "Brunei Darussalam": "Southeast Asia",
    "Timor-Leste": "Southeast Asia", "East Timor": "Southeast Asia",
    "China": "East Asia", "Hong Kong": "East Asia", "Japan": "East Asia",
    "South Korea": "East Asia", "Taiwan": "East Asia", "Macau": "East Asia",
    "Macao": "East Asia", "Korea": "East Asia", "Mongolia": "East Asia",
    "India": "South Asia", "Bangladesh": "South Asia", "Pakistan": "South Asia",
    "Sri Lanka": "South Asia", "Nepal": "South Asia", "Bhutan": "South Asia",
    "Afghanistan": "South Asia", "Maldives": "South Asia",
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "Papua New Guinea": "Oceania", "Nauru": "Oceania",
    "United States": "North America", "United States of America": "North America",
    "USA": "North America", "Canada": "North America", "Mexico": "North America",
    "Puerto Rico": "North America",
    "Guatemala": "Central America", "El Salvador": "Central America",
    "Honduras": "Central America", "Nicaragua": "Central America",
    "Costa Rica": "Central America", "Panama": "Central America",
    "Brazil": "South America", "Argentina": "South America",
    "Chile": "South America", "Colombia": "South America",
    "Peru": "South America", "Ecuador": "South America",
    "Uruguay": "South America", "Paraguay": "South America",
    "United Kingdom": "Europe", "Germany": "Europe", "France": "Europe",
    "Italy": "Europe", "Spain": "Europe", "Netherlands": "Europe",
    "Belgium": "Europe", "Switzerland": "Europe", "Austria": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe",
    "Finland": "Europe", "Poland": "Europe", "Portugal": "Europe",
    "Greece": "Europe", "Czech Republic": "Europe", "Hungary": "Europe",
    "Romania": "Europe", "Bulgaria": "Europe", "Croatia": "Europe",
    "Slovakia": "Europe", "Slovenia": "Europe", "Estonia": "Europe",
    "Latvia": "Europe", "Lithuania": "Europe", "Ireland": "Europe",
    "Iceland": "Europe", "Luxembourg": "Europe", "Malta": "Europe",
    "Cyprus": "Europe", "Albania": "Europe", "Bosnia": "Europe",
    "Serbia": "Europe", "Montenegro": "Europe", "Macedonia": "Europe",
    "Belarus": "Europe", "Ukraine": "Europe", "Russia": "Europe",
    "Moldova": "Europe", "Republic of Moldova": "Europe",
    "Liechtenstein": "Europe", "Faroe Islands": "Europe",
    "Isle of Man": "Europe", "Jersey": "Europe", "Guernsey": "Europe",
    "Guernsey (United Kingdom)": "Europe",
    "Isle of Man (United Kingdom)": "Europe",
    "Jersey (United Kingdom)": "Europe",
    "Turkey": "Europe", "Turkiye": "Europe",
    "Saudi Arabia": "Middle East", "UAE": "Middle East",
    "United Arab Emirates": "Middle East", "Qatar": "Middle East",
    "Kuwait": "Middle East", "Bahrain": "Middle East",
    "Oman": "Middle East", "Jordan": "Middle East",
    "Iraq": "Middle East", "Israel": "Middle East",
    "Palestine": "Middle East", "Lebanon": "Middle East",
    "Yemen": "Middle East", "Iran": "Middle East",
    "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa",
    "Ghana": "Africa", "Egypt": "Africa", "Morocco": "Africa",
    "Tanzania": "Africa", "Ethiopia": "Africa", "Zambia": "Africa",
    "Zimbabwe": "Africa", "Algeria": "Africa", "Tunisia": "Africa",
    "Angola": "Africa", "Mozambique": "Africa", "Madagascar": "Africa",
    "Mauritius": "Africa", "Rwanda": "Africa", "Uganda": "Africa",
    "Congo": "Africa", "D.R.Congo": "Africa", "DR Congo": "Africa",
    "D.R.Congo (Zaire)": "Africa", "Gabon": "Africa",
    "Ivory Coast": "Africa", "Senegal": "Africa", "Benin": "Africa",
    "Cameroon": "Africa", "Chad": "Africa", "Cape Verde": "Africa",
    "Botswana": "Africa", "Namibia": "Africa",
    "Jamaica": "Caribbean", "Barbados": "Caribbean", "Dominica": "Caribbean",
    "Grenada": "Caribbean", "Trinidad and Tobago": "Caribbean",
    "Anguilla": "Caribbean", "Antigua and Barbuda": "Caribbean",
    "Cayman Islands": "Caribbean", "British Virgin Island": "Caribbean",
}


def get_region(country):
    return REGION.get(country, "Other")


def clean_country(raw):
    if not raw:
        return ""
    s = re.sub(r"\s*\(\+?\d+\)\s*$", "", str(raw)).strip()
    s = s.strip(":").strip()
    return s


def parse_price(text):
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(text).replace("RM", "").replace(",", ""))
    return float(m.group(1)) if m else None


def infer_persona(plan_name, validity_days):
    name = plan_name.lower()
    if "global" in name or "world" in name or "multi" in name:
        if validity_days and validity_days >= 15:
            return "Global Executive"
        return "Global Executive"
    if "asean" in name or "apac" in name:
        return "Regional Hopper"
    if "sg" in name or "thai" in name or "indo" in name or "cross-border" in name:
        return "Regional Hopper"
    if "tourist" in name or "inbound" in name:
        return "Inbound Tourist"
    if validity_days and validity_days >= 30:
        return "Global Executive"
    return "Regional Hopper"


# Each parser returns:
#   passes: list of dicts (travelplans schema minus travel_plan_id)
#   bridge_map: dict  plan_name -> [country, ...]   (only for plans with known countries)


# ---------------------------------------------------------------------------
# 1. redONE — full country lists in harvested/redone_roaming_table_3.csv
# ---------------------------------------------------------------------------
def parse_redone():
    path = HARVESTED / "redone_roaming_table_3.csv"
    print(f"\n[redONE] {path}")

    # CSV is a transposed table: columns = passes, rows = attributes
    # Header row: 0,1,2,3,4  (column indices)
    # Row 0: pass base names   e.g. "Singapore, Indonesia, Thailand" / "redROAM APAC" / ...
    # Row 1: durations         e.g. "3-Day Pass"
    # Row 2: prices            e.g. "Price:3 days - RM10"
    # Row 3: data quotas       e.g. "Internet Quota:3 days - 10GB 5G/4G"
    # Row 4: country counts    e.g. "No. of Countries:3"
    # Row 5: "Countries:"      (label row, skip)
    # Row 6: country lists     e.g. "Singapore, Indonesia, Thailand"
    # Row 7: basic internet
    # Row 8: pass type

    raw = pd.read_csv(path, header=None)  # read without header so rows are accessible by iloc
    # Row 0 is the numeric header (0,1,2,3,4) — drop it
    raw = raw.iloc[1:].reset_index(drop=True)

    passes = []
    bridge_map = {}
    num_cols = raw.shape[1]

    for col_idx in range(num_cols):
        col = raw.iloc[:, col_idx]
        # col[0] = pass base name  (e.g. "redROAM APAC" or "Singapore, Indonesia, Thailand")
        # col[1] = duration        (e.g. "3-Day Pass")
        # col[2] = price string    (e.g. "Price:3 days - RM30")
        # col[3] = quota string
        # col[4] = country count   (e.g. "No. of Countries:24")
        # col[5] = "Countries:"
        # col[6] = country list

        base_name = str(col.iloc[0]).strip() if len(col) > 0 else ""
        duration_raw = str(col.iloc[1]).strip() if len(col) > 1 else ""
        price_raw = str(col.iloc[2]).strip() if len(col) > 2 else ""
        quota_raw = str(col.iloc[3]).strip() if len(col) > 3 else ""
        count_raw = str(col.iloc[4]).strip() if len(col) > 4 else ""
        countries_raw = str(col.iloc[6]).strip() if len(col) > 6 else ""

        # Derive plan name
        dur_label = re.sub(r"[Pp]ass", "Pass", duration_raw).strip()
        if "Singapore" in base_name or "Indonesia" in base_name:
            plan_name = f"redROAM SG/ID/TH {dur_label}"
        elif "APAC" in base_name:
            plan_name = f"redROAM APAC {dur_label}"
        elif "Global" in base_name:
            plan_name = f"redROAM Global {dur_label}"
        else:
            plan_name = f"redROAM {base_name} {dur_label}".strip()

        # Duration in days
        dur_match = re.search(r"(\d+)", duration_raw)
        validity_days = int(dur_match.group(1)) if dur_match else None
        if "14" in duration_raw:
            validity_days = 14

        # Price: format "Price:X days - RMY"
        price_myr = None
        price_search = re.search(r"RM\s*(\d+(?:\.\d+)?)", price_raw)
        if price_search:
            price_myr = float(price_search.group(1))

        # Quota
        gb_match = re.search(r"(\d+(?:\.\d+)?)GB", quota_raw, re.I)
        data_gb = float(gb_match.group(1)) if gb_match else None

        # Country count
        cnt_match = re.search(r"(\d+)", count_raw)
        country_count_marketed = cnt_match.group(1) if cnt_match else count_raw

        # Countries list
        country_list = []
        if countries_raw and countries_raw.lower() not in {"nan", "countries:", ""}:
            country_list = [c.strip() for c in countries_raw.split(",") if c.strip()]

        persona = infer_persona(plan_name, validity_days)

        passes.append({
            "brand": "redONE",
            "plan_name": plan_name,
            "plan_type": "both",
            "direction": "outbound",
            "price_myr": price_myr,
            "validity_days": validity_days,
            "data_gb_roaming": data_gb,
            "country_count_marketed": country_count_marketed,
            "calls": "no",
            "sms": "no",
            "priority_pass_visits": 0,
            "unique_benefits": "",
            "best_for_persona": persona,
            "source_url": "https://www.redonemobile.com.my/en/roaming/",
        })
        if country_list:
            bridge_map[plan_name] = country_list

    print(f"  -> {len(passes)} passes, {sum(len(v) for v in bridge_map.values())} bridge entries")
    return passes, bridge_map


# ---------------------------------------------------------------------------
# 2. Tune Talk — count-only
# ---------------------------------------------------------------------------
def parse_tunetalk():
    path = HARVESTED / "tunetalk_roaming_table_0.csv"
    print(f"\n[Tune Talk] {path}")
    df = pd.read_csv(path, index_col=0)

    passes = []
    for col in df.columns:
        attrs = df[col]
        price_myr = parse_price(attrs.get("Price", ""))

        validity_raw = str(attrs.get("Validity", ""))
        if "75" in validity_raw:
            validity_days = 3
        elif "24" in validity_raw:
            validity_days = 1
        else:
            d = re.search(r"(\d+)", validity_raw)
            validity_days = int(d.group(1)) if d else None

        country_count = str(attrs.get("Roaming Countries", "")).strip()
        quota_raw = str(attrs.get("Plan Quota", "")).strip()
        gb_m = re.search(r"(\d+(?:\.\d+)?)GB", quota_raw, re.I)
        data_gb = float(gb_m.group(1)) if gb_m else None
        plan_name = str(col).strip()

        passes.append({
            "brand": "Tune Talk",
            "plan_name": plan_name,
            "plan_type": "prepaid",
            "direction": "outbound",
            "price_myr": price_myr,
            "validity_days": validity_days,
            "data_gb_roaming": data_gb,
            "country_count_marketed": country_count,
            "calls": "no",
            "sms": "no",
            "priority_pass_visits": 0,
            "unique_benefits": "",
            "best_for_persona": infer_persona(plan_name, validity_days),
            "source_url": "https://www.tunetalk.com/prepaid/roaming/",
        })

    print(f"  -> {len(passes)} passes (count-only)")
    return passes, {}


# ---------------------------------------------------------------------------
# 3. U Mobile — count-only
# ---------------------------------------------------------------------------
def parse_umobile():
    passes = []
    files = ["umobile_roaming_table_0.csv", "umobile_roaming_table_2.csv"]
    for fname in files:
        path = HARVESTED / fname
        print(f"\n[U Mobile] {path}")
        df = pd.read_csv(path, index_col=0)

        for col in df.columns:
            attrs = df[col]
            price_myr = parse_price(attrs.get("Price", ""))

            validity_raw = str(attrs.get("Validity", ""))
            if "hour" in validity_raw.lower():
                validity_days = 1
            else:
                d = re.search(r"(\d+)", validity_raw)
                validity_days = int(d.group(1)) if d else None

            country_count = str(attrs.get("Countries", "")).strip()
            quota_raw = str(attrs.get("Data Quota", "")).strip()
            gb_m = re.search(r"(\d+(?:\.\d+)?)GB", quota_raw, re.I)
            data_gb = float(gb_m.group(1)) if gb_m else None
            plan_name = str(col).strip()

            passes.append({
                "brand": "U Mobile",
                "plan_name": plan_name,
                "plan_type": "both",
                "direction": "outbound",
                "price_myr": price_myr,
                "validity_days": validity_days,
                "data_gb_roaming": data_gb,
                "country_count_marketed": country_count,
                "calls": "no",
                "sms": "no",
                "priority_pass_visits": 0,
                "unique_benefits": "",
                "best_for_persona": infer_persona(plan_name, validity_days),
                "source_url": "https://www.u.com.my/en/personal/mobile-plans/roam-travel/roaming",
            })

    print(f"  -> {len(passes)} passes (count-only)")
    return passes, {}


# ---------------------------------------------------------------------------
# 4. Hotlink
# ---------------------------------------------------------------------------
def parse_hotlink():
    passes = []
    bridge_map = {}

    path3 = HARVESTED / "hotlink_roaming_table_3.csv"
    path0 = HARVESTED / "hotlink_roaming_table_0.csv"
    print(f"\n[Hotlink] {path3} + {path0}")

    df3 = pd.read_csv(path3)
    df0 = pd.read_csv(path0)

    if {"Duration", "Countries / Regions", "Price"}.issubset(df3.columns):
        for _, row in df3.iterrows():
            duration_raw = str(row.get("Duration", "")).strip()
            regions_raw = str(row.get("Countries / Regions", "")).strip()
            price_raw = str(row.get("Price", "")).strip()

            dur_m = re.search(r"(\d+)", duration_raw)
            validity_days = int(dur_m.group(1)) if dur_m else None

            prices = re.findall(r"RM\s*(\d+(?:\.\d+)?)", price_raw)
            price_myr = float(prices[0]) if prices else None

            region_upper = regions_raw.upper()
            if "ASEAN" in region_upper:
                plan_name = f"Hotlink {duration_raw} ASEAN Roam Pass"
            elif "MULTI" in region_upper:
                plan_name = f"Hotlink {duration_raw} Multi Country Roam Pass"
            else:
                plan_name = f"Hotlink {duration_raw} Roam Pass ({regions_raw})"

            passes.append({
                "brand": "Hotlink",
                "plan_name": plan_name,
                "plan_type": "both",
                "direction": "outbound",
                "price_myr": price_myr,
                "validity_days": validity_days,
                "data_gb_roaming": None,
                "country_count_marketed": regions_raw,
                "calls": "no",
                "sms": "no",
                "priority_pass_visits": 0,
                "unique_benefits": "",
                "best_for_persona": infer_persona(plan_name, validity_days),
                "source_url": "https://www.hotlink.com.my/en/services/international-roaming/",
            })
    else:
        for _, row in df0.iterrows():
            price_myr = parse_price(str(row.get("Price", "")))
            validity_raw = str(row.get("Validity", "")).strip()
            dur_m = re.search(r"(\d+)", validity_raw)
            validity_days = int(dur_m.group(1)) if dur_m else None
            plan_name = "Hotlink Roam Pass"
            passes.append({
                "brand": "Hotlink",
                "plan_name": plan_name,
                "plan_type": "both",
                "direction": "outbound",
                "price_myr": price_myr,
                "validity_days": validity_days,
                "data_gb_roaming": None,
                "country_count_marketed": "",
                "calls": "no",
                "sms": "no",
                "priority_pass_visits": 0,
                "unique_benefits": "",
                "best_for_persona": "Regional Hopper",
                "source_url": "https://www.hotlink.com.my/en/services/international-roaming/",
            })

    print(f"  -> {len(passes)} passes")
    return passes, bridge_map


# ---------------------------------------------------------------------------
# 5. Maxis — parse modals from maxis_roaming_rendered.html
# ---------------------------------------------------------------------------
MAXIS_PASS_INFO = {
    "1dayDataRoamPasscountries":        ("1 Day DataRoam Pass",               38.0, 1,  "payg_daily"),
    "1DayUnlimitedDataPasscountries":   ("1 Day Unlimited Data Pass",          29.0, 1,  "payg_daily"),
    "1DayCallsSMSUnlimitedPasscountries": ("1 Day Calls & SMS Unlimited Pass", 15.0, 1,  "payg_daily"),
    "3DaysAseanDataPasscountries":      ("3 Days ASEAN Data Pass",             39.0, 3,  "regional_pass"),
    "7DaysAseanDataPasscountries":      ("7 Days ASEAN Data Pass",             49.0, 7,  "regional_pass"),
    "7DaysApacDataPass":                ("7 Days APAC Data Pass",              69.0, 7,  "regional_pass"),
    "15DaysWorldUnlimitedDataPass":     ("15 Days Multi Country Data Pass",    99.0, 15, "country_pass"),
    "30DaysWorldUnlimitedDataPass":     ("30 Days Multi Country Data Pass",    149.0, 30, "country_pass"),
}


def parse_maxis_modals():
    path = HARVESTED / "maxis_roaming_rendered.html"
    print(f"\n[Maxis] {path}")
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")

    modal_countries = {}
    for modal in soup.find_all("div", attrs={"class": re.compile(r"\bmodal\b")}):
        mid = modal.get("id") or ""
        if not mid:
            continue
        table = modal.find("table")
        if not table:
            continue
        countries = []
        for td in table.find_all("td"):
            c = clean_country(td.get_text(strip=True))
            if c and len(c) > 1 and c.lower() not in {"countries", "nan"}:
                countries.append(c)
        if countries:
            modal_countries[mid] = countries

    print(f"  found {len(modal_countries)} modals with country tables: {list(modal_countries.keys())}")

    passes = []
    bridge_map = {}

    for modal_id, (pass_suffix, price_myr, validity_days, pass_type) in MAXIS_PASS_INFO.items():
        countries = modal_countries.get(modal_id, [])
        plan_name = f"Maxis {pass_suffix}"
        country_count = str(len(countries)) if countries else "varies"

        passes.append({
            "brand": "Maxis",
            "plan_name": plan_name,
            "plan_type": "postpaid",
            "direction": "outbound",
            "price_myr": price_myr,
            "validity_days": validity_days,
            "data_gb_roaming": None,
            "country_count_marketed": country_count,
            "calls": "yes" if "Calls" in pass_suffix else "no",
            "sms": "yes" if "Calls" in pass_suffix else "no",
            "priority_pass_visits": 0,
            "unique_benefits": (
                "Auto-activated when data usage hits preset limit"
                if "DataRoam" in pass_suffix else ""
            ),
            "best_for_persona": infer_persona(plan_name, validity_days),
            "source_url": "https://www.maxis.com.my/en/mobile-plans/maxis-roaming/",
        })
        if countries:
            bridge_map[plan_name] = countries

    print(f"  -> {len(passes)} passes, bridge entries for {len(bridge_map)} passes")
    return passes, bridge_map


# ---------------------------------------------------------------------------
# 6. Unifi — parse #taas modal from unifi_roaming_rendered.html
# ---------------------------------------------------------------------------
UNIFI_PRICE_BY_KEY = {
    "sg-thai-indo": 9.0, "cross-border": 9.0,
    "asean-unlimited-modal": 19.0, "asean-unlimited": 19.0,
    "global-unlimited-modal": 39.0, "global-unlimited": 39.0,
    "data-daily": 39.0, "other-limited": 39.0,
    "middleeast-1-day": 15.0, "middleeast-7-day": 38.0,
    "middleeast-15-day": 75.0, "middleeast-30-day": 85.0,
    "middleeast-45-day": 135.0, "middleeast-unlimited": 15.0,
    "asean-week": 39.0, "asean-week-unlimited": 39.0,
    "global-week": 69.0, "global-week-unlimited": 69.0,
}


def parse_unifi():
    path = HARVESTED / "unifi_roaming_rendered.html"
    print(f"\n[Unifi] {path}")
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")

    taas = soup.find("div", id="taas")
    if not taas:
        print("  WARNING: #taas modal not found")
        return [], {}

    passes = []
    bridge_map = {}

    for sub in taas.find_all("div", id=re.compile(r"-modal$")):
        modal_id = sub.get("id", "")

        label_div = sub.find("div", class_=re.compile(r"font-weight-bold"))
        if not label_div:
            continue
        label_text = label_div.get_text(" ", strip=True)
        parts = [p.strip() for p in re.split(r"[\|/]|\s{2,}", label_text) if p.strip()]

        list_div = sub.find("div", id=re.compile(r"^list-"))
        countries = []
        if list_div:
            for cdiv in list_div.find_all("div", recursive=False):
                raw_text = cdiv.get_text(strip=True)
                raw_text = re.sub(r"5G\s*-[^<>]*", "", raw_text, flags=re.I).strip()
                c = clean_country(raw_text)
                if c and len(c) > 1:
                    countries.append(c)

        if not countries:
            continue

        plan_name = "UNI5G Roam " + " ".join(parts)
        plan_name = re.sub(r"\s+", " ", plan_name).strip()

        dur_m = re.search(r"(\d+)\s*-?\s*[Dd]ay", label_text)
        week_m = re.search(r"(\d+)\s*-?\s*[Ww]eek", label_text)
        if dur_m:
            validity_days = int(dur_m.group(1))
        elif week_m:
            validity_days = int(week_m.group(1)) * 7
        else:
            validity_days = 1

        # Price lookup
        mid_lower = modal_id.lower()
        price_myr = 39.0
        for key, val in UNIFI_PRICE_BY_KEY.items():
            if key in mid_lower:
                price_myr = val
                break

        passes.append({
            "brand": "Unifi Mobile",
            "plan_name": plan_name,
            "plan_type": "postpaid",
            "direction": "outbound",
            "price_myr": price_myr,
            "validity_days": validity_days,
            "data_gb_roaming": None,
            "country_count_marketed": str(len(countries)),
            "calls": "no",
            "sms": "no",
            "priority_pass_visits": 0,
            "unique_benefits": "5G roaming available on select networks",
            "best_for_persona": infer_persona(plan_name, validity_days),
            "source_url": "https://unifi.com.my/mobile/roaming",
        })
        bridge_map[plan_name] = countries

    print(f"  -> {len(passes)} passes, {sum(len(v) for v in bridge_map.values())} bridge entries")
    return passes, bridge_map


# ---------------------------------------------------------------------------
# 7. Maxis country-list page -> maxis_roaming_by_country.csv  (side output)
# ---------------------------------------------------------------------------
MAXIS_SECTION_PRICES = [
    ("1 Day Roam Data Pass",   38.0, 1),
    ("1 Day Unlimited Data Pass", 29.0, 1),
    ("3 Days ASEAN Data Pass", 39.0, 3),
    ("7 Days ASEAN Data Pass", 49.0, 7),
    ("7 Days APAC Data Pass",  69.0, 7),
    ("15 Days Multi Country",  99.0, 15),
    ("30 Days Multi Country",  149.0, 30),
]


def build_maxis_roaming_by_country():
    path = DEBUG / "maxis_country_list_rendered.html"
    print(f"\n[Maxis country list] {path}")
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")

    sections = []
    for ptag in soup.find_all("p", style=re.compile(r"text-align.*center", re.I)):
        b = ptag.find("b")
        if not b:
            continue
        section_name = b.get_text(strip=True)
        if not section_name:
            continue
        # Find the next faq-table-comp div as a sibling or nearby
        table_div = ptag.find_next("div", class_=re.compile(r"faq-table-comp"))
        if not table_div:
            continue
        countries = []
        for td in table_div.find_all("td"):
            cell_text = td.get_text(" ", strip=True)
            if "•" in cell_text or "•" in cell_text:
                # Bullet-separated list in single cell: "• Brunei • Cambodia • ..."
                parts = re.split(r"[••]", cell_text)
                for part in parts:
                    c = clean_country(part.replace("\xa0", " ").strip())
                    if c and len(c) > 1 and c.lower() not in {"aeromobile (inflight)", "nan"}:
                        countries.append(c)
            else:
                c = clean_country(cell_text)
                if c and len(c) > 1 and c.lower() not in {"aeromobile (inflight)", "nan"}:
                    countries.append(c)
        if countries:
            sections.append((section_name, countries))
            print(f"  section '{section_name}': {len(countries)} countries")

    rows = []
    rid = 1
    for section_name, countries in sections:
        price_myr, duration_days = 38.0, 1
        for key, p, d in MAXIS_SECTION_PRICES:
            if key.lower() in section_name.lower() or section_name.lower() in key.lower():
                price_myr, duration_days = p, d
                break

        for country in countries:
            rows.append({
                "record_id": rid,
                "brand": "Maxis",
                "pass_name": f"Maxis {section_name}",
                "country": country,
                "region": get_region(country),
                "price_myr": price_myr,
                "duration_days": duration_days,
                "data_gb": "Unlimited (FUP applies)",
                "data_speed_mbps": None,
                "calls_minutes": None,
                "sms_count": None,
                "is_unlimited_data": True,
                "pass_type": "payg_daily" if duration_days == 1 else "regional_pass",
                "roaming_operator": "",
                "source_url": "https://www.maxis.com.my/en/mobile-plans/maxis-roaming/country-list/",
                "scraped_at": NOW,
            })
            rid += 1

    df = pd.DataFrame(rows, columns=ROAMING_COLS)
    out = Path("maxis_roaming_by_country.csv")
    df.to_csv(out, index=False)
    print(f"  [OK] {out}: {len(df)} rows across {len(sections)} sections")
    return df


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    all_passes = []
    all_bridge_maps = []  # list of dict[plan_name -> [countries]]

    for fn in [parse_redone, parse_tunetalk, parse_umobile, parse_hotlink,
               parse_maxis_modals, parse_unifi]:
        passes, bridge_map = fn()
        all_passes.extend(passes)
        all_bridge_maps.append(bridge_map)

    # Merge all bridge_maps into one, keyed by brand::plan_name for safety
    merged_bridge = {}
    for bridge_map in all_bridge_maps:
        for pname, countries in bridge_map.items():
            merged_bridge[pname] = countries

    # Assign travel_plan_id
    for i, p in enumerate(all_passes, start=1):
        p["travel_plan_id"] = i

    # Write travelplans.csv
    tp_df = pd.DataFrame(all_passes, columns=TP_COLS)
    tp_df.to_csv("travelplans.csv", index=False)
    print(f"\n[OK] travelplans.csv: {len(tp_df)} rows")
    print(tp_df.groupby("brand").size().to_string())

    # Build bridge
    bridge_rows = []
    for p in all_passes:
        countries = merged_bridge.get(p["plan_name"], [])
        for country in countries:
            bridge_rows.append({
                "travel_plan_id": p["travel_plan_id"],
                "country": country,
                "region": get_region(country),
            })

    bridge_df = pd.DataFrame(bridge_rows, columns=BRIDGE_COLS)
    bridge_df.to_csv("pass_country_bridge.csv", index=False)
    print(f"[OK] pass_country_bridge.csv: {len(bridge_df)} rows")

    # Side output
    build_maxis_roaming_by_country()

    print("\n[DONE]")


if __name__ == "__main__":
    main()
