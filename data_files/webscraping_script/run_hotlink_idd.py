"""
run_hotlink_idd.py
Re-scrapes Hotlink IDD with correct column mapping and tab handling.

Per country:
  - Clicks "Hotlink Prepaid" tab  â†’ rate_fixed_per_min_myr (fixed line), rate_per_min_myr (mobile line), rate_per_sms_myr
  - Clicks "Hotlink Postpaid" tab â†’ same, with IDD 132 rate + dial info in notes

Output: hotlink_idd.csv
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
URL = "https://www.hotlink.com.my/idd/"

IDD_COLS = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "notes","source_url","scraped_at"
]

# â”€â”€ Region lookup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
REGION_LOOKUP = {}
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
    "uganda":"Africa","zambia":"Africa","zimbabwe":"Africa","ascension island":"Africa",
    "st helena":"Africa","saint helena":"Africa","sao tome":"Africa","morroco":"Africa",
    "guinea":"Africa","anguilla":"Caribbean","antigua":"Caribbean","aruba":"Caribbean",
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
    "alaska":"North America","hawaii":"North America","haiwaii":"North America",
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
    "vatican":"Europe","palestine":"Middle East","syria":"Middle East",
    "yemen":"Middle East","bhutan":"South Asia",
    "kyrgyz republic":"Central Asia","turkmenistan":"Central Asia",
}

def _load_region_lookup():
    path = BASE / "data" / "countries.csv"
    if not path.exists():
        return
    import pandas as pd
    df = pd.read_csv(path, usecols=["country","region"])
    for _, r in df.iterrows():
        REGION_LOOKUP[r["country"].strip().lower()] = r["region"]

_load_region_lookup()

def get_region(country):
    import pandas as pd
    if pd.isna(country):
        return "Other"
    c = str(country).strip()
    cl = c.lower()
    cl_clean = re.sub(r'\s*\(\+?[\d\-/]+\)\s*$', '', cl).strip()
    for key in (cl, cl_clean):
        if key in REGION_LOOKUP: return REGION_LOOKUP[key]
        if key in _SUP: return _SUP[key]
    for name, region in REGION_LOOKUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name): return region
    for name, region in _SUP.items():
        if len(name) >= 4 and (name in cl_clean or cl_clean in name): return region
    return "Other"

def extract_cc(text):
    m = re.search(r'\(\+?([\d]+)\)', str(text))
    return m.group(1) if m else ""

def clean_name(text):
    return re.sub(r'\s*\(\+?[\d\-]+\)\s*', '', str(text)).strip()

# â”€â”€ Rate parsing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def parse_rate_per_min(text):
    """Parse 'RM4.00/min' or 'RM4.80/60 secs' â†’ per-minute rate."""
    m = re.search(r'RM\s*([\d.]+)\s*/\s*min', text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r'RM\s*([\d.]+)\s*/\s*(\d+)\s*secs?', text, re.I)
    if m:
        return round(float(m.group(1)) * 60 / int(m.group(2)), 4)
    return None


def extract_tab_rates(pane_soup):
    """
    Extract (rate_fixed, rate_mobile, rate_sms, notes) from an active tab pane.

    Rate cards live in div.rebrand-roaming-cruise-table.
    SMS may be in a .price-section with '/SMS' anywhere in the pane.
    IDD 132 block â†’ rate goes to notes.
    Fixed/Mobile may be same ('To Fixed/Mobile Line') or split ('To Fixed Line'/'To Mobile Line').
    """
    rate_fixed = rate_mobile = rate_sms = None
    idd132_rate = None

    # â”€â”€ Iterate rate card tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for table in pane_soup.find_all(class_="rebrand-roaming-cruise-table"):
        txt = table.get_text(separator=" ", strip=True)
        txt_l = txt.lower()

        if "idd 132" in txt_l:
            r = parse_rate_per_min(txt)
            if r:
                idd132_rate = r
            continue

        # SMS rate
        if "/sms" in txt_l and rate_sms is None:
            m = re.search(r'RM\s*([\d.]+)', txt, re.I)
            if m:
                rate_sms = float(m.group(1))
            continue

        # Direct Dial / Premium call rate
        if rate_fixed is not None:
            continue  # already have call rate from this pane

        price_sec = table.find(class_="price-section")
        if not price_sec:
            continue

        price_txt = price_sec.get_text(separator=" ", strip=True)
        wrappers = price_sec.find_all(class_="price-wrapper")

        if wrappers and "to fixed line" in price_txt.lower() and "to mobile line" in price_txt.lower():
            rates = []
            for w in wrappers:
                r = parse_rate_per_min(w.get_text(separator=" ", strip=True))
                if r is not None:
                    rates.append(r)
            if rates:
                rate_fixed  = rates[0]
                rate_mobile = rates[1] if len(rates) > 1 else rates[0]
        else:
            r = parse_rate_per_min(price_txt)
            if r is not None:
                rate_fixed = rate_mobile = r

    # â”€â”€ Fallback: scan all .price-section for SMS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if rate_sms is None:
        for sec in pane_soup.find_all(class_="price-section"):
            sec_txt = sec.get_text(separator=" ", strip=True)
            if "/sms" in sec_txt.lower():
                m = re.search(r'RM\s*([\d.]+)', sec_txt, re.I)
                if m:
                    rate_sms = float(m.group(1))
                break

    notes_parts = []
    if idd132_rate is not None:
        notes_parts.append(f"IDD 132: RM{idd132_rate}/min")
        notes_parts.append("Dial: 132 00 <country code> <area code> <phone number>")

    return rate_fixed, rate_mobile, rate_sms, "; ".join(notes_parts)


def get_active_pane(soup):
    """Find the currently-active Bootstrap tab pane."""
    pane = soup.find(
        "div",
        class_=lambda c: c and "tab-pane" in c and "show" in c and "active" in c
    )
    return pane or soup  # fall back to full soup if not found


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IDD_COLS)
        w.writeheader()
        for idx, r in enumerate(rows, 1):
            r["record_id"] = idx
            w.writerow(r)
    print(f"  -> Wrote {len(rows)} rows to {path.name}")


def make_row(country, cc, plan_type, fixed, mobile, sms, notes):
    return {
        "brand": "Hotlink",
        "country": country,
        "region": get_region(country),
        "plan_type": plan_type,
        "rate_per_min_myr": mobile,
        "rate_fixed_per_min_myr": fixed,
        "rate_per_sms_myr": sms,
        "notes": notes,
        "source_url": URL,
        "scraped_at": SCRAPED_AT,
    }


# â”€â”€ Main scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def main():
    print("=" * 52)
    print("Hotlink IDD Scraper (corrected â€” tabs + SMS + IDD 132)")
    print("=" * 52)

    # Get country list from local debug HTML
    html_path = BASE / "data" / "html_debug" / "hotlink_idd.html"
    soup0 = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    sel = soup0.find("select", {"name": "roaming-dropdown"})
    if not sel:
        print("[ERROR] roaming-dropdown not found in debug HTML")
        return

    countries = []
    for opt in sel.find_all("option"):
        v = opt.get("value", "").strip()
        if v:
            label = opt.get_text(strip=True)
            countries.append((v, extract_cc(label)))
    print(f"  {len(countries)} countries in dropdown")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        print(f"  Loading {URL} ...")
        await page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        rows = []
        failed = 0

        for i, (val, cc) in enumerate(countries):
            country = clean_name(val)
            pp_fixed = pp_mobile = pp_sms = None
            po_fixed = po_mobile = po_sms = None
            pp_notes = po_notes = ""

            try:
                await page.select_option('select[name="roaming-dropdown"]', value=val)
                await page.wait_for_timeout(1800)

                # â”€â”€ Prepaid tab â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                await page.locator("a.nav-link", has_text="Hotlink Prepaid").first.click()
                await page.wait_for_timeout(600)
                soup = BeautifulSoup(await page.content(), "lxml")
                pane = get_active_pane(soup)
                pp_fixed, pp_mobile, pp_sms, pp_notes = extract_tab_rates(pane)

                # â”€â”€ Postpaid tab â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                await page.locator("a.nav-link", has_text="Hotlink Postpaid").first.click()
                await page.wait_for_timeout(600)
                soup = BeautifulSoup(await page.content(), "lxml")
                pane = get_active_pane(soup)
                po_fixed, po_mobile, po_sms, po_notes = extract_tab_rates(pane)

            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  [WARN] {country}: {type(e).__name__}: {str(e)[:70]}")

            rows.append(make_row(country, cc, "prepaid",  pp_fixed, pp_mobile, pp_sms, pp_notes))
            rows.append(make_row(country, cc, "postpaid", po_fixed, po_mobile, po_sms, po_notes))

            if (i + 1) % 25 == 0:
                print(f"  Progress: {i+1}/{len(countries)} | failures: {failed}")

        await ctx.close()
        await browser.close()

    print(f"\n  Done: {len(rows)} rows, {failed} failures")
    write_csv(SOURCE / "hotlink_idd.csv", rows)

    import pandas as pd
    df = pd.read_csv(SOURCE / "hotlink_idd.csv")
    sms_ok = df["rate_per_sms_myr"].notna().sum()
    call_ok = df["rate_per_min_myr"].notna().sum()
    print(f"  Call rate filled: {call_ok}/{len(df)}")
    print(f"  SMS filled:       {sms_ok}/{len(df)}")
    print("\n  Sample (prepaid):")
    print(df[df["plan_type"]=="prepaid"][
        ["country","rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr","notes"]
    ].head(4).to_string())
    print("\n  Sample (postpaid):")
    print(df[df["plan_type"]=="postpaid"][
        ["country","rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr","notes"]
    ].head(4).to_string())


asyncio.run(main())

