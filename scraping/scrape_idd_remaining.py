"""
scrape_idd_remaining.py
Scrapes IDD rates for 5 remaining brands:
  - Tune Talk  : WP AJAX  action=load_idd_data  (post IDs from local HTML)
  - redONE     : WP REST API /wp/v2/idd-listing  (fallback: JetSmartFilter AJAX)
  - U Mobile   : Playwright dropdown iteration
  - CelcomDigi : Playwright (tries several URL candidates)
  - Unifi Mobile: Playwright (finds IDD rate table)

Output: individual CSVs per brand in e:/DV/
  tunetalk_idd.csv, redone_idd.csv, umobile_idd.csv,
  celcomdigi_idd.csv (or empty if page not found),
  unifi_idd.csv
"""

import os, re, json, time, csv
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

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
    "Papua New Guinea":"Oceania","Guam":"Oceania",
    "United Kingdom":"Europe","France":"Europe","Germany":"Europe",
    "Italy":"Europe","Spain":"Europe","Netherlands":"Europe","Sweden":"Europe",
    "Norway":"Europe","Denmark":"Europe","Finland":"Europe","Switzerland":"Europe",
    "Austria":"Europe","Belgium":"Europe","Portugal":"Europe","Greece":"Europe",
    "Poland":"Europe","Czech Republic":"Europe","Hungary":"Europe","Romania":"Europe",
    "Bulgaria":"Europe","Croatia":"Europe","Serbia":"Europe","Slovakia":"Europe",
    "Slovenia":"Europe","Estonia":"Europe","Latvia":"Europe","Lithuania":"Europe",
    "Turkey":"Europe","Ireland":"Europe","Ukraine":"Europe","Russia":"Europe",
    "Saudi Arabia":"Middle East","United Arab Emirates":"Middle East",
    "Qatar":"Middle East","Kuwait":"Middle East","Bahrain":"Middle East",
    "Oman":"Middle East","Jordan":"Middle East","Iraq":"Middle East",
    "Iran":"Middle East","Lebanon":"Middle East","Israel":"Middle East",
    "Yemen":"Middle East","Egypt":"Middle East","Libya":"Middle East",
    "Tunisia":"Middle East","Morocco":"Middle East","Algeria":"Africa",
    "India":"South Asia","Pakistan":"South Asia","Bangladesh":"South Asia",
    "Sri Lanka":"South Asia","Nepal":"South Asia","Afghanistan":"South Asia",
    "Maldives":"South Asia",
    "United States":"North America","Canada":"North America","Mexico":"North America",
    "Brazil":"South America","Argentina":"South America","Chile":"South America",
    "Colombia":"South America","Peru":"South America","Venezuela":"South America",
}

def get_region(country):
    country = country.strip()
    if country in REGION_MAP:
        return REGION_MAP[country]
    for k, v in REGION_MAP.items():
        if k.lower() in country.lower() or country.lower() in k.lower():
            return v
    return "Other"

def extract_country_code(text):
    m = re.search(r'\(\+?([\d]+)\)', text)
    return m.group(1) if m else ""

def clean_country_name(text):
    name = re.sub(r'\s*\(\+?[\d\-]+\)\s*', '', text).strip()
    return name

IDD_SCHEMA = [
    "record_id","brand","country","region","plan_type",
    "rate_per_min_myr","rate_fixed_per_min_myr","rate_per_sms_myr",
    "country_code","access_code","plan_specific","notes","source_url","scraped_at"
]

