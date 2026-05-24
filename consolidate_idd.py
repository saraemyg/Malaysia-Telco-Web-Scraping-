"""
consolidate_idd.py
Merges all brand IDD CSVs into a single idd.csv.

Input files (all in e:/DV/):
  yes_idd.csv        -- brand Yes, actual rates per country
  hotlink_idd.csv    -- brand Hotlink
  maxis_idd.csv      -- brand Maxis
  tunetalk_idd.csv   -- brand Tune Talk  (from scrape_idd_remaining.py)
  redone_idd.csv     -- brand redONE     (from scrape_idd_remaining.py)
  umobile_idd.csv    -- brand U Mobile   (from scrape_idd_remaining.py)
  celcomdigi_roaming.csv -- brand CelcomDigi (roaming voice/SMS rates)
  unifi_roaming.csv      -- brand Unifi      (roaming voice/SMS rates)

Output: idd.csv
"""

import re
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent
DATA   = BASE / "data"
SOURCE = BASE / "data" / "source"

UNIFIED_COLS = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "notes","source_url","scraped_at"
]

def _build_region_lookup():
    """Build {name_lower: region} from countries.csv (all alias rows included)."""
    path = DATA / "countries.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, usecols=["country", "region"])
    return {row["country"].strip().lower(): row["region"] for _, row in df.iterrows()}

REGION_LOOKUP = _build_region_lookup()

