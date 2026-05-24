"""
run_redone_idd.py
Re-scrapes redONE IDD with correct column mapping:
  rate_fixed_per_min_myr  = FIXED LINE (SEN/MIN)
  rate_per_min_myr        = MOBILE (SEN/MIN)
  rate_per_sms_myr        = SMS (SEN/SMS)
  notes                   = video_call=X/min; mms=X/mms

Output: redone_idd.csv
"""
import asyncio, re, csv, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE   = Path(__file__).parent
SOURCE = BASE / "data" / "source"
SCRAPED_AT = datetime.now().isoformat(timespec="seconds")
URL = "https://www.redonemobile.com.my/en/idd/"

IDD_COLS = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "notes","source_url","scraped_at"
]

REGION_LOOKUP = {}
_countries_path = BASE / "data" / "countries.csv"
if _countries_path.exists():
    import pandas as pd
    _cdf = pd.read_csv(_countries_path, usecols=["country", "region"])
    REGION_LOOKUP = {r["country"].strip().lower(): r["region"] for _, r in _cdf.iterrows()}

_SUP = {
    "algeria":"Africa","angola":"Africa","benin":"Africa","botswana":"Africa",
    "burkina faso":"Africa","burundi":"Africa","cameroon":"Africa","cape verde":"Africa",
    "central african republic":"Africa","chad":"Africa","comoros":"Africa",
    "djibouti":"Africa","equatorial guinea":"Africa","eritrea":"Africa",
    "ethiopia":"Africa","gabon":"Africa","gambia":"Africa","ivory coast":"Africa",
    "lesotho":"Africa","liberia":"Africa","libya":"Africa","malawi":"Africa",
    "mali":"Africa","mauritania":"Africa","mauritius":"Africa","mayotte":"Africa",
    "namibia":"Africa","reunion":"Africa","rwanda":"Africa","senegal":"Africa",
    "seychelles":"Africa","sierra leone":"Africa","somalia":"Africa",
    "south sudan":"Africa","sudan":"Africa","swaziland":"Africa","togo":"Africa",
    "uganda":"Africa","zambia":"Africa","zimbabwe":"Africa",
    "anguilla":"Caribbean","antigua":"Caribbean","aruba":"Caribbean",
    "bahamas":"Caribbean","barbados":"Caribbean","bermuda":"Caribbean",
    "bonaire":"Caribbean","british virgin islands":"Caribbean",
    "cayman islands":"Caribbean","cuba":"Caribbean","curacao":"Caribbean",
    "dominica":"Caribbean","dominican republic":"Caribbean","grenada":"Caribbean",
    "guadeloupe":"Caribbean","haiti":"Caribbean","jamaica":"Caribbean",
    "martinique":"Caribbean","montserrat":"Caribbean","puerto rico":"Caribbean",
    "saint kitts":"Caribbean","saint lucia":"Caribbean","st kitts":"Caribbean",
    "st. kitts":"Caribbean","st lucia":"Caribbean","st. lucia":"Caribbean",
    "st maarten":"Caribbean","st. maarten":"Caribbean","st vincent":"Caribbean",
    "st. vincent":"Caribbean","saint vincent":"Caribbean","trinidad":"Caribbean",
    "turks and caicos":"Caribbean","turks & caicos":"Caribbean",
    "us virgin islands":"Caribbean","virgin island":"Caribbean","nevis":"Caribbean",
    "bolivia":"South America","colombia":"South America",
    "french guiana":"South America","guyana":"South America",
    "paraguay":"South America","suriname":"South America","venezuela":"South America",
    "belize":"Central America","guatemala":"Central America",
    "honduras":"Central America","panama":"Central America",
    "alaska":"North America","hawaii":"North America",
    "american samoa":"Oceania","christmas island":"Oceania","cocos island":"Oceania",
    "cook island":"Oceania","french polynesia":"Oceania","guam":"Oceania",
    "kiribati":"Oceania","marshall island":"Oceania","micronesia":"Oceania",
    "nauru":"Oceania","new caledonia":"Oceania","niue":"Oceania",
    "norfolk island":"Oceania","mariana island":"Oceania","palau":"Oceania",
    "samoa":"Oceania","saipan":"Oceania","solomon island":"Oceania",
    "tokelau":"Oceania","tonga":"Oceania","tuvalu":"Oceania",
    "vanuatu":"Oceania","wallis":"Oceania","western samoa":"Oceania",
    "andorra":"Europe","azores":"Europe","faroe island":"Europe",
    "faeroe island":"Europe","falkland island":"Europe","gibraltar":"Europe",
    "greenland":"Europe","kosovo":"Europe","madeira":"Europe",
    "monaco":"Europe","san marino":"Europe","slovak republic":"Europe",
    "vatican":"Europe","andorra":"Europe",
    "palestine":"Middle East","syria":"Middle East","yemen":"Middle East",
    "bhutan":"South Asia","kyrgyz republic":"Central Asia","turkmenistan":"Central Asia",
    "st. pierre":"Caribbean","saint pierre":"Caribbean",
    "niue island":"Oceania","st. helena":"Africa","saint helena":"Africa",
    "marianas islands":"Oceania","cuba-guantanamo":"Caribbean",
    "usa - guam":"Oceania","usa guam":"Oceania",
    "usa - mainland":"North America","usa - call":"North America",
}

