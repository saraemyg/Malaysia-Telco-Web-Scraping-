"""
scrape_idd_playwright.py
Scrapes IDD rates for: redONE, U Mobile, CelcomDigi, Unifi Mobile
Uses Playwright async API for dynamic pages.
Outputs individual CSVs: redone_idd.csv, umobile_idd.csv,
                          celcomdigi_idd.csv, unifi_idd.csv
"""

import asyncio, re, csv, json, time
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright

BASE   = Path(__file__).parent
SOURCE = BASE / "data" / "source"
SCRAPED_AT = datetime.now().isoformat(timespec="seconds")

REGION_MAP = {
    "Singapore":"Southeast Asia","Malaysia":"Southeast Asia","Thailand":"Southeast Asia",
    "Indonesia":"Southeast Asia","Vietnam":"Southeast Asia","Philippines":"Southeast Asia",
    "Cambodia":"Southeast Asia","Myanmar":"Southeast Asia","Laos":"Southeast Asia",
    "Brunei":"Southeast Asia","East Timor":"Southeast Asia","Timor-Leste":"Southeast Asia",
    "Japan":"East Asia","South Korea":"East Asia","China":"East Asia",
    "Hong Kong":"East Asia","Taiwan":"East Asia","Macau":"East Asia",
    "Australia":"Oceania","New Zealand":"Oceania","Fiji":"Oceania",
    "Papua New Guinea":"Oceania","Guam":"Oceania","Samoa":"Oceania",
    "United Kingdom":"Europe","France":"Europe","Germany":"Europe",
    "Italy":"Europe","Spain":"Europe","Netherlands":"Europe","Sweden":"Europe",
    "Norway":"Europe","Denmark":"Europe","Finland":"Europe","Switzerland":"Europe",
    "Austria":"Europe","Belgium":"Europe","Portugal":"Europe","Greece":"Europe",
    "Poland":"Europe","Czech Republic":"Europe","Hungary":"Europe","Romania":"Europe",
    "Bulgaria":"Europe","Croatia":"Europe","Serbia":"Europe","Slovakia":"Europe",
    "Slovenia":"Europe","Estonia":"Europe","Latvia":"Europe","Lithuania":"Europe",
    "Turkey":"Europe","Ireland":"Europe","Ukraine":"Europe","Russia":"Europe",
    "Bosnia Herzegovina":"Europe","Albania":"Europe","North Macedonia":"Europe",
    "Montenegro":"Europe","Kosovo":"Europe","Belarus":"Europe","Moldova":"Europe",
    "Saudi Arabia":"Middle East","United Arab Emirates":"Middle East",
    "Qatar":"Middle East","Kuwait":"Middle East","Bahrain":"Middle East",
    "Oman":"Middle East","Jordan":"Middle East","Iraq":"Middle East",
    "Iran":"Middle East","Lebanon":"Middle East","Israel":"Middle East",
    "Yemen":"Middle East","Palestine":"Middle East","Syria":"Middle East",
    "Egypt":"Middle East","Libya":"Middle East","Tunisia":"Africa",
    "Morocco":"Africa","Algeria":"Africa","Sudan":"Africa","Ethiopia":"Africa",
    "Kenya":"Africa","Nigeria":"Africa","Ghana":"Africa","Tanzania":"Africa",
    "Uganda":"Africa","Zimbabwe":"Africa","Zambia":"Africa","Cameroon":"Africa",
    "India":"South Asia","Pakistan":"South Asia","Bangladesh":"South Asia",
    "Sri Lanka":"South Asia","Nepal":"South Asia","Afghanistan":"South Asia",
    "Maldives":"South Asia","Bhutan":"South Asia",
    "United States":"North America","Canada":"North America","Mexico":"North America",
    "Brazil":"South America","Argentina":"South America","Chile":"South America",
    "Colombia":"South America","Peru":"South America","Venezuela":"South America",
    "Ecuador":"South America","Bolivia":"South America","Paraguay":"South America",
    "Uruguay":"South America","Guyana":"South America",
}

def get_region(country):
    c = str(country).strip()
    if c in REGION_MAP:
        return REGION_MAP[c]
    for k, v in REGION_MAP.items():
        if k.lower() in c.lower():
            return v
    return "Other"

def clean_name(text):
    return re.sub(r'\s*\(\+?[\d\-]+\)\s*', '', str(text)).strip()