def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=IDD_SCHEMA)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r["record_id"] = i
            w.writerow(r)
    print(f"  Wrote {len(rows)} rows -> {path.name}")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TUNE TALK  (WP AJAX: action=load_idd_data)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_tunetalk():
    print("\n=== Tune Talk ===")
    html_path = BASE / "data" / "html_debug" / "tunetalk_idd.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")

    # Extract country options from rth_select
    sel = soup.find("select", class_="rth_select")
    if not sel:
        print("  [WARN] rth_select dropdown not found")
        return []

    options = [(opt.get("value",""), opt.get_text(strip=True))
               for opt in sel.find_all("option")
               if opt.get("value","")]
    print(f"  Found {len(options)} countries in dropdown")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.tunetalk.com/prepaid/idd/",
        "Origin": "https://www.tunetalk.com",
    })

    rows = []
    AJAX_URL = "https://www.tunetalk.com/wp-admin/admin-ajax.php"

    for i, (post_id, label) in enumerate(options):
        country = clean_country_name(label)
        cc = extract_country_code(label)
        region = get_region(country)

        try:
            resp = session.post(AJAX_URL, data={
                "action": "load_idd_data",
                "rth_select": post_id,
                "lang": "en"
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            html_body = data.get("html", "")
        except Exception as e:
            print(f"  [WARN] {country}: {e}")
            time.sleep(1)
            continue

        # Parse rate values from response HTML
        rsoup = BeautifulSoup(html_body, "lxml")
        rate_mobile = None
        rate_fixed  = None
        rate_sms    = None

        # Look for rc_div or similar containers with rates
        rc_divs = rsoup.find_all("div", class_=re.compile(r"rc_div|rate_div|rth_rate"))
        for div in rc_divs:
            title = div.find(class_=re.compile(r"title|label|type"))
            rate  = div.find(class_=re.compile(r"rate|price|value"))
            if not title or not rate:
                continue
            title_text = title.get_text(strip=True).lower()
            rate_text  = rate.get_text(strip=True)
            m = re.search(r'(\d+\.?\d*)', rate_text)
            if not m:
                continue
            val = float(m.group(1))
            if "fix" in title_text or "land" in title_text:
                rate_fixed = val
            elif "mobile" in title_text or "cell" in title_text:
                rate_mobile = val
            elif "sms" in title_text or "text" in title_text:
                rate_sms = val

        # Fallback: scan all numeric RM patterns in response
        if rate_mobile is None:
            rm_vals = re.findall(r'RM\s*(\d+\.?\d*)', html_body)
            nums    = re.findall(r'\b(\d+\.\d{2})\b', html_body)
            all_vals = [float(v) for v in rm_vals] + [float(n) for n in nums]
            if all_vals:
                # Use the first two distinct values as fixed/mobile
                uniq = list(dict.fromkeys(all_vals))
                rate_fixed  = uniq[0] if len(uniq) > 0 else None
                rate_mobile = uniq[1] if len(uniq) > 1 else uniq[0] if uniq else None

        for plan_type in ("prepaid", "postpaid"):
            rows.append({
                "brand": "Tune Talk",
                "country": country,
                "region": region,
                "plan_type": plan_type,
                "rate_per_min_myr": rate_mobile,
                "rate_fixed_per_min_myr": rate_fixed,
                "rate_per_sms_myr": rate_sms,
                "country_code": cc,
                "access_code": "132",
                "plan_specific": False,
                "notes": "",
                "source_url": "https://www.tunetalk.com/prepaid/idd/",
                "scraped_at": SCRAPED_AT,
            })

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(options)}")
        time.sleep(0.3)

    print(f"  Total rows: {len(rows)}")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# REDONE  (WP REST API for idd-listing CPT)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_redone_rest():
    """Try WP REST API for redONE idd-listing custom post type."""
    base_url = "https://www.redonemobile.com.my/wp-json/wp/v2/idd-listing"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })

    all_posts = []
    page = 1
    while True:
        try:
            resp = session.get(base_url, params={
                "per_page": 100, "page": page, "_embed": 1
            }, timeout=15)
            if resp.status_code == 400:
                break  # no more pages
            resp.raise_for_status()
            posts = resp.json()
            if not posts:
                break
            all_posts.extend(posts)
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            print(f"  REST page {page}/{total_pages} -> {len(posts)} posts")
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  [REST ERROR page {page}] {e}")
            break

    return all_posts


