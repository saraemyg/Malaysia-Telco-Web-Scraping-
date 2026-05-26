"""
gmaps_scraper.py
════════════════════════════════════════════════════════════════════
Scrape Google Maps search results → 2-column CSV (Name, Category).

USAGE
-----
    python gmaps_scraper.py
    python gmaps_scraper.py --query "sdn. bhd" --max 200
    python gmaps_scraper.py -q "sdn bhd selangor" -m 150

ANTI-DETECTION STRATEGY (why it works)
--------------------------------------
1.  undetected-chromedriver removes all webdriver / CDP fingerprints.
2.  Real Chrome window, real viewport size — Google's bot scoring
    drops headless sessions almost immediately.
3.  Scrolls the INTERNAL feed panel (div[role="feed"]) in small,
    variable-sized increments with random pauses — never a single
    jump to the bottom (a classic bot tell).
4.  Random "reading" pauses (4–8 s) sprinkled in every ~6 scrolls.
5.  Mouse jitter between scrolls so the cursor isn't frozen.
6.  Selectors target stable attributes (role, aria-label) first,
    Google-generated class names only as a fallback.
7.  One query per session — open, scrape, close.  Don't loop several
    searches in the same driver instance.

LIMITS YOU CAN'T BEAT
---------------------
Google hard-caps Maps search at ~120-200 results per query.  If you
need more, run several narrower sub-queries (by state, by city) and
dedupe.

REQUIREMENTS
------------
    pip install undetected-chromedriver selenium
    (already in your Shopee project's requirements.txt)
"""

import argparse
import csv
import os
import random
import re
import time
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Config ──────────────────────────────────────────────────────────────────
CHROME_MAJOR  = 148          # Match your installed Chrome version
DEFAULT_QUERY = "sdn. bhd"
DEFAULT_MAX   = 200
OUTPUT_DIR    = "gmap_data"


# ── Human-like helpers ──────────────────────────────────────────────────────

def human_pause(min_s: float = 2.0, max_s: float = 5.0):
    """Sleep a randomised amount — mimics reading time."""
    time.sleep(random.uniform(min_s, max_s))