# Supplemental map for countries not in countries.csv
# Keys are lowercase; covers Africa, Caribbean, Oceania, and other gaps
_SUP = {
    # Africa
    "algeria":"Africa","angola":"Africa","benin":"Africa","botswana":"Africa",
    "bostwana":"Africa","burkina faso":"Africa","burundi":"Africa",
    "burundi kingdom":"Africa","cameroon":"Africa","cape verde":"Africa",
    "central african republic":"Africa","chad":"Africa","comoros":"Africa",
    "djibouti":"Africa","equatorial guinea":"Africa","eritrea":"Africa",
    "ethiopia":"Africa","gabon":"Africa","gambia":"Africa","ivory coast":"Africa",
    "lesotho":"Africa","liberia":"Africa","libya":"Africa","malawi":"Africa",
    "mali":"Africa","mauritania":"Africa","mauritius":"Africa","mayotte":"Africa",
    "namibia":"Africa","reunion":"Africa","rwanda":"Africa","senegal":"Africa",
    "seychelles":"Africa","sierra leone":"Africa","somalia":"Africa",
    "south sudan":"Africa","sudan":"Africa","sudan south":"Africa",
    "swaziland":"Africa","togo":"Africa","uganda":"Africa","zambia":"Africa",
    "zimbabwe":"Africa","ascension island":"Africa","st helena":"Africa",
    "saint helena":"Africa","sao tome":"Africa","morroco":"Africa",
    "libyan arab":"Africa","guinea":"Africa",
    # Caribbean
    "anguilla":"Caribbean","antigua":"Caribbean","aruba":"Caribbean",
    "bahamas":"Caribbean","barbados":"Caribbean","bermuda":"Caribbean",
    "bonaire":"Caribbean","british virgin islands":"Caribbean",
    "cayman islands":"Caribbean","caymen island":"Caribbean",
    "cuba":"Caribbean","curacao":"Caribbean","dominica":"Caribbean",
    "dominican republic":"Caribbean","domincan republic":"Caribbean",
    "grenada":"Caribbean","guadeloupe":"Caribbean","haiti":"Caribbean",
    "jamaica":"Caribbean","martinique":"Caribbean","montserrat":"Caribbean",
    "puerto rico":"Caribbean","saint kitts":"Caribbean","saint lucia":"Caribbean",
    "st kitts":"Caribbean","st. kitts":"Caribbean","st lucia":"Caribbean",
    "st. lucia":"Caribbean","st maarten":"Caribbean","st. maarten":"Caribbean",
    "sint maarten":"Caribbean","st vincent":"Caribbean","st. vincent":"Caribbean",
    "saint vincent":"Caribbean","trinidad":"Caribbean",
    "turks and caicos":"Caribbean","turks & caicos":"Caribbean",
    "us virgin islands":"Caribbean","u.s virgin islands":"Caribbean",
    "virgin island":"Caribbean","nevis":"Caribbean",
    # South America
    "bolivia":"South America","colombia":"South America",
    "french guiana":"South America","french guyana":"South America",
    "guyana":"South America","paraguay":"South America",
    "suriname":"South America","surinam":"South America",
    "venezuela":"South America","venezula":"South America",
    # Central America
    "belize":"Central America","guatemala":"Central America",
    "honduras":"Central America","panama":"Central America",
    # North America
    "alaska":"North America","hawaii":"North America","haiwaii":"North America",
    # Oceania
    "american samoa":"Oceania","christmas island":"Oceania",
    "cocos island":"Oceania","cook island":"Oceania","french polynesia":"Oceania",
    "guam":"Oceania","kiribati":"Oceania","marshall island":"Oceania",
    "micronesia":"Oceania","nauru":"Oceania","new caledonia":"Oceania",
    "niue":"Oceania","norfolk island":"Oceania","northern mariana":"Oceania",
    "northen mariana":"Oceania","mariana island":"Oceania","palau":"Oceania",
    "samoa":"Oceania","saipan":"Oceania","solomon island":"Oceania",
    "tokelau":"Oceania","tonga":"Oceania","tuvalu":"Oceania",
    "vanuatu":"Oceania","wallis":"Oceania","western samoa":"Oceania",
    # Europe
    "andorra":"Europe","azores":"Europe","faroe island":"Europe",
    "faeroe island":"Europe","falkland island":"Europe","gibraltar":"Europe",
    "greenland":"Europe","kosovo":"Europe","madeira":"Europe",
    "monaco":"Europe","san marino":"Europe","slovak republic":"Europe",
    "vatican":"Europe","yugoslavia":"Europe",
    # Middle East
    "palestine":"Middle East","syria":"Middle East","yemen":"Middle East",
    # South Asia
    "bhutan":"South Asia",
    # Central Asia
    "kyrgyz republic":"Central Asia","turkmenistan":"Central Asia",
    # Edge cases / alternate spellings not caught by substring
    "st. pierre":"Caribbean","saint pierre":"Caribbean","st pierre":"Caribbean",
    "niue island":"Oceania","niue":"Oceania",
    "st. helena":"Africa","saint helena":"Africa",
    "marianas islands":"Oceania","mariana islands":"Oceania",
    "usa - guam":"Oceania","usa guam":"Oceania",
    "usa - mainland":"North America","usa - call":"North America","usa mainland":"North America",
    "cuba-guantanamo":"Caribbean",
    "diego garcia":"Other",
    "tatarstan":"Europe",
    "antarctica":"Other",
}

def get_region(country):
    if pd.isna(country):
        return "Other"
    c = str(country).strip()
    cl = c.lower()
    # Strip trailing (+dialing_code)
    cl_clean = re.sub(r'\s*\(\+?\d+[-\d/]*\)\s*$', '', cl).strip()

    for lookup_key in (cl, cl_clean):
        # Exact match against countries.csv
        if lookup_key in REGION_LOOKUP:
            return REGION_LOOKUP[lookup_key]
        # Exact match against supplemental map
        if lookup_key in _SUP:
            return _SUP[lookup_key]

    # Substring match against countries.csv (longer name contains shorter, or vice versa)
    for name, region in REGION_LOOKUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name):
            return region

    # Substring match against supplemental map
    for name, region in _SUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name):
            return region

    return "Other"