def parse_redone_rest_post(post):
    """Extract country and rate from a redONE REST API post."""
    title = post.get("title", {}).get("rendered", "")
    country = BeautifulSoup(title, "lxml").get_text(strip=True)
    cc = extract_country_code(country)
    country = clean_country_name(country)

    # Try ACF fields
    acf = post.get("acf", {})
    meta = post.get("meta", {})

    # Common ACF field names for redONE IDD
    rate_fixed  = None
    rate_mobile = None
    rate_video  = None

    for src in (acf, meta):
        for k, v in src.items():
            k_lower = k.lower()
            if "fix" in k_lower:
                try: rate_fixed = float(v)
                except: pass
            elif "mobile" in k_lower or "cell" in k_lower:
                try: rate_mobile = float(v)
                except: pass
            elif "video" in k_lower:
                try: rate_video = float(v)
                except: pass

    # Fallback: parse rendered content
    if rate_fixed is None:
        content = post.get("content", {}).get("rendered", "")
        vals = re.findall(r'(\d+\.?\d*)', content)
        numeric = [float(v) for v in vals if 0.1 <= float(v) <= 50]
        if numeric:
            rate_fixed  = numeric[0]
            rate_mobile = numeric[1] if len(numeric) > 1 else numeric[0]

    return country, cc, rate_fixed, rate_mobile


def scrape_redone_playwright():
    """Fallback: use Playwright to iterate redONE country dropdown."""
    print("  Falling back to Playwright for redONE...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [ERROR] playwright not installed: py -m pip install playwright && py -m playwright install chromium")
        return []

    html_path = BASE / "data" / "html_debug" / "redone_idd.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    sel = soup.find("select", class_="jet-select__control")
    if not sel:
        return []
    countries_raw = [
        opt.get("value", "").strip()
        for opt in sel.find_all("option")
        if opt.get("value", "").strip()
    ]
    print(f"  Found {len(countries_raw)} countries via Playwright route")

    rows = []
    AJAX_URL = "https://www.redonemobile.com.my/wp-admin/admin-ajax.php"

    # Fetch fresh nonce from the page
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        page_resp = session.get("https://www.redonemobile.com.my/en/idd/", timeout=20)
        nonce_m = re.search(r'"restNonce"\s*:\s*"([a-f0-9]+)"', page_resp.text)
        nonce = nonce_m.group(1) if nonce_m else ""
        listing_id_m = re.search(r'data-listing-id="(\d+)"', page_resp.text)
        listing_id = listing_id_m.group(1) if listing_id_m else "878"
    except Exception as e:
        print(f"  [WARN] Could not refresh page for nonce: {e}")
        nonce = ""
        listing_id = "878"

    for country_raw in countries_raw:
        country = clean_country_name(country_raw)
        if country.startswith("ï»¿"):
            country = country[1:]
        cc = extract_country_code(country_raw)
        region = get_region(country)

        try:
            resp = session.post(AJAX_URL, data={
                "action": "jet_smart_filters",
                "provider": "jet-engine/default",
                "defaults": json.dumps({"lisitng_id": listing_id, "posts_num": "1"}),
                "filters": json.dumps({"meta_query": {"idd_country": country_raw.strip()}}),
                "_nonce": nonce,
            }, timeout=15)
            rsoup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"  [WARN] {country}: {e}")
            time.sleep(1)
            continue

        # Extract rate values: look for h5 elements with numeric content
        h5s = rsoup.find_all("h5")
        nums = []
        for h in h5s:
            t = h.get_text(strip=True)
            if re.match(r'^\d+\.?\d*$', t):
                try:
                    nums.append(float(t))
                except:
                    pass

        rate_fixed  = nums[0] if len(nums) > 0 else None
        rate_mobile = nums[1] if len(nums) > 1 else rate_fixed

        for plan_type in ("prepaid", "postpaid"):
            rows.append({
                "brand": "redONE",
                "country": country,
                "region": region,
                "plan_type": plan_type,
                "rate_per_min_myr": rate_mobile,
                "rate_fixed_per_min_myr": rate_fixed,
                "rate_per_sms_myr": None,
                "country_code": cc,
                "access_code": "+",
                "plan_specific": False,
                "notes": "",
                "source_url": "https://www.redonemobile.com.my/en/idd/",
                "scraped_at": SCRAPED_AT,
            })
        time.sleep(0.3)

    return rows