def extract_cc(text):
    m = re.search(r'\(\+?([\d]+)\)', str(text))
    return m.group(1) if m else ""

def extract_rates_from_html(html):
    """Pull (fixed_rate, mobile_rate) from rendered HTML chunk."""
    soup = BeautifulSoup(html, "lxml")
    nums = []
    # h5 / h4 / strong tags with bare numbers
    for tag in soup.find_all(["h5","h4","h3","strong","span","td","div"]):
        t = tag.get_text(strip=True)
        if re.match(r'^\d+\.?\d*$', t):
            try:
                v = float(t)
                if 0.05 <= v <= 100:
                    nums.append(v)
            except: pass
    # RM X.XX patterns
    for m in re.finditer(r'RM\s*(\d+\.?\d*)', html, re.I):
        try:
            v = float(m.group(1))
            if 0.05 <= v <= 100:
                nums.append(v)
        except: pass
    # Deduplicate preserving order
    seen = set()
    uniq = []
    for v in nums:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    rate_fixed  = uniq[0] if uniq else None
    rate_mobile = uniq[1] if len(uniq) > 1 else rate_fixed
    return rate_fixed, rate_mobile

IDD_COLS = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "country_code","access_code","plan_specific","notes","source_url","scraped_at"
]

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IDD_COLS)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r["record_id"] = i
            w.writerow(r)
    print(f"  -> Wrote {len(rows)} rows to {path.name}")

def make_row(brand, country, cc, plan_type, rate_fixed, rate_mobile,
             access_code, source_url, notes=""):
    return {
        "brand": brand,
        "country": country,
        "region": get_region(country),
        "plan_type": plan_type,
        "rate_per_min_myr": rate_mobile,
        "rate_fixed_per_min_myr": rate_fixed,
        "rate_per_sms_myr": None,
        "country_code": cc,
        "access_code": access_code,
        "plan_specific": False,
        "notes": notes,
        "source_url": source_url,
        "scraped_at": SCRAPED_AT,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# REDONE  â€” Playwright on live site, iterate dropdown
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def scrape_redone(browser):
    print("\n=== redONE ===")
    URL = "https://www.redonemobile.com.my/en/idd/"

    # Get country list from local HTML (already has full list)
    html_path = BASE / "data" / "html_debug" / "redone_idd.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    sel = soup.find("select", class_="jet-select__control")
    if not sel:
        print("  [ERROR] dropdown not found in local HTML")
        return []

    raw_countries = []
    for opt in sel.find_all("option"):
        v = opt.get("value", "").strip().lstrip("ï»¿")
        if v:
            raw_countries.append(v)
    print(f"  {len(raw_countries)} countries in dropdown")

    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()

    print("  Loading redONE IDD page...")
    try:
        await page.goto(URL, timeout=30000, wait_until="networkidle")
    except Exception as e:
        print(f"  [WARN] page load: {e}")

    # Wait for the jet-select to be ready
    try:
        await page.wait_for_selector("select.jet-select__control", timeout=10000)
    except:
        print("  [WARN] jet-select not visible, trying anyway")

    rows = []
    failed = 0

    for i, raw in enumerate(raw_countries):
        country = clean_name(raw)
        cc      = extract_cc(raw)

        try:
            # Select country in the JetEngine filter dropdown
            await page.select_option("select.jet-select__control", value=raw)
            # Wait for listing to update (jet-listing-grid reloads via AJAX)
            await page.wait_for_timeout(1200)

            # Extract rates from the updated listing
            listing_html = await page.inner_html(".jet-listing-grid__items")
            rate_fixed, rate_mobile = extract_rates_from_html(listing_html)

        except Exception as e:
            rate_fixed, rate_mobile = None, None
            failed += 1
            if failed <= 5:
                print(f"  [WARN] {country}: {e}")

        for pt in ("prepaid", "postpaid"):
            rows.append(make_row("redONE", country, cc, pt,
                                 rate_fixed, rate_mobile, "+", URL))

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(raw_countries)}")

    await ctx.close()
    print(f"  Done: {len(rows)} rows, {failed} failures")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# U MOBILE  â€” Playwright on u.com.my, iterate custom dropdown
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _parse_umobile_rates(soup_idd):
    """
    Extract (rate_fixed, rate_mobile, prepaid_fixed, prepaid_mobile, postpaid_fixed, postpaid_mobile)
    from the roaming-idd component soup after country selection.
    Returns (prepaid_fixed, prepaid_mobile, postpaid_fixed, postpaid_mobile).
    RM and its value are in separate tags; parse via get_text with separator.
    """
    # Remove dropdown options to avoid noise
    for el in soup_idd.find_all(class_=re.compile(r'menu-list')):
        el.decompose()

    text = soup_idd.get_text(separator="||", strip=True)
    tokens = [t.strip() for t in text.split("||") if t.strip()]

    # Find all /min call rates and their context
    call_rates = []   # list of (val, line_type, section)
    current_section = "prepaid"
    for i, tok in enumerate(tokens):
        tl = tok.lower()
        if "postpaid" in tl:
            current_section = "postpaid"
        elif any(w in tl for w in ("idd call rates",)):
            current_section = "prepaid"

        if tok == "RM" and i + 1 < len(tokens):
            try:
                val = float(tokens[i + 1])
                if not (0.05 <= val <= 50):
                    continue
                unit = tokens[i + 2] if i + 2 < len(tokens) else ""
                if "/min" not in unit:
                    continue
                # Determine line type from nearby tokens
                ctx_tokens = tokens[i + 3 : i + 7]
                ctx = " ".join(ctx_tokens).lower()
                if "fixed" in ctx and "mobile" in ctx:
                    line = "both"
                elif "mobile" in ctx:
                    line = "mobile"
                elif "fixed" in ctx:
                    line = "fixed"
                else:
                    line = "both"
                call_rates.append((val, line, current_section))
            except Exception:
                pass

    if not call_rates:
        return None, None, None, None

    def pick(section, line):
        # Prefer the given section; fall back to any section
        for v, l, s in call_rates:
            if s == section and (l == line or l == "both"):
                return v
        for v, l, s in call_rates:
            if l == line or l == "both":
                return v
        return call_rates[0][0]

    pp_fixed  = pick("prepaid",  "fixed")
    pp_mobile = pick("prepaid",  "mobile")
    po_fixed  = pick("postpaid", "fixed")
    po_mobile = pick("postpaid", "mobile")
    return pp_fixed, pp_mobile, po_fixed, po_mobile