def jitter_mouse(driver):
    """Small random mouse movement so the cursor isn't frozen."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        x = random.randint(-150, 150)
        y = random.randint(-150, 150)
        (ActionChains(driver)
            .move_to_element_with_offset(body, x, y)
            .pause(random.uniform(0.2, 0.7))
            .perform())
    except Exception:
        pass


# ── Browser launch ──────────────────────────────────────────────────────────

def make_driver(chrome_major: int):
    """Launch undetected Chrome with a realistic profile."""
    opts = uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=en-MY")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # Headless gets flagged within seconds on Maps — don't.
    return uc.Chrome(options=opts, use_subprocess=True, version_main=chrome_major)


def dismiss_consent(driver):
    """Click cookie / consent buttons that sometimes pop up."""
    selectors = [
        'button[aria-label*="Accept all" i]',
        'button[aria-label*="Accept" i]',
        'button[aria-label*="I agree" i]',
        'form[action*="consent"] button',
    ]
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            human_pause(1, 2)
            return
        except Exception:
            continue


# ── Scrolling the results feed ──────────────────────────────────────────────

def get_feed_panel(driver):
    """The scrollable left-side results panel."""
    return driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')


def _card_count(driver):
    """Return (count, feed_element) using the best available selector."""
    try:
        feed = get_feed_panel(driver)
        cards = feed.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
        if not cards:
            cards = feed.find_elements(By.CSS_SELECTOR, 'div[jsaction*="mouseover"]')
        return len(cards), feed
    except Exception:
        return 0, None


def scroll_feed(driver, target_count: int, hard_round_cap: int = 300):
    """
    Scroll the feed to the bottom on each round and poll until new cards
    appear.  Never gives up on a timeout — keeps going until target_count
    is reached, the end-of-list sentinel appears, or hard_round_cap is hit.
    """
    POLL_INTERVAL = 0.8   # check for new cards every 0.8 s
    LOAD_TIMEOUT  = 12.0  # wait up to 12 s per scroll for Maps to respond

    rounds = 0

    while rounds < hard_round_cap:
        count_before, feed = _card_count(driver)
        print(f"  scroll #{rounds:>3}: {count_before} cards loaded", end="\r")

        if count_before >= target_count:
            print()
            return

        # Scroll to the absolute bottom of the feed — most reliable way to
        # trigger Maps' lazy-load for the next batch of cards.
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight;", feed
        )

        # Brief pause so the scroll animation settles before polling
        time.sleep(random.uniform(1.0, 2.0))

        # Poll until new cards appear or the timeout expires.
        # On timeout we do NOT give up — we just scroll again next round.
        deadline = time.time() + LOAD_TIMEOUT
        while time.time() < deadline:
            new_count, _ = _card_count(driver)
            if new_count > count_before:
                break
            time.sleep(POLL_INTERVAL)

        # Check the end-of-list sentinel regardless of whether we got new cards
        try:
            _, feed = _card_count(driver)
            if feed and "you've reached the end of the list" in feed.text.lower():
                final, _ = _card_count(driver)
                print(f"\n  → reached end of list ({final} cards total)")
                return
        except Exception:
            pass

        # Occasional human-like behaviour
        if random.random() < 0.25:
            jitter_mouse(driver)
        if random.random() < 0.10:
            time.sleep(random.uniform(3, 5))

        rounds += 1

    print()


# ── Extraction (executed inside the page) ───────────────────────────────────

EXTRACT_JS = r"""
function clean(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

const feed = document.querySelector('div[role="feed"]');
if (!feed) return [];

// Try current class, then fall back to a jsaction-based selector.
let cards = feed.querySelectorAll('div.Nv2PK');
if (!cards.length) cards = feed.querySelectorAll('div[jsaction*="mouseover"]');

const out = [];
for (const card of cards) {
  try {
    // Name: stable across recent Maps versions.
    const nameEl =
      card.querySelector('.qBF1Pd') ||
      card.querySelector('.fontHeadlineSmall') ||
      card.querySelector('div[role="heading"]');
    const name = nameEl ? clean(nameEl.textContent) : '';
    if (!name) continue;

    // Scan every .W4Efsd metadata row and pick the first part that looks
    // like a business category (e.g. "Software company", "Real estate developer").
    // Parts are split by "·"; we take the first part that:
    //   - starts with a letter (not a digit/icon)
    //   - has no long digit runs (street numbers, phone numbers)
    //   - isn't an hours string (Open/Closed/am/pm)
    //   - is short enough not to be an address
    let category = '';
    const rows = card.querySelectorAll('.W4Efsd');
    outer:
    for (const row of rows) {
      const txt = clean(row.textContent);
      if (!txt.includes('·')) continue;
      const parts = txt.split('·').map(p => p.trim()).filter(Boolean);
      for (const cand of parts) {
        if (cand.length < 3)                            continue;  // too short
        if (!/^[A-Za-z]/.test(cand))                   continue;  // must start with letter
        if (/\d{3,}/.test(cand))                        continue;  // street/phone number
        if (/(closed|open|\d\s*am|\d\s*pm)/i.test(cand)) continue; // hours
        if (cand.length > 55)                           continue;  // too long = address
        category = cand;
        break outer;
      }
    }

    out.push({ name: name, category: category });
  } catch (e) { /* skip card */ }
}
return out;
"""


def extract(driver):
    """Pull (name, category) pairs from the loaded feed and dedupe by name."""
    rows = driver.execute_script(EXTRACT_JS) or []
    seen = set()
    cleaned = []
    for r in rows:
        n = (r.get("name") or "").strip()
        c = (r.get("category") or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        cleaned.append((n, c))
    return cleaned


# ── Main pipeline ───────────────────────────────────────────────────────────

def run(query: str, max_results: int, chrome_major: int) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe  = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"gmaps_{safe}_{stamp}.csv")

    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/?hl=en"

    print(f"[gmaps] Launching Chrome v{chrome_major}...")
    driver = make_driver(chrome_major)

    try:
        print(f"[gmaps] Opening {url}")
        driver.get(url)
        human_pause(3, 6)

        dismiss_consent(driver)

        # Wait for the feed to render
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
        )
        human_pause(2, 4)

        print(f"[gmaps] Scrolling to load up to {max_results} results...")
        print("  (press Ctrl+C at any time to stop and save what's loaded so far)")
        try:
            scroll_feed(driver, max_results)
        except KeyboardInterrupt:
            print("\n[gmaps] Interrupted — saving what was scraped so far...")

        print("[gmaps] Extracting...")
        rows = extract(driver)
        print(f"[gmaps] {len(rows)} unique businesses extracted")

        # Save CSV (utf-8-sig so Excel displays Malay characters correctly)
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Name", "Category"])
            w.writerows(rows[:max_results])

        size_kb = round(os.path.getsize(out_path) / 1024, 1)
        print(f"\n[gmaps] ✅  Saved → {out_path}  ({len(rows)} rows, {size_kb} KB)")
        return out_path

    finally:
        input("\nPress Enter to close the browser...")
        try:
            driver.quit()
        except Exception:
            pass


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Google Maps search → 2-column CSV (Name, Category)"
    )
    p.add_argument("--query", "-q", default=DEFAULT_QUERY,
                   help=f"Search query (default: '{DEFAULT_QUERY}')")
    p.add_argument("--max",   "-m", type=int, default=DEFAULT_MAX,
                   help="Max results to extract (Google caps ~200/query)")
    p.add_argument("--chrome-version", type=int, default=CHROME_MAJOR,
                   help=f"Installed Chrome major version (default: {CHROME_MAJOR})")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.query, args.max, args.chrome_version)