def scrape_redone():
    print("\n=== redONE ===")

    # Try local HTML first â€” it already renders the first country's data
    # If REST API works, that's ideal
    posts = scrape_redone_rest()

    if posts:
        rows = []
        for post in posts:
            country, cc, rate_fixed, rate_mobile = parse_redone_rest_post(post)
            if not country:
                continue
            region = get_region(country)
            for plan_type in ("prepaid", "postpaid"):
                rows.append({
                    "brand": "redONE",
                    "country": country,
                    "region": region,
                    "plan_type": plan_type,
                    "rate_per_min_myr": rate_mobile,
                    "rate_fixed_per_min_myr": rate_fixed,
                    "rate_per_sms_myr": None,
                    "country_code": cc,
                    "access_code": "+",
                    "plan_specific": False,
                    "notes": "via WP REST API",
                    "source_url": "https://www.redonemobile.com.my/en/idd/",
                    "scraped_at": SCRAPED_AT,
                })
        print(f"  REST API: {len(rows)} rows")
        return rows

    # REST API failed, try JetSmartFilter AJAX
    return scrape_redone_playwright()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# U MOBILE  (Playwright dropdown iteration)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def scrape_umobile():
    print("\n=== U Mobile ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [ERROR] playwright not installed: py -m pip install playwright && py -m playwright install chromium")
        return []

    html_path = BASE / "data" / "html_debug" / "umobile_idd.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")

    # Extract countries from the custom dropdown
    country_opts = []
    for div in soup.find_all("div", role="option", attrs={"data-value": True}):
        raw = div["data-value"].strip()
        if raw:
            country_opts.append(raw)
    print(f"  Found {len(country_opts)} countries")

    rows = []
    IDD_URL = "https://www.u.com.my/en/personal/mobile-plans/roam-travel/international-direct-dial"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = ctx.new_page()

        print("  Loading U Mobile IDD page...")
        try:
            page.goto(IDD_URL, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"  [WARN] Page load issue: {e}")

        for i, raw_val in enumerate(country_opts):
            country = clean_country_name(raw_val)
            cc = extract_country_code(raw_val)
            region = get_region(country)

            rate_fixed  = None
            rate_mobile = None
            rate_sms    = None

            try:
                # Click the dropdown trigger to open it
                trigger = page.locator(".custom-select, .dropdown-trigger, [data-value]").first
                if trigger.count() > 0:
                    trigger.click()
                    page.wait_for_timeout(300)

                # Click the matching option
                option = page.locator(f'[data-value="{raw_val}"]').first
                if option.count() > 0:
                    option.click()
                    page.wait_for_timeout(1000)

                    # Extract rates from the page
                    content = page.content()
                    rsoup = BeautifulSoup(content, "lxml")

                    # Look for rate display area
                    rate_area = rsoup.find(class_=re.compile(
                        r"idd.rate|rate.display|rate.result|idd.result|rate.table", re.I
                    ))
                    if rate_area:
                        rm_vals = re.findall(r'RM\s*(\d+\.?\d*)', rate_area.get_text())
                        if rm_vals:
                            rate_fixed  = float(rm_vals[0])
                            rate_mobile = float(rm_vals[1]) if len(rm_vals) > 1 else float(rm_vals[0])

                    # Wider search if rate area not found
                    if rate_fixed is None:
                        rm_vals = re.findall(r'RM\s*(\d+\.?\d*)/min', content)
                        nums = re.findall(r'\b(\d+\.\d{2})\b', content)
                        all_v = [float(v) for v in rm_vals] + \
                                [float(n) for n in nums if 0.1 <= float(n) <= 20]
                        if all_v:
                            uniq = list(dict.fromkeys(all_v))
                            rate_fixed  = uniq[0]
                            rate_mobile = uniq[1] if len(uniq) > 1 else uniq[0]

            except Exception as e:
                print(f"  [WARN] {country}: {e}")

            for plan_type in ("prepaid", "postpaid"):
                rows.append({
                    "brand": "U Mobile",
                    "country": country,
                    "region": region,
                    "plan_type": plan_type,
                    "rate_per_min_myr": rate_mobile,
                    "rate_fixed_per_min_myr": rate_fixed,
                    "rate_per_sms_myr": rate_sms,
                    "country_code": cc,
                    "access_code": "133",
                    "plan_specific": False,
                    "notes": "",
                    "source_url": IDD_URL,
                    "scraped_at": SCRAPED_AT,
                })

            if (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(country_opts)}")

        browser.close()

    print(f"  Total rows: {len(rows)}")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CELCOMDIGI  (Playwright â€” try several URL candidates)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