def _fix_numeric(series):
    """Convert string column to float, handling comma decimals like '9,80'."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )


def load_yes():
    """yes_idd.csv has different column names; normalise."""
    path = SOURCE / "yes_idd.csv"
    if not path.exists():
        print(f"  [SKIP] {path.name} not found")
        return pd.DataFrame()
    df = pd.read_csv(path)
    df = df.rename(columns={
        "countryCode":    "country_code",
        "callRateFixed":  "rate_fixed_per_min_myr",
        "callRateMobile": "rate_per_min_myr",
        "smsRate":        "rate_per_sms_myr",
        "source_url":     "source_url",
    })
    # Fix comma-decimal values (e.g. '9,80' → 9.80)
    for col in ("rate_per_min_myr", "rate_fixed_per_min_myr", "rate_per_sms_myr"):
        if col in df.columns:
            df[col] = _fix_numeric(df[col])
    df["brand"] = "Yes"
    df["access_code"]   = ""
    df["plan_specific"] = False
    df["notes"]         = ""
    df["scraped_at"]    = datetime.now().isoformat(timespec="seconds")
    if "region" not in df.columns:
        df["region"] = df["country"].apply(get_region)
    return df[UNIFIED_COLS[1:]]  # drop record_id, added later


def load_standard(fname, brand_override=None):
    """Load a CSV that already uses the unified schema."""
    path = SOURCE / fname
    if not path.exists():
        print(f"  [SKIP] {path.name} not found")
        return pd.DataFrame()
    df = pd.read_csv(path)
    if brand_override:
        df["brand"] = brand_override
    # Ensure all columns present
    for col in UNIFIED_COLS[1:]:
        if col not in df.columns:
            df[col] = None
    return df[UNIFIED_COLS[1:]]


def main():
    print("=" * 50)
    print("IDD Consolidation")
    print("=" * 50)

    frames = []

    # Yes (different schema)
    yes_df = load_yes()
    if not yes_df.empty:
        print(f"  Yes:         {len(yes_df)} rows")
        frames.append(yes_df)

    # Standard schema files
    brand_files = [
        ("hotlink_idd.csv",        None),
        ("maxis_idd.csv",          None),
        ("tunetalk_idd.csv",       None),
        ("redone_idd.csv",         None),
        ("umobile_idd.csv",        None),
        # Roaming call rates (per-country voice + SMS while abroad)
        ("celcomdigi_roaming.csv", None),
        ("unifi_roaming.csv",      None),
    ]
    for fname, brand in brand_files:
        df = load_standard(fname, brand)
        if not df.empty:
            brand_name = df["brand"].iloc[0] if "brand" in df.columns else fname
            print(f"  {brand_name:16s}: {len(df)} rows")
            frames.append(df)

    if not frames:
        print("\n[ERROR] No IDD data found.")
        return

    combined = pd.concat(frames, ignore_index=True)

    # TuneTalk column fix: scraper puts SMS rate in rate_per_min_myr; shift it across
    mask_tt = combined["brand"] == "Tune Talk"
    combined.loc[mask_tt, "rate_per_sms_myr"] = combined.loc[mask_tt, "rate_per_min_myr"]
    combined.loc[mask_tt, "rate_per_min_myr"]  = combined.loc[mask_tt, "rate_fixed_per_min_myr"]

    # U Mobile fix: website shows flat RM0.35/SMS but scraper misses it
    combined.loc[combined["brand"] == "U Mobile", "rate_per_sms_myr"] = 0.35

    # Always recompute region from countries.csv + supplemental map for consistency
    combined["region"] = combined["country"].apply(get_region)

    # Reassign sequential record_id
    combined.insert(0, "record_id", range(1, len(combined) + 1))

    # Sort: brand, country, plan_type
    combined = combined.sort_values(
        ["brand", "country", "plan_type"], na_position="last"
    ).reset_index(drop=True)
    combined["record_id"] = range(1, len(combined) + 1)

    out_path = DATA / "idd.csv"
    combined.to_csv(out_path, index=False)

    print(f"\n  Combined: {len(combined)} rows")
    print(f"  Written:  {out_path.name}")
    print("\n  By brand:")
    for brand, grp in combined.groupby("brand"):
        countries = grp["country"].nunique()
        print(f"    {brand:16s}: {len(grp):5d} rows ({countries} countries)")


if __name__ == "__main__":
    main()
