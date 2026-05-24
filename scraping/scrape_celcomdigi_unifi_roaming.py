"""
scrape_celcomdigi_unifi_roaming.py

Scrapes per-country roaming voice & SMS rates for CelcomDigi and Unifi.

CelcomDigi: https://www.celcomdigi.com/roaming/multi-day-pass#check
  - <select id="country-list"> with 193 countries
  - Rates in div.cd-roaming-table-content-block elements

Unifi: https://unifi.com.my/mobile/roaming
  - Bootstrap dropdown (button#roaming-options + a.dropdown-item)
  - Rates in .roaming-box elements

Outputs: celcomdigi_roaming.csv, unifi_roaming.csv
"""
import asyncio, re, csv, sys
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

BASE   = Path(__file__).parent
SOURCE = BASE / "data" / "source"
SCRAPED_AT = datetime.now().isoformat(timespec="seconds")

REGION_MAP = {
    "Singapore": "Southeast Asia", "Malaysia": "Southeast Asia", "Thailand": "Southeast Asia",
    "Indonesia": "Southeast Asia", "Vietnam": "Southeast Asia", "Philippines": "Southeast Asia",
    "Cambodia": "Southeast Asia", "Myanmar": "Southeast Asia", "Laos": "Southeast Asia",
    "Brunei": "Southeast Asia", "East Timor": "Southeast Asia", "Timor-Leste": "Southeast Asia",
    "Japan": "East Asia", "South Korea": "East Asia", "China": "East Asia",
    "Hong Kong": "East Asia", "Taiwan": "East Asia", "Macau": "East Asia",
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe",
    "Italy": "Europe", "Spain": "Europe", "Netherlands": "Europe", "Sweden": "Europe",
    "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe", "Switzerland": "Europe",
    "Austria": "Europe", "Belgium": "Europe", "Portugal": "Europe", "Greece": "Europe",
    "Poland": "Europe", "Turkey": "Europe", "Russia": "Europe", "Ireland": "Europe",
    "Ukraine": "Europe", "Iceland": "Europe",
    "Saudi Arabia": "Middle East", "United Arab Emirates": "Middle East",
    "Qatar": "Middle East", "Kuwait": "Middle East", "Bahrain": "Middle East",
    "Oman": "Middle East", "Jordan": "Middle East", "Iraq": "Middle East",
    "Iran": "Middle East", "Egypt": "Middle East", "Morocco": "Africa",
    "India": "South Asia", "Pakistan": "South Asia", "Bangladesh": "South Asia",
    "Sri Lanka": "South Asia", "Nepal": "South Asia", "Afghanistan": "South Asia",
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "Brazil": "South America", "Argentina": "South America", "Chile": "South America",
}

def get_region(country):
    c = str(country).strip()
    if c in REGION_MAP:
        return REGION_MAP[c]
    for k, v in REGION_MAP.items():
        if k.lower() in c.lower():
            return v
    return "Other"

def extract_cc(text):
    m = re.search(r'\(\+?([\d]+)\)', str(text))
    return m.group(1) if m else ""

COLS = [
    "record_id", "brand", "country", "region", "plan_type",
    "rate_per_min_myr", "rate_fixed_per_min_myr", "rate_per_sms_myr",
    "country_code", "access_code", "plan_specific", "notes", "source_url", "scraped_at"
]

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r["record_id"] = i
            w.writerow(r)
    print(f"  -> Wrote {len(rows)} rows to {path.name}")

def make_row(brand, country, cc, rate_within, rate_to_malaysia, rate_sms, notes_str, url):
    return {
        "brand": brand,
        "country": country,
        "region": get_region(country),
        "plan_type": "roaming",
        "rate_per_min_myr": rate_within,
        "rate_fixed_per_min_myr": rate_to_malaysia,
        "rate_per_sms_myr": rate_sms,
        "country_code": cc,
        "access_code": "",
        "plan_specific": False,
        "notes": notes_str,
        "source_url": url,
        "scraped_at": SCRAPED_AT,
    }


def parse_celcomdigi_rates(soup):
    """
    Extract rates from div.cd-roaming-table-content-block elements.
    Each block contains one rate, e.g. 'RM6.00 / min within country'.
    Returns: (within, to_malaysia, to_other, receiving, sms)
    """
    within = to_malaysia = to_other = receiving = sms = None

    for block in soup.find_all(class_="cd-roaming-table-content-block"):
        txt = block.get_text(separator=" ", strip=True)
        txt_l = txt.lower()

        m_min = re.search(r'RM\s*([\d.]+)\s*/\s*min', txt, re.I)
        m_sms = re.search(r'RM\s*([\d.]+)\s*/\s*SMS', txt, re.I)

        if m_min:
            val = float(m_min.group(1))
            if 'within' in txt_l and within is None:
                within = val
            elif 'malaysia' in txt_l and to_malaysia is None:
                to_malaysia = val
            elif 'other' in txt_l and to_other is None:
                to_other = val
            elif 'receiv' in txt_l and receiving is None:
                receiving = val

        if m_sms and sms is None:
            sms = float(m_sms.group(1))

        if all(x is not None for x in [within, to_malaysia, to_other, receiving, sms]):
            break

    return within, to_malaysia, to_other, receiving, sms


