"""
run_maxis_idd.py
Re-scrapes Maxis IDD with correct tab handling and column mapping.

Structure (per country):
  Hotlink Prepaid tab:
    - "Direct Dial" block: rate_fixed_per_min_myr (fixed), rate_per_min_myr (mobile), both /min
    - "SMS" block: rate_per_sms_myr
  Hotlink Postpaid tab:
    - "Premium" block: single rate for fixed/mobile (/60 secs or /min)
    - "IDD 132" block: fixed + mobile rates (/240 secs) â†’ notes
    - "SMS" block: rate_per_sms_myr

Output: maxis_idd.csv
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
URL = "https://www.maxis.com.my/idd/"

IDD_COLS = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "notes","source_url","scraped_at"
]

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
    df = pd.read_csv(path, usecols=["country", "region"])
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

def clean_name(text):
    return re.sub(r'\s*\(\+?[\d\-/]+\)\s*', '', str(text)).strip()


def parse_price_wrapper(wrapper):
    """Extract per-minute rate from a price-wrapper element.
    Handles /min, /60 secs, /240 secs etc."""
    price_el = wrapper.find(class_="price")
    if not price_el:
        return None
    try:
        val = float(price_el.get_text(strip=True))
    except ValueError:
        return None
    txt = wrapper.get_text(separator=" ", strip=True)
    m = re.search(r'/\s*(\d+)\s*secs?', txt, re.I)
    if m:
        secs = int(m.group(1))
        return round(val * 60 / secs, 4)
    return val  # /min assumed


def extract_maxis_tab_rates(pane_soup):
    """
    Extract (rate_fixed, rate_mobile, rate_sms, notes) from active Maxis tab pane.

    Rate blocks use class cmp-rebrand-roaming-cruise-table.
    - SMS block: contains /SMS
    - IDD 132 block: 'idd 132' in text â†’ two rates (fixed/mobile) â†’ notes
    - Direct Dial / Premium block: main IDD call rate
    """
    rate_fixed = rate_mobile = rate_sms = None
    idd132_parts = []

    for table in pane_soup.find_all(class_="cmp-rebrand-roaming-cruise-table"):
        txt = table.get_text(separator=" ", strip=True)
        txt_l = txt.lower()

        # SMS block
        if "/sms" in txt_l:
            price_el = table.find(class_="price")
            if price_el and rate_sms is None:
                try:
                    rate_sms = float(price_el.get_text(strip=True))
                except ValueError:
                    pass
            continue

        # IDD 132 block â†’ notes
        if "idd 132" in txt_l:
            sec = table.find(class_="price-section")
            if sec:
                wrappers = sec.find_all(class_="price-wrapper")
                sec_txt = sec.get_text(separator=" ", strip=True).lower()
                rates = [parse_price_wrapper(w) for w in wrappers]
                rates = [r for r in rates if r is not None]
                if "to fixed line" in sec_txt and "to mobile line" in sec_txt and len(rates) >= 2:
                    idd132_parts.append(f"IDD 132 Fixed: RM{rates[0]}/min; Mobile: RM{rates[1]}/min")
                elif rates:
                    idd132_parts.append(f"IDD 132: RM{rates[0]}/min")
                idd132_parts.append("Dial: 132 00 <country code> <area code> <phone number>")
            continue

        # Direct Dial / Premium: main IDD call rate
        if rate_fixed is not None:
            continue
        sec = table.find(class_="price-section")
        if not sec:
            continue
        sec_txt = sec.get_text(separator=" ", strip=True)
        sec_txt_l = sec_txt.lower()
        wrappers = sec.find_all(class_="price-wrapper")
        if not wrappers:
            continue

        if "to fixed line" in sec_txt_l and "to mobile line" in sec_txt_l:
            rates = [parse_price_wrapper(w) for w in wrappers]
            rates = [r for r in rates if r is not None]
            if rates:
                rate_fixed = rates[0]
                rate_mobile = rates[1] if len(rates) > 1 else rates[0]
        else:
            r = parse_price_wrapper(wrappers[0])
            if r is not None:
                rate_fixed = rate_mobile = r

    return rate_fixed, rate_mobile, rate_sms, "; ".join(idd132_parts)


def get_active_pane(soup):
    pane = soup.find(
        "div",
        class_=lambda c: c and "tab-pane" in c and "show" in c and "active" in c
    )
    return pane or soup


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IDD_COLS)
        w.writeheader()
        for idx, r in enumerate(rows, 1):
            r["record_id"] = idx
            w.writerow(r)
    print(f"  -> Wrote {len(rows)} rows to {path.name}")


def make_row(country, plan_type, fixed, mobile, sms, notes):
    return {
        "brand": "Maxis",
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


async def main():
    print("=" * 52)
    print("Maxis IDD Scraper (tab-aware)")
    print("=" * 52)

    html_path = BASE / "data" / "html_debug" / "maxis_idd.html"
    soup0 = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    sel = soup0.find("select", {"name": "roaming-dropdown"})
    if not sel:
        print("[ERROR] roaming-dropdown not found in debug HTML")
        return

    countries = []
    for opt in sel.find_all("option"):
        v = opt.get("value", "").strip()
        if v:
            countries.append(v)
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

        for i, val in enumerate(countries):
            country = clean_name(val)
            pp_fixed = pp_mobile = pp_sms = None
            po_fixed = po_mobile = po_sms = None
            pp_notes = po_notes = ""

            try:
                await page.select_option('select[name="roaming-dropdown"]', value=val)
                await page.wait_for_timeout(1800)

                # Prepaid tab
                await page.locator("a.nav-link", has_text="Hotlink Prepaid").first.click()
                await page.wait_for_timeout(600)
                soup = BeautifulSoup(await page.content(), "lxml")
                pane = get_active_pane(soup)
                pp_fixed, pp_mobile, pp_sms, pp_notes = extract_maxis_tab_rates(pane)

                # Postpaid tab
                await page.locator("a.nav-link", has_text="Hotlink Postpaid").first.click()
                await page.wait_for_timeout(600)
                soup = BeautifulSoup(await page.content(), "lxml")
                pane = get_active_pane(soup)
                po_fixed, po_mobile, po_sms, po_notes = extract_maxis_tab_rates(pane)

            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  [WARN] {country}: {type(e).__name__}: {str(e)[:70]}")

            rows.append(make_row(country, "prepaid",  pp_fixed, pp_mobile, pp_sms, pp_notes))
            rows.append(make_row(country, "postpaid", po_fixed, po_mobile, po_sms, po_notes))

            if (i + 1) % 25 == 0:
                print(f"  Progress: {i+1}/{len(countries)} | failures: {failed}")

        await ctx.close()
        await browser.close()

    print(f"\n  Done: {len(rows)} rows, {failed} failures")
    write_csv(SOURCE / "maxis_idd.csv", rows)

    import pandas as pd
    df = pd.read_csv(SOURCE / "maxis_idd.csv")
    sms_ok = df["rate_per_sms_myr"].notna().sum()
    call_ok = df["rate_per_min_myr"].notna().sum()
    print(f"  Call rate filled: {call_ok}/{len(df)}")
    print(f"  SMS filled:       {sms_ok}/{len(df)}")
    print("\n  Sample (prepaid):")
    print(df[df["plan_type"]=="prepaid"][
        ["country","rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr","notes"]
    ].head(5).to_string())
    print("\n  Sample (postpaid):")
    print(df[df["plan_type"]=="postpaid"][
        ["country","rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr","notes"]
    ].head(5).to_string())


asyncio.run(main())

