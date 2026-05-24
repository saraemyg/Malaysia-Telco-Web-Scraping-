"""Standalone runner: scrape U Mobile IDD rates only."""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from playwright.async_api import async_playwright
from scrape_idd_playwright import scrape_umobile, write_csv, BASE, SOURCE

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        rows = await scrape_umobile(browser)
        await browser.close()

    if rows:
        write_csv(SOURCE / "umobile_idd.csv", rows)
    else:
        print("[WARN] No rows produced for U Mobile")

asyncio.run(main())