def get_region(country):
    import pandas as pd
    if pd.isna(country):
        return "Other"
    c = str(country).strip()
    cl = c.lower()
    cl_clean = re.sub(r'\s*\(\+?[\d\-/]+\)\s*$', '', cl).strip()
    for key in (cl, cl_clean):
        if key in REGION_LOOKUP:
            return REGION_LOOKUP[key]
        if key in _SUP:
            return _SUP[key]
    for name, region in REGION_LOOKUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name):
            return region
    for name, region in _SUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name):
            return region
    return "Other"

def clean_name(text):
    return re.sub(r'\s*\(\+?[\d\-]+\)\s*', '', str(text)).strip()

def extract_cc(text):
    m = re.search(r'\(\+?([\d]+)\)', str(text))
    return m.group(1) if m else ""

def extract_redone_rates(html):
    """
    Parse redONE jet-listing HTML.
    Rates appear as sequential h2 elements: label â†’ 'RM' â†’ value.
    Order: FIXED LINE, MOBILE, VIDEO CALL, SMS, MMS.
    Returns: (fixed, mobile, video, sms, mms)
    """
    soup = BeautifulSoup(html, "lxml")
    # Labels are h2; currency marker "RM" and numeric values are h5
    h2s = [h.get_text(separator=" ", strip=True) for h in soup.find_all(["h2", "h5"])]

    fixed = mobile = video = sms = mms = None
    i = 0
    while i < len(h2s):
        t = h2s[i].upper()
        # Each rate: label (h2) at i, 'RM' (h5) at i+1, value (h5) at i+2
        if i + 2 < len(h2s) and h2s[i + 1].strip() == "RM":
            try:
                val = float(h2s[i + 2])
                if "FIXED LINE" in t and fixed is None:
                    fixed = val; i += 3; continue
                elif "MOBILE" in t and "SEN/MIN" in t and mobile is None:
                    mobile = val; i += 3; continue
                elif "VIDEO" in t and video is None:
                    video = val; i += 3; continue
                elif "SMS" in t and "MMS" not in t and sms is None:
                    sms = val; i += 3; continue
                elif "MMS" in t and mms is None:
                    mms = val; i += 3; continue
            except (ValueError, IndexError):
                pass
        i += 1

    return fixed, mobile, video, sms, mms

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IDD_COLS)
        w.writeheader()
        for idx, r in enumerate(rows, 1):
            r["record_id"] = idx
            w.writerow(r)
    print(f"  -> Wrote {len(rows)} rows to {path.name}")


async def main():
    print("=" * 52)
    print("redONE IDD Scraper (corrected)")
    print("=" * 52)

    html_path = BASE / "data" / "html_debug" / "redone_idd.html"
    soup0 = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    sel = soup0.find("select", class_="jet-select__control")
    if not sel:
        print("[ERROR] jet-select__control not found in debug HTML")
        return

    raw_countries = [
        opt.get("value", "").strip().lstrip("ï»¿")
        for opt in sel.find_all("option")
        if opt.get("value", "").strip()
    ]
    print(f"  {len(raw_countries)} countries in dropdown")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        print("  Loading redONE IDD page...")
        try:
            await page.goto(URL, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"  [WARN] page load: {e}")

        try:
            await page.wait_for_selector("select.jet-select__control", timeout=10000)
        except Exception:
            print("  [WARN] jet-select not found, continuing anyway")

        rows = []
        failed = 0

        for i, raw in enumerate(raw_countries):
            country = clean_name(raw)
            cc = extract_cc(raw)
            fixed = mobile = video = sms = mms = None

            try:
                await page.select_option("select.jet-select__control", value=raw)
                await page.wait_for_timeout(1200)
                listing_html = await page.inner_html(".jet-listing-grid__items")
                fixed, mobile, video, sms, mms = extract_redone_rates(listing_html)
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  [WARN] {country}: {type(e).__name__}: {str(e)[:60]}")

            notes_parts = []
            if video is not None:
                notes_parts.append(f"video_call={video}/min")
            if mms is not None:
                notes_parts.append(f"mms={mms}/mms")
            notes_str = "; ".join(notes_parts)

            for pt in ("prepaid", "postpaid"):
                rows.append({
                    "brand": "redONE",
                    "country": country,
                    "region": get_region(country),
                    "plan_type": pt,
                    "rate_per_min_myr": mobile,
                    "rate_fixed_per_min_myr": fixed,
                    "rate_per_sms_myr": sms,
                    "notes": notes_str,
                    "source_url": URL,
                    "scraped_at": SCRAPED_AT,
                })

            if (i + 1) % 25 == 0:
                print(f"  Progress: {i+1}/{len(raw_countries)} | failures: {failed}")

        await ctx.close()
        await browser.close()

    print(f"\n  Done: {len(rows)} rows, {failed} failures")
    write_csv(SOURCE / "redone_idd.csv", rows)

    # Quick spot-check
    import pandas as pd
    df = pd.read_csv(SOURCE / "redone_idd.csv")
    filled_sms = df["rate_per_sms_myr"].notna().sum()
    print(f"  SMS filled: {filled_sms}/{len(df)}")
    print(df[["country","rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr","notes"]].head(6).to_string())


asyncio.run(main())