CELCOMDIGI_URL_CANDIDATES = [
    "https://www.celcomdigi.com/calls-messaging/idd",
    "https://www.celcomdigi.com/personal/calls-messaging/idd",
    "https://www.celcomdigi.com/calls/idd",
    "https://www.celcomdigi.com/en/calls-messaging/idd",
    "https://www.celcomdigi.com/personal/idd",
    "https://www.celcomdigi.com/services/idd",
    "https://www.celcomdigi.com/postpaid/idd",
    "https://www.celcomdigi.com/prepaid/idd",
]

def scrape_celcomdigi():
    print("\n=== CelcomDigi ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [ERROR] playwright not installed")
        return []

    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = ctx.new_page()

        working_url = None
        for url in CELCOMDIGI_URL_CANDIDATES:
            try:
                resp = page.goto(url, timeout=15000, wait_until="domcontentloaded")
                if resp and resp.status == 200:
                    content = page.content()
                    # Check it's a real IDD page, not 404 or homepage
                    if re.search(r'idd|international.*dial|call.*rate', content, re.I) \
                       and "not found" not in content.lower()[:2000]:
                        working_url = url
                        print(f"  Found live IDD page: {url}")
                        break
            except Exception as e:
                print(f"  [SKIP] {url}: {e}")

        if not working_url:
            print("  [WARN] No CelcomDigi IDD URL found â€” skipping")
            browser.close()
            return []

        # Wait for content to load
        page.wait_for_timeout(2000)
        content = page.content()
        soup = BeautifulSoup(content, "lxml")

        # Find country dropdown / select
        sel = soup.find("select") or \
              soup.find("div", class_=re.compile(r"dropdown|select|country", re.I))

        if sel:
            # Get country options
            country_opts = []
            if sel.name == "select":
                country_opts = [(opt.get("value",""), opt.get_text(strip=True))
                                for opt in sel.find_all("option") if opt.get("value","")]
            else:
                country_opts = [(div.get("data-value",""), div.get_text(strip=True))
                                for div in sel.find_all("[data-value]")]

            print(f"  Found {len(country_opts)} countries")

            for val, label in country_opts:
                country = clean_country_name(label)
                cc = extract_country_code(label)
                region = get_region(country)

                rate_fixed  = None
                rate_mobile = None
                rate_sms    = None

                try:
                    # Try to select country
                    if soup.find("select"):
                        page.select_option("select", value=val)
                    else:
                        page.click(f'[data-value="{val}"]')
                    page.wait_for_timeout(800)

                    updated = page.content()
                    rm_vals = re.findall(r'RM\s*(\d+\.?\d*)', updated)
                    nums = [float(v) for v in rm_vals if 0.1 <= float(v) <= 50]
                    if nums:
                        uniq = list(dict.fromkeys(nums))
                        rate_fixed  = uniq[0]
                        rate_mobile = uniq[1] if len(uniq) > 1 else uniq[0]
                except Exception as e:
                    print(f"  [WARN] {country}: {e}")

                for plan_type in ("prepaid", "postpaid"):
                    rows.append({
                        "brand": "CelcomDigi",
                        "country": country,
                        "region": region,
                        "plan_type": plan_type,
                        "rate_per_min_myr": rate_mobile,
                        "rate_fixed_per_min_myr": rate_fixed,
                        "rate_per_sms_myr": rate_sms,
                        "country_code": cc,
                        "access_code": "+",
                        "plan_specific": False,
                        "notes": "",
                        "source_url": working_url,
                        "scraped_at": SCRAPED_AT,
                    })
                time.sleep(0.3)
        else:
            # No dropdown â€” try to parse a rate table directly
            print("  No dropdown found â€” parsing rate table")
            tables = soup.find_all("table")
            for table in tables:
                for row in table.find_all("tr")[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
                    if len(cells) < 2:
                        continue
                    country = cells[0]
                    region  = get_region(country)
                    rm_m = re.search(r'(\d+\.?\d*)', cells[1])
                    rate_mobile = float(rm_m.group(1)) if rm_m else None
                    rate_fixed  = rate_mobile

                    for plan_type in ("prepaid", "postpaid"):
                        rows.append({
                            "brand": "CelcomDigi",
                            "country": country,
                            "region": region,
                            "plan_type": plan_type,
                            "rate_per_min_myr": rate_mobile,
                            "rate_fixed_per_min_myr": rate_fixed,
                            "rate_per_sms_myr": None,
                            "country_code": "",
                            "access_code": "+",
                            "plan_specific": False,
                            "notes": "",
                            "source_url": working_url,
                            "scraped_at": SCRAPED_AT,
                        })

        browser.close()

    print(f"  Total rows: {len(rows)}")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UNIFI MOBILE  (Playwright â€” find IDD page)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

UNIFI_IDD_CANDIDATES = [
    "https://unifi.com.my/mobile/idd",
    "https://www.unifi.com.my/mobile/idd",
    "https://unifi.com.my/home/mobile/add-ons/idd",
    "https://www.unifi.com.my/home/mobile/add-ons/idd",
    "https://unifi.com.my/personal/mobile/idd",
    "https://unifi.com.my/mobile/international-direct-dial",
    "https://unifi.com.my/mobile/calling-rates",
    "https://unifi.com.my/mobile/idd-rates",
]

def scrape_unifi():
    print("\n=== Unifi Mobile ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [ERROR] playwright not installed")
        return []

    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = ctx.new_page()

        working_url = None
        for url in UNIFI_IDD_CANDIDATES:
            try:
                resp = page.goto(url, timeout=15000, wait_until="domcontentloaded")
                if resp and resp.status == 200:
                    content = page.content()
                    if re.search(r'idd|international.*dial|call.*rate|per.min', content, re.I) \
                       and "not found" not in content.lower()[:3000] \
                       and "404" not in content[:500]:
                        working_url = url
                        print(f"  Found live Unifi IDD page: {url}")
                        break
            except Exception as e:
                print(f"  [SKIP] {url}: {e}")

        if not working_url:
            print("  [WARN] No Unifi IDD URL found â€” skipping")
            browser.close()
            return []

        page.wait_for_timeout(2000)
        content = page.content()
        soup = BeautifulSoup(content, "lxml")

        # Strategy 1: find a country dropdown
        sel = soup.find("select")
        country_opts = []
        if sel:
            country_opts = [(opt.get("value",""), opt.get_text(strip=True))
                            for opt in sel.find_all("option") if opt.get("value","")]
            print(f"  Dropdown with {len(country_opts)} countries")

        # Strategy 2: find a rate table
        if not country_opts:
            tables = soup.find_all("table")
            for table in tables:
                headers = [th.get_text(strip=True).lower()
                           for th in table.find_all("th")]
                if any("country" in h or "destination" in h for h in headers):
                    for row in table.find_all("tr")[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all("td")]
                        if len(cells) < 2:
                            continue
                        country = cells[0]
                        region  = get_region(country)
                        rm_m = re.search(r'(\d+\.?\d*)', cells[1])
                        rate_mobile = float(rm_m.group(1)) if rm_m else None
                        rate_fixed  = None
                        if len(cells) > 2:
                            rm2 = re.search(r'(\d+\.?\d*)', cells[2])
                            rate_fixed = float(rm2.group(1)) if rm2 else rate_mobile
                        else:
                            rate_fixed = rate_mobile

                        for plan_type in ("prepaid", "postpaid"):
                            rows.append({
                                "brand": "Unifi Mobile",
                                "country": country,
                                "region": region,
                                "plan_type": plan_type,
                                "rate_per_min_myr": rate_mobile,
                                "rate_fixed_per_min_myr": rate_fixed,
                                "rate_per_sms_myr": None,
                                "country_code": "",
                                "access_code": "",
                                "plan_specific": False,
                                "notes": "",
                                "source_url": working_url,
                                "scraped_at": SCRAPED_AT,
                            })

        # Strategy 3: dropdown interaction
        if country_opts:
            for val, label in country_opts:
                country = clean_country_name(label)
                cc = extract_country_code(label)
                region = get_region(country)

                rate_fixed  = None
                rate_mobile = None
                try:
                    page.select_option("select", value=val)
                    page.wait_for_timeout(800)
                    updated = page.content()
                    rm_vals = re.findall(r'RM\s*(\d+\.?\d*)', updated)
                    nums = [float(v) for v in rm_vals if 0.1 <= float(v) <= 50]
                    if nums:
                        uniq = list(dict.fromkeys(nums))
                        rate_fixed  = uniq[0]
                        rate_mobile = uniq[1] if len(uniq) > 1 else uniq[0]
                except Exception as e:
                    print(f"  [WARN] {country}: {e}")

                for plan_type in ("prepaid", "postpaid"):
                    rows.append({
                        "brand": "Unifi Mobile",
                        "country": country,
                        "region": region,
                        "plan_type": plan_type,
                        "rate_per_min_myr": rate_mobile,
                        "rate_fixed_per_min_myr": rate_fixed,
                        "rate_per_sms_myr": None,
                        "country_code": cc,
                        "access_code": "",
                        "plan_specific": False,
                        "notes": "",
                        "source_url": working_url,
                        "scraped_at": SCRAPED_AT,
                    })
                time.sleep(0.3)

        browser.close()

    print(f"  Total rows: {len(rows)}")
    return rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    print("=" * 50)
    print("IDD Scraper â€” remaining 5 brands")
    print("=" * 50)

    # Tune Talk
    tt_rows = scrape_tunetalk()
    if tt_rows:
        write_csv(SOURCE / "tunetalk_idd.csv", tt_rows)
    else:
        print("  [SKIP] No Tune Talk rows")

    # redONE
    ro_rows = scrape_redone()
    if ro_rows:
        write_csv(BASE / "redone_idd.csv", ro_rows)
    else:
        print("  [SKIP] No redONE rows")

    # U Mobile
    um_rows = scrape_umobile()
    if um_rows:
        write_csv(SOURCE / "umobile_idd.csv", um_rows)
    else:
        print("  [SKIP] No U Mobile rows")

    # CelcomDigi
    cd_rows = scrape_celcomdigi()
    if cd_rows:
        write_csv(BASE / "celcomdigi_idd.csv", cd_rows)
    else:
        print("  [SKIP] No CelcomDigi rows (IDD page not found)")

    # Unifi Mobile
    uni_rows = scrape_unifi()
    if uni_rows:
        write_csv(BASE / "unifi_idd.csv", uni_rows)
    else:
        print("  [SKIP] No Unifi rows")

    # Summary
    print("\n--- Summary ---")
    for brand, rows, fname in [
        ("Tune Talk",   tt_rows,  "tunetalk_idd.csv"),
        ("redONE",      ro_rows,  "redone_idd.csv"),
        ("U Mobile",    um_rows,  "umobile_idd.csv"),
        ("CelcomDigi",  cd_rows,  "celcomdigi_idd.csv"),
        ("Unifi Mobile",uni_rows, "unifi_idd.csv"),
    ]:
        status = f"{len(rows)} rows -> {fname}" if rows else "SKIPPED (0 rows)"
        print(f"  {brand:15s}: {status}")


if __name__ == "__main__":
    main()

