import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
import os
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
import re

# --- Configuration ---
USER_DATA_DIR = "./playwright_user_data"
INBOX_URL = "https://substack.com/inbox"
BASE_URL_FOR_JOINING = "https://substack.com"

ASSUME_LOGGED_IN = True

ENABLE_DATE_FILTER_CONFIG = True
DATE_FILTER_QUERY_CONFIG = "LAST 7 DAYS" # Example: Last 7 days
# DATE_FILTER_QUERY_CONFIG = "05-20 TO 05-25"
# DATE_FILTER_QUERY_CONFIG = None


if not ASSUME_LOGGED_IN and not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)
    print(f"Created user data directory: {USER_DATA_DIR}")

def parse_date_string_flexible(date_str, reference_year):
    formats_to_try = [
        "%Y-%m-%d", "%m-%d", "%b %d", "%B %d", "%b %d, %Y", "%B %d, %Y",
    ]
    for fmt in formats_to_try:
        try:
            dt_obj = datetime.strptime(date_str, fmt)
            if "%Y" not in fmt:
                dt_obj = dt_obj.replace(year=reference_year)
            return dt_obj.date()
        except ValueError:
            continue
    return None

async def scrape_substack_inbox_playwright_extract_v5(): # Renamed
    articles_data = []
    effective_enable_date_filter = ENABLE_DATE_FILTER_CONFIG

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True, # Set to True for background, False for debugging
            slow_mo=20 # Can be reduced if stable
        )
        page = await context.new_page()

        print(f"Navigating to Substack inbox: {INBOX_URL}")
        try:
            await page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            print(f"Timeout initially navigating to {INBOX_URL}.")
        print(f"Current URL: {page.url}")

        if not ASSUME_LOGGED_IN:
            print("-" * 50)
            print("ASSUME_LOGGED_IN is False. Please MANUALLY LOG IN and NAVIGATE to your inbox.")
            input(f"Once logged in AND on {INBOX_URL}, press Enter here to continue...")
            print("-" * 50)
        else:
            print("ASSUME_LOGGED_IN is True. Skipping manual login prompt.")
            if INBOX_URL not in page.url:
                print(f"Not on inbox. Navigating to {INBOX_URL}...")
                try:
                    await page.goto(INBOX_URL, wait_until="networkidle", timeout=30000)
                except PlaywrightTimeoutError:
                    print(f"Timeout navigating to inbox again.")
            print(f"Successfully on inbox page: {page.url}")
        
        await asyncio.sleep(0.5) # Shorter pause

        print("Attempting to set sort filter to 'Recent'...")
        try:
            sort_dropdown_selector = "select.sort-lAhhIt"
            sort_dropdown = page.locator(sort_dropdown_selector)
            if await sort_dropdown.is_visible(timeout=10000):
                current_value = await sort_dropdown.evaluate("element => element.value")
                if current_value != "recent":
                    print("Found sort dropdown. Selecting 'Recent'...")
                    await sort_dropdown.select_option(value="recent")
                    print("Selected 'recent' option.")
                    article_container_selector = "div.reader2-post-container" # Main article container
                    print(f"Waiting for content to update (waiting for: '{article_container_selector}')...")
                    await page.wait_for_selector(article_container_selector, state="visible", timeout=30000)
                    print("'Recent' articles list seems loaded.")
                else:
                    print("Sort filter already set to 'Recent'.")
            else:
                print(f"Could not find/see dropdown: '{sort_dropdown_selector}'.")
        except Exception as e:
            print(f"Error with 'Recent' sort filter: {e}")
        
        await asyncio.sleep(1) # Shorter pause


        print("Extracting articles...")
        article_item_selector = "div.reader2-post-container" # Main selector for each article card
        article_elements = page.locator(article_item_selector)
        count = await article_elements.count()
        print(f"Found {count} potential article elements with: '{article_item_selector}'")

        today_date = datetime.now().date()
        filter_start_date, filter_end_date = None, None

        if effective_enable_date_filter and DATE_FILTER_QUERY_CONFIG:
            # ... (Date Filter Query Parsing - same as v4) ...
            query = DATE_FILTER_QUERY_CONFIG.strip().upper()
            print(f"Applying date filter query: {query}")
            last_n_days_match = re.match(r"LAST (\d+) DAYS", query)
            between_match = re.match(r"(.+?) TO (.+)", query)
            if last_n_days_match:
                days = int(last_n_days_match.group(1))
                filter_start_date = today_date - timedelta(days=days -1)
                filter_end_date = today_date
                print(f"Filtering for last {days} days: {filter_start_date.isoformat()} to {filter_end_date.isoformat()}")
            elif between_match:
                start_str, end_str = between_match.group(1).strip(), between_match.group(2).strip()
                filter_start_date = parse_date_string_flexible(start_str, today_date.year)
                filter_end_date = parse_date_string_flexible(end_str, today_date.year)
                if not (filter_start_date and filter_end_date and filter_start_date <= filter_end_date):
                    print(f"Warning: Invalid range: '{start_str}' TO '{end_str}'. Disabling date filter.")
                    effective_enable_date_filter = False
                else:
                    print(f"Filtering BETWEEN {filter_start_date.isoformat()} AND {filter_end_date.isoformat()}")
            else: 
                filter_start_date = parse_date_string_flexible(query, today_date.year)
                filter_end_date = filter_start_date
                if not filter_start_date:
                    print(f"Warning: Could not parse single date query: '{query}'. Disabling date filter.")
                    effective_enable_date_filter = False
                else:
                    print(f"Filtering for single date: {filter_start_date.isoformat()}")
        else:
            print("Date filtering is disabled or no query provided.")
            effective_enable_date_filter = False


        for i in range(count):
            article_element = article_elements.nth(i)
            
            # Locators within each article_element
            link_locator = article_element.locator("a.linkRowA-pQXF7n")
            if not await link_locator.count(): # Fallback
                link_locator = article_element.locator("a[href*='/p/']").first
            
            title_locator = article_element.locator("div.reader2-post-title")
            date_locator = article_element.locator("div.inbox-item-timestamp")
            
            # --- NEW: Substack Name Locator ---
            # Based on HTML: <div class="pub-name"><a>SUBSTACK NAME</a></div>
            # It's a child of div.reader2-post-head, which is a child of the main link_locator context usually
            # Or a direct child of article_element if link_locator is not the main wrapper for everything.
            # Let's assume it's within the broader article_element context for simplicity here.
            substack_name_locator = article_element.locator("div.pub-name a") # Targets the <a> inside div.pub-name
            # Alternative, if div.pub-name itself has the text directly (less likely from your HTML):
            # substack_name_locator = article_element.locator("div.pub-name")

            article_date_for_filtering = None

            try:
                href_val = await link_locator.get_attribute("href")
                title_text_val = await title_locator.text_content()
                
                article_date_str_on_page = None
                if await date_locator.count() > 0:
                    article_date_str_on_page = (await date_locator.first.text_content()).strip()

                substack_name_val = "N/A" # Default if not found
                if await substack_name_locator.count() > 0:
                    substack_name_val = (await substack_name_locator.first.text_content()).strip()


                if href_val and title_text_val:
                    href_val = href_val.strip()
                    title_text_val = title_text_val.strip()

                    if '/p/' in href_val:
                        # --- Article Date Parsing (from webpage) ---
                        if article_date_str_on_page:
                            # ... (Date parsing logic for article_date_for_filtering - same as v4) ...
                            if ":" in article_date_str_on_page and \
                               ("AM" in article_date_str_on_page.upper() or "PM" in article_date_str_on_page.upper()):
                                article_date_for_filtering = today_date
                            elif "yesterday" in article_date_str_on_page.lower():
                                article_date_for_filtering = today_date - timedelta(days=1)
                            else:
                                parsed_web_date = parse_date_string_flexible(article_date_str_on_page, today_date.year)
                                if parsed_web_date:
                                    if parsed_web_date.month > today_date.month and \
                                       (parsed_web_date.month - today_date.month > 6) and \
                                       parsed_web_date.year == today_date.year :
                                        article_date_for_filtering = parsed_web_date.replace(year=today_date.year - 1)
                                    else:
                                        article_date_for_filtering = parsed_web_date
                                else:
                                    print(f"Could not parse web date: '{article_date_str_on_page}' for '{title_text_val}'")

                        # --- Apply Date Filter ---
                        if effective_enable_date_filter:
                            # ... (Date filtering logic - same as v4) ...
                            if not article_date_for_filtering:
                                continue 
                            if filter_start_date and filter_end_date: 
                                if not (filter_start_date <= article_date_for_filtering <= filter_end_date):
                                    continue
                            elif not filter_start_date and not filter_end_date and DATE_FILTER_QUERY_CONFIG:
                                print(f"Skipping '{title_text_val}' as date query '{DATE_FILTER_QUERY_CONFIG}' was invalid.")
                                continue

                        full_url = urljoin(BASE_URL_FOR_JOINING, href_val)
                        articles_data.append({
                            "substack_name": substack_name_val, # Added
                            "title": title_text_val, 
                            "url": full_url, 
                            "date_str_on_page": article_date_str_on_page, 
                            "parsed_article_date": article_date_for_filtering.isoformat() if article_date_for_filtering else "N/A"
                        })
            except PlaywrightError as e:
                # print(f"Error extracting from article element {i}: {e}") # Verbose error
                # print(f"HTML for element {i}: {await article_element.inner_html()}")
                continue # Skip this article if essential parts are missing
        
        print("Finished extracting.")
        # ... (logging for extraction results) ...
        if not articles_data and count > 0:
             print("Elements found, but no articles passed filters or had valid data. Check filters and selectors.")
        elif not articles_data and count == 0:
            print("No article elements found. Check `article_item_selector`.")


        await context.close()
        return articles_data

if __name__ == "__main__":
    extracted_data = asyncio.run(scrape_substack_inbox_playwright_extract_v5())

    # 1) Print to terminal as before
    if extracted_data:
        print(f"\n--- Extracted {len(extracted_data)} Articles (after filters) ---")
        for article in extracted_data:
            print(f"Substack: {article['substack_name']}")
            print(f"Title: {article['title']}")
            print(f"URL: {article['url']}")
            print(f"Date on Page: {article['date_str_on_page']} (Parsed as: {article['parsed_article_date']})")
            print("-" * 20)
    else:
        print("\nNo data was extracted or passed filters.")

    # 2) ALSO dump to a CSV file named UR_<YYYYMMDD-HHMM>.csv
    import csv
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"UR_{ts}.csv"
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Header row
            writer.writerow([
                "substack_name",
                "title",
                "url",
                "date_on_page",
                "parsed_date"
            ])
            # Data rows
            for a in extracted_data:
                writer.writerow([
                    a["substack_name"],
                    a["title"],
                    a["url"],
                    a["date_str_on_page"],
                    a["parsed_article_date"]
                ])
        print(f"\nSaved extracted articles to file: {filename}")
    except Exception as e:
        print(f"\nFailed to write output file {filename}: {e}")

