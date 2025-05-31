import os
import sys
import asyncio
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# Simple file paths (in current directory)
USER_DATA_DIR = "playwright_user_data"
SESSION_FLAG = "logged_in.flag"
DATE_FILE = "date.txt"
DATA_DIR = "data"

os.makedirs(USER_DATA_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def is_logged_in():
    return os.path.exists(SESSION_FLAG)

def set_logged_in(flag: bool):
    if flag:
        with open(SESSION_FLAG, "w", encoding="utf-8") as f:
            f.write("true")
    else:
        try:
            os.remove(SESSION_FLAG)
        except FileNotFoundError:
            pass

def load_date_filter():
    if os.path.exists(DATE_FILE):
        return open(DATE_FILE, encoding="utf-8").read().strip() or None
    return None

def save_date_filter(s: str):
    with open(DATE_FILE, "w", encoding="utf-8") as f:
        f.write(s.strip())

# ------------------------------------------------------------
# Login / Logout Flows
# ------------------------------------------------------------
def login_flow():
    clear_screen()
    print("== LOGIN / RE-AUTHENTICATE ==")
    input("A Chromium window will open. Log in, then press Enter…")
    async def _do():
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                USER_DATA_DIR, headless=False, slow_mo=100
            )
            page = await ctx.new_page()
            await page.goto("https://substack.com/inbox")
            input("Once inbox is visible, press Enter…")
            await ctx.close()
    asyncio.run(_do())
    set_logged_in(True)
    print("✅ Login saved.")
    input("Press Enter to continue…")

def logout_flow():
    clear_screen()
    set_logged_in(False)
    print("✅ Logged out.")
    input("Press Enter to continue…")

# ------------------------------------------------------------
# Date Filter Flow
# ------------------------------------------------------------
def set_date_flow():
    clear_screen()
    print("== SET DATE FILTER ==")
    print("Allowed: 'LAST N DAYS', 'MM-DD', 'MM-DD TO MM-DD'")
    current = load_date_filter() or "None"
    s = input(f"Enter date filter (blank to clear) [{current}]: ").strip()
    if not s:
        save_date_filter("")
        print("Filter cleared.")
    else:
        up = s.upper()
        valid = bool(
            re.match(r"LAST \d+ DAYS", up)
            or re.match(r"\d{1,2}-\d{1,2}$", up)
            or re.match(r"\d{1,2}-\d{1,2}\s+TO\s+\d{1,2}-\d{1,2}$", up)
        )
        if valid:
            save_date_filter(s)
            print(f"Filter set to '{s}'")
        else:
            print("Invalid format.")
    input("Press Enter to continue…")

# ------------------------------------------------------------
# Extraction Flow
# ------------------------------------------------------------
def extract_flow():
    clear_screen()
    print("== EXTRACTING ARTICLES ==")

    logged = is_logged_in()
    if not logged:
        print("Not logged in.")
        if input("Proceed anyway? (y/N): ").strip().lower() != 'y':
            return
    date_filter = load_date_filter()
    use_filter = bool(date_filter)
    if use_filter:
        print(f"Using date filter: {date_filter}")

    async def _scrape():
        today = datetime.now().date()
        year = today.year
        start = end = None
        if use_filter:
            q = date_filter.strip().upper()
            m = re.match(r"LAST (\d+) DAYS", q)
            if m:
                n = int(m.group(1))
                start, end = today - timedelta(days=n-1), today
            else:
                parts = re.match(r"(.+?) TO (.+)", q)
                if parts:
                    start = datetime.strptime(parts.group(1), "%m-%d").replace(year=year).date()
                    end   = datetime.strptime(parts.group(2), "%m-%d").replace(year=year).date()
                else:
                    d = datetime.strptime(q, "%m-%d").replace(year=year).date()
                    start = end = d
        articles = []
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                USER_DATA_DIR, headless=True, slow_mo=20
            )
            page = await ctx.new_page()
            await page.goto("https://substack.com/inbox", timeout=60000)
            try:
                await page.wait_for_selector("div.reader2-post-container", timeout=30000)
            except PlaywrightTimeoutError:
                await ctx.close()
                return []
            conts = page.locator("div.reader2-post-container")
            total = await conts.count()
            for i in range(total):
                el = conts.nth(i)
                href = await el.locator("a.linkRowA-pQXF7n").get_attribute("href") or ""
                title = (await el.locator("div.reader2-post-title").text_content() or "").strip()
                date_raw = (await el.locator("div.inbox-item-timestamp").text_content() or "").strip()
                name = (await el.locator("div.pub-name a").text_content() or "N/A").strip()
                if not href or not title:
                    continue
                # parse date
                if ":" in date_raw.lower():
                    art_date = today
                elif "yesterday" in date_raw.lower():
                    art_date = today - timedelta(days=1)
                else:
                    art_date = datetime.strptime(date_raw, "%b %d").replace(year=year).date()
                # filter
                if use_filter and art_date:
                    if not (start <= art_date <= end):
                        continue
                full_url = urljoin("https://substack.com", href)
                articles.append({
                    "date": art_date.isoformat(),
                    "name": name,
                    "title": title,
                    "url": full_url
                })
            await ctx.close()
        return articles

    data = asyncio.run(_scrape())
    if not data:
        print("No articles.")
        input("Press Enter…")
        return
    # Save to TXT
    fn = os.path.join(DATA_DIR, f"UR_{datetime.now().strftime('%Y%m%d-%H%M')}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        for a in data:
            f.write(f"{a['date']} | {a['name']} | {a['title']} | {a['url']}\n")
    print(f"Saved to {fn}")
    input("Press Enter…")

# ------------------------------------------------------------
# Main Menu
# ------------------------------------------------------------
def main():
    while True:
        clear_screen()
        logged = is_logged_in()
        df = load_date_filter() or "None"
        print("=== Substack Scraper ===")
        print(f"1. {'Logout' if logged else 'Login'}")
        print(f"2. Set Date Filter (Current: {df})")
        print("3. Extract Articles")
        print("4. Exit")
        choice = input("Choose [1-4]: ").strip()
        if choice == '1':
            logout_flow() if logged else login_flow()
        elif choice == '2':
            set_date_flow()
        elif choice == '3':
            extract_flow()
        elif choice == '4':
            break
        else:
            continue

if __name__ == '__main__':
    main()