def parse_unifi_rates(soup):
    """
    Extract rates from .roaming-box elements.
    Boxes use '|'-separated text; RM and value are in a single token e.g. 'RM 1.40'.
    Returns: (outgoing_within, outgoing_to_malaysia, outgoing_to_other, incoming, sms)
    """
    out_within = out_to_malaysia = out_to_other = incoming = sms = None

    for box in soup.find_all(class_=re.compile(r'roaming-box', re.I)):
        tokens = [t.strip() for t in box.get_text(separator="|").split("|") if t.strip()]
        if not tokens:
            continue
        heading = tokens[0].lower()

        if 'outgoing' in heading:
            for i, tok in enumerate(tokens):
                m = re.match(r'^RM\s+([\d.]+)$', tok)
                if m and i + 1 < len(tokens) and '/min' in tokens[i + 1].lower():
                    val = float(m.group(1))
                    ctx = tokens[i + 2].lower() if i + 2 < len(tokens) else ""
                    if 'malaysia' in ctx and out_to_malaysia is None:
                        out_to_malaysia = val
                    elif 'other' in ctx and out_to_other is None:
                        out_to_other = val
                    elif 'within' in ctx and out_within is None:
                        out_within = val
                    elif out_within is None:
                        out_within = val

        elif 'incoming' in heading:
            for i, tok in enumerate(tokens):
                m = re.match(r'^RM\s+([\d.]+)$', tok)
                if m and i + 1 < len(tokens) and '/min' in tokens[i + 1].lower():
                    incoming = float(m.group(1))
                    break

        elif heading == 'sms':
            for i, tok in enumerate(tokens):
                m = re.match(r'^RM\s+([\d.]+)$', tok)
                if m and i + 1 < len(tokens) and '/sms' in tokens[i + 1].lower():
                    sms = float(m.group(1))
                    break

    return out_within, out_to_malaysia, out_to_other, incoming, sms


async def scrape_celcomdigi(browser):
    url = "https://www.celcomdigi.com/roaming/multi-day-pass#check"
    print(f"\n=== CelcomDigi ===")

    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()
    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    content = await page.content()
    soup0 = BeautifulSoup(content, "lxml")
    sel = soup0.find("select", id="country-list")
    if not sel:
        print("  [ERROR] select#country-list not found")
        await ctx.close()
        return []

    countries = []
    for opt in sel.find_all("option"):
        v = opt.get("value", "").strip()
        if v:
            countries.append(v)
    print(f"  {len(countries)} countries in dropdown")

    rows = []
    failed = 0

    for i, val in enumerate(countries):
        country_clean = re.sub(r'\s*\(\+[\d]+\)', '', val).strip()
        cc = extract_cc(val)

        try:
            await page.select_option("select#country-list", value=val)
            await page.wait_for_timeout(2000)

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            within, to_malaysia, to_other, receiving, sms = parse_celcomdigi_rates(soup)

            notes_parts = []
            if to_other is not None:
                notes_parts.append(f"to_other={to_other}/min")
            if receiving is not None:
                notes_parts.append(f"receiving={receiving}/min")

            rows.append(make_row(
                "CelcomDigi", country_clean, cc,
                within, to_malaysia, sms,
                "; ".join(notes_parts), url
            ))

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [WARN] {val}: {type(e).__name__}: {str(e)[:80]}")

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(countries)} | failures: {failed}")

    await ctx.close()
    print(f"  Done: {len(rows)} rows, {failed} failures")
    return rows


async def scrape_unifi(browser):
    url = "https://unifi.com.my/mobile/roaming"
    print(f"\n=== Unifi ===")

    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()
    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)

    # Get the country list by opening the country dropdown once and reading only those items.
    # This avoids picking up navigation menu items that also use .dropdown-item class.
    await page.click("button#roaming-options")
    await page.wait_for_timeout(800)
    countries = await page.locator(".dropdown-menu.show a.dropdown-item").all_text_contents()
    countries = [c.strip() for c in countries if c.strip()]
    # Close the dropdown
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    print(f"  {len(countries)} countries in country dropdown")

    rows = []
    failed = 0
    skipped_no_rates = 0

    for i, country in enumerate(countries):
        try:
            await page.click("button#roaming-options")
            await page.wait_for_timeout(500)

            # Scope to .dropdown-menu.show so we only target the open country dropdown
            link = page.locator(".dropdown-menu.show a.dropdown-item").filter(has_text=country).first
            await link.click(timeout=10000)
            await page.wait_for_timeout(2000)

            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            out_within, out_to_malaysia, out_to_other, incoming, sms = parse_unifi_rates(soup)

            if out_within is None and out_to_malaysia is None and sms is None:
                skipped_no_rates += 1
                continue

            notes_parts = []
            if out_to_other is not None:
                notes_parts.append(f"to_other={out_to_other}/min")
            if incoming is not None:
                notes_parts.append(f"incoming={incoming}/min")

            rows.append(make_row(
                "Unifi", country, "",
                out_within, out_to_malaysia, sms,
                "; ".join(notes_parts), url
            ))

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [WARN] {country}: {type(e).__name__}: {str(e)[:80]}")

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(countries)} | failures: {failed} | skipped: {skipped_no_rates}")

    await ctx.close()
    print(f"  Done: {len(rows)} rows, {failed} failures, {skipped_no_rates} skipped (no rates)")
    return rows


async def main():
    print("=" * 52)
    print("CelcomDigi + Unifi Roaming Scraper")
    print("=" * 52)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])

        cd_rows = await scrape_celcomdigi(browser)
        if cd_rows:
            write_csv(SOURCE / "celcomdigi_roaming.csv", cd_rows)

        uni_rows = await scrape_unifi(browser)
        if uni_rows:
            write_csv(SOURCE / "unifi_roaming.csv", uni_rows)

        await browser.close()

    print("\n--- Summary ---")
    for brand, rows in [("CelcomDigi", cd_rows), ("Unifi", uni_rows)]:
        if rows:
            filled = sum(1 for r in rows if r["rate_per_min_myr"] is not None)
            print(f"  {brand}: {len(rows)} rows, {filled} with call rate")
        else:
            print(f"  {brand}: 0 rows")


if __name__ == "__main__":
    asyncio.run(main())