async def scrape_umobile(browser):
    print("\n=== U Mobile ===")
    URL = "https://www.u.com.my/en/personal/mobile-plans/roam-travel/international-direct-dial"

    # Country list from local HTML
    html_path = BASE / "data" / "html_debug" / "umobile_idd.html"
    soup0 = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    raw_countries = []
    for div in soup0.find_all("div", role="option", attrs={"data-value": True}):
        v = div["data-value"].strip()
        if v:
            raw_countries.append(v)
    print(f"  {len(raw_countries)} countries in dropdown")

    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()

    print("  Loading U Mobile IDD page...")
    try:
        await page.goto(URL, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  [WARN] page load: {e}")
    await page.wait_for_timeout(4000)  # let Vue mount

    # Scroll to IDD component so it's in the viewport
    idd_el = page.locator('[data-component="roaming-idd"]').first
    if await idd_el.count() > 0:
        await idd_el.scroll_into_view_if_needed()
    await page.wait_for_timeout(500)

    rows = []
    failed = 0

    for i, raw in enumerate(raw_countries):
        country = clean_name(raw)
        cc      = extract_cc(raw)
        pp_fixed = pp_mobile = po_fixed = po_mobile = None

        try:
            # Click the IDD dropdown trigger to open menu
            trigger = page.locator(".vue-single-select.input-select").first
            await trigger.click()
            await page.wait_for_timeout(600)

            # Click the matching option (it's in the DOM, visible when menu is open)
            escaped = raw.replace('"', '\\"')
            opt = page.locator(f'[data-value="{escaped}"]').first
            if await opt.count() > 0:
                await opt.click(force=True)
            else:
                failed += 1
                if failed <= 5:
                    print(f"  [WARN] {country}: option not found")
                raise ValueError("option not found")

            # Wait for Vue to render the rates
            await page.wait_for_timeout(3000)

            # Extract from roaming-idd component
            content = await page.content()
            soup2 = BeautifulSoup(content, "lxml")
            idd_comp = soup2.find(attrs={"data-component": "roaming-idd"})
            if idd_comp:
                pp_fixed, pp_mobile, po_fixed, po_mobile = _parse_umobile_rates(idd_comp)

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [WARN] {country}: {type(e).__name__}: {str(e)[:80]}")
            # Recover by reloading the page every 15 failures
            if failed % 15 == 0:
                try:
                    await page.goto(URL, timeout=20000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    idd_el2 = page.locator('[data-component="roaming-idd"]').first
                    if await idd_el2.count() > 0:
                        await idd_el2.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

        rows.append(make_row("U Mobile", country, cc, "prepaid",
                             pp_fixed, pp_mobile, "133", URL))
        rows.append(make_row("U Mobile", country, cc, "postpaid",
                             po_fixed, po_mobile, "133", URL))

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(raw_countries)} | failures: {failed}")

    await ctx.close()
    print(f"  Done: {len(rows)} rows, {failed} failures")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CELCOMDIGI â€” probe URLs, parse rate table or dropdown
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

CELCOM_CANDIDATES = [
    "https://www.celcomdigi.com/calls-messaging/idd",
    "https://www.celcomdigi.com/personal/calls-messaging/idd",
    "https://www.celcomdigi.com/calls/idd",
    "https://www.celcomdigi.com/en/calls-messaging/idd",
    "https://www.celcomdigi.com/personal/idd",
    "https://www.celcomdigi.com/postpaid/idd",
    "https://www.celcomdigi.com/prepaid/idd",
    "https://www.celcomdigi.com/postpaid/add-ons/idd",
    "https://www.celcomdigi.com/prepaid/add-ons/idd",
]

async def scrape_celcomdigi(browser):
    print("\n=== CelcomDigi ===")
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()

    live_url = None
    for url in CELCOM_CANDIDATES:
        try:
            resp = await page.goto(url, timeout=12000, wait_until="domcontentloaded")
            status = resp.status if resp else 0
            if status == 200:
                content = await page.content()
                has_idd = bool(re.search(r'idd|international.*dial|call.*rate|per.min', content, re.I))
                is_404  = bool(re.search(r'not found|404|page.+not.+exist', content[:3000], re.I))
                if has_idd and not is_404:
                    live_url = url
                    print(f"  Found: {url}")
                    break
                else:
                    print(f"  [skip] {url} (status {status}, idd={has_idd}, 404={is_404})")
            else:
                print(f"  [skip] {url} -> HTTP {status}")
        except Exception as e:
            print(f"  [skip] {url}: {type(e).__name__}")

    if not live_url:
        print("  [RESULT] No CelcomDigi IDD page found â€” 0 rows")
        await ctx.close()
        return []

    await page.wait_for_timeout(2000)
    content = await page.content()
    soup = BeautifulSoup(content, "lxml")

    rows = []

    # Try rate table first
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(k in " ".join(ths) for k in ("country","destination","nation")):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            country = clean_name(tds[0])
            if not country:
                continue
            m1 = re.search(r'(\d+\.?\d*)', tds[1])
            rate_mobile = float(m1.group(1)) if m1 else None
            rate_fixed  = None
            if len(tds) > 2:
                m2 = re.search(r'(\d+\.?\d*)', tds[2])
                rate_fixed = float(m2.group(1)) if m2 else rate_mobile
            else:
                rate_fixed = rate_mobile
            for pt in ("prepaid","postpaid"):
                rows.append(make_row("CelcomDigi", country, "", pt,
                                     rate_fixed, rate_mobile, "+", live_url))

    if rows:
        await ctx.close()
        print(f"  Table parse: {len(rows)} rows")
        return rows

    # Try dropdown
    sel = soup.find("select")
    if sel:
        opts = [(o.get("value",""), o.get_text(strip=True))
                for o in sel.find_all("option") if o.get("value","")]
        for val, label in opts:
            country = clean_name(label)
            cc = extract_cc(label)
            try:
                await page.select_option("select", value=val)
                await page.wait_for_timeout(800)
                chunk = await page.content()
                rate_fixed, rate_mobile = extract_rates_from_html(chunk)
            except:
                rate_fixed = rate_mobile = None
            for pt in ("prepaid","postpaid"):
                rows.append(make_row("CelcomDigi", country, cc, pt,
                                     rate_fixed, rate_mobile, "+", live_url))

    await ctx.close()
    print(f"  {len(rows)} rows")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UNIFI MOBILE â€” probe URLs, parse rate table or dropdown
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

UNIFI_CANDIDATES = [
    "https://unifi.com.my/mobile/idd",
    "https://www.unifi.com.my/mobile/idd",
    "https://unifi.com.my/home/mobile/add-ons/idd",
    "https://www.unifi.com.my/home/mobile/add-ons/idd",
    "https://unifi.com.my/personal/mobile/idd",
    "https://unifi.com.my/mobile/international-call",
    "https://unifi.com.my/mobile/idd-rates",
    "https://unifi.com.my/mobile/calling",
    "https://unifi.com.my/mobile/add-ons",
]

async def scrape_unifi(browser):
    print("\n=== Unifi Mobile ===")
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await ctx.new_page()

    live_url = None
    for url in UNIFI_CANDIDATES:
        try:
            resp = await page.goto(url, timeout=12000, wait_until="domcontentloaded")
            status = resp.status if resp else 0
            if status == 200:
                content = await page.content()
                has_idd  = bool(re.search(r'idd|international.*dial|call.*rate|per.min|destination', content, re.I))
                is_404   = bool(re.search(r'not found|404|page.+not.+exist', content[:3000], re.I))
                if has_idd and not is_404:
                    live_url = url
                    print(f"  Found: {url}")
                    break
                else:
                    print(f"  [skip] {url} (idd={has_idd}, 404={is_404})")
            else:
                print(f"  [skip] {url} -> HTTP {status}")
        except Exception as e:
            print(f"  [skip] {url}: {type(e).__name__}")

    if not live_url:
        print("  [RESULT] No Unifi IDD page found â€” 0 rows")
        await ctx.close()
        return []

    await page.wait_for_timeout(2000)
    content = await page.content()
    soup = BeautifulSoup(content, "lxml")
    rows = []

    # Try rate table
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(k in " ".join(ths) for k in ("country","destination")):
            continue
        for tr in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            country = clean_name(tds[0])
            if not country:
                continue
            m1 = re.search(r'(\d+\.?\d*)', tds[1])
            rate_mobile = float(m1.group(1)) if m1 else None
            rate_fixed  = None
            if len(tds) > 2:
                m2 = re.search(r'(\d+\.?\d*)', tds[2])
                rate_fixed = float(m2.group(1)) if m2 else rate_mobile
            else:
                rate_fixed = rate_mobile
            for pt in ("prepaid","postpaid"):
                rows.append(make_row("Unifi Mobile", country, "", pt,
                                     rate_fixed, rate_mobile, "", live_url))
        if rows:
            break

    if rows:
        await ctx.close()
        print(f"  Table parse: {len(rows)} rows")
        return rows

    # Try select dropdown
    sel = soup.find("select")
    if sel:
        opts = [(o.get("value",""), o.get_text(strip=True))
                for o in sel.find_all("option") if o.get("value","")]
        for val, label in opts:
            country = clean_name(label)
            cc = extract_cc(label)
            try:
                await page.select_option("select", value=val)
                await page.wait_for_timeout(800)
                chunk = await page.content()
                rate_fixed, rate_mobile = extract_rates_from_html(chunk)
            except:
                rate_fixed = rate_mobile = None
            for pt in ("prepaid","postpaid"):
                rows.append(make_row("Unifi Mobile", country, cc, pt,
                                     rate_fixed, rate_mobile, "", live_url))

    await ctx.close()
    print(f"  {len(rows)} rows")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def main():
    print("=" * 52)
    print("IDD Playwright Scraper â€” redONE / U Mobile / CelcomDigi / Unifi")
    print("=" * 52)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])

        ro_rows  = await scrape_redone(browser)
        um_rows  = await scrape_umobile(browser)
        cd_rows  = await scrape_celcomdigi(browser)
        uni_rows = await scrape_unifi(browser)

        await browser.close()

    if ro_rows:
        write_csv(BASE / "redone_idd.csv", ro_rows)
    if um_rows:
        write_csv(SOURCE / "umobile_idd.csv", um_rows)
    if cd_rows:
        write_csv(BASE / "celcomdigi_idd.csv", cd_rows)
    if uni_rows:
        write_csv(BASE / "unifi_idd.csv", uni_rows)

    print("\n--- Summary ---")
    for brand, rows, f in [
        ("redONE",       ro_rows,  "redone_idd.csv"),
        ("U Mobile",     um_rows,  "umobile_idd.csv"),
        ("CelcomDigi",   cd_rows,  "celcomdigi_idd.csv"),
        ("Unifi Mobile", uni_rows, "unifi_idd.csv"),
    ]:
        s = f"{len(rows)} rows -> {f}" if rows else "0 rows (page not found)"
        print(f"  {brand:15s}: {s}")


if __name__ == "__main__":
    asyncio.run(main())

