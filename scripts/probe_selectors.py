"""
Probe script: open a Google Maps search, dump the actual DOM structure
of result cards so we can verify/fix selectors before scraping.

Run: python3 scripts/probe_selectors.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


PROBE_URL = "https://www.google.com/maps/search/workshop+near+Johor+Bahru,+Malaysia"


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        locale="en-MY",
        timezone_id="Asia/Kuala_Lumpur",
    )
    page = await context.new_page()

    print(f"Navigating to: {PROBE_URL}\n")
    await page.goto(PROBE_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # --- 1. Check if consent/cookie dialog blocks ---
    consent_selectors = [
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'form[action*="consent"] button',
    ]
    for sel in consent_selectors:
        btn = page.locator(sel).first
        if await btn.count() > 0:
            print(f"[CONSENT] Found consent button: {sel} — clicking it")
            await btn.click()
            await page.wait_for_timeout(3000)
            break
    else:
        print("[CONSENT] No consent dialog found (good)\n")

    # --- 2. Test feed selector ---
    print("=" * 60)
    print("TESTING SELECTORS")
    print("=" * 60)

    feed = page.locator('div[role="feed"]')
    feed_count = await feed.count()
    print(f'\n[FEED] div[role="feed"] -> found: {feed_count}')

    if feed_count == 0:
        print("[FEED] Trying alternative: div[role=\"main\"] .scrollable...")
        # Dump roles on page for debugging
        roles = await page.evaluate("""
            () => [...document.querySelectorAll('[role]')]
                .map(el => ({role: el.getAttribute('role'), tag: el.tagName, classes: el.className.slice(0, 60)}))
                .slice(0, 30)
        """)
        for r in roles:
            print(f"  role={r['role']} tag={r['tag']} class={r['classes']}")
        await _pause_and_cleanup(browser, pw)
        return

    # --- 3. Test card selectors ---
    direct_children = page.locator('div[role="feed"] > div')
    dc_count = await direct_children.count()
    print(f'[CARDS] div[role="feed"] > div -> count: {dc_count}')

    # Get first few cards and inspect structure
    print("\n--- First 3 card structures ---")
    for i in range(min(3, dc_count)):
        card = direct_children.nth(i)
        html = await card.evaluate("el => el.outerHTML.slice(0, 500)")
        inner = await card.inner_text()
        inner_short = inner[:200].replace("\n", " | ")
        print(f"\n[Card {i}]")
        print(f"  HTML prefix: {html[:300]}")
        print(f"  Text: {inner_short}")

        # Test key sub-selectors on this card
        tests = {
            "CARD_LINK a[href*='maps/place']": "a[href*='maps/place']",
            "WEBSITE_BTN a[data-value='Website']": 'a[data-value="Website"]',
            "WEBSITE_BTN_ALT a:has-text('Website')": 'a:has-text("Website")',
            "SPONSORED span:has-text('Sponsored')": 'span:has-text("Sponsored")',
            "SPONSORED_ALT span:has-text('Ad')": 'span:has-text("Ad")',
        }
        for label, sel in tests.items():
            count = await card.locator(sel).count()
            status = "FOUND" if count > 0 else "not found"
            print(f"  {label} -> {status} ({count})")

    # --- 4. Click first non-empty card and test detail selectors ---
    print("\n--- Clicking into first result for detail panel ---")
    clicked = False
    for i in range(dc_count):
        card = direct_children.nth(i)
        link = card.locator("a[href*='maps/place']").first
        if await link.count() > 0:
            await link.click()
            await page.wait_for_timeout(4000)
            clicked = True
            break

    if not clicked:
        print("[DETAIL] Could not find a card to click into")
        await _pause_and_cleanup(browser, pw)
        return

    print(f"[DETAIL] Current URL: {page.url}\n")

    detail_tests = {
        "NAME h1": "h1",
        "ADDRESS button[data-item-id='address']": 'button[data-item-id="address"]',
        "PHONE button[data-item-id^='phone:tel:']": 'button[data-item-id^="phone:tel:"]',
        "WEBSITE a[data-item-id='authority']": 'a[data-item-id="authority"]',
        "CATEGORY button[jsaction*='category']": 'button[jsaction*="category"]',
        "RATING span[role='img']": 'span[role="img"]',
        "REVIEWS span[aria-label*='review']": 'span[aria-label*="review"]',
        "PHOTO_COUNT button[jsaction*='heroHeaderImage']": 'button[jsaction*="heroHeaderImage"]',
        "BACK_BTN button[aria-label='Back']": 'button[aria-label="Back"]',
    }

    for label, sel in detail_tests.items():
        loc = page.locator(sel).first
        count = await loc.count()
        status = "FOUND" if count > 0 else "NOT FOUND"
        value = ""
        if count > 0:
            try:
                value = (await loc.inner_text())[:80]
            except Exception:
                try:
                    value = await loc.get_attribute("aria-label") or ""
                except Exception:
                    value = "(could not read)"
        print(f"  [{status}] {label}")
        if value:
            print(f"           -> {value}")

    # Check place ID in URL
    import re
    url = page.url
    place_match = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    print(f"\n[URL] Place ID regex match: {'YES -> ' + place_match.group(1) if place_match else 'NO'}")

    coord_match = re.search(r"@(-?[\d.]+),(-?[\d.]+)", url)
    print(f"[URL] Coordinates regex match: {'YES -> ' + coord_match.group(0) if coord_match else 'NO'}")

    # --- 5. Dump all data-item-id attributes on detail page ---
    print("\n--- All data-item-id attributes on detail page ---")
    data_items = await page.evaluate("""
        () => [...document.querySelectorAll('[data-item-id]')]
            .map(el => ({
                id: el.getAttribute('data-item-id'),
                tag: el.tagName,
                text: el.textContent.slice(0, 60)
            }))
    """)
    for item in data_items:
        print(f"  data-item-id=\"{item['id']}\" <{item['tag']}> {item['text']}")

    # --- 6. Dump all data-value attributes on detail page ---
    print("\n--- All data-value attributes on detail page ---")
    data_values = await page.evaluate("""
        () => [...document.querySelectorAll('[data-value]')]
            .map(el => ({
                val: el.getAttribute('data-value'),
                tag: el.tagName,
                text: el.textContent.slice(0, 60)
            }))
    """)
    for item in data_values:
        print(f"  data-value=\"{item['val']}\" <{item['tag']}> {item['text']}")

    print("\n" + "=" * 60)
    print("PROBE COMPLETE — browser will stay open for manual inspection.")
    print("Press Enter to close...")
    input()

    await browser.close()
    await pw.stop()


async def _pause_and_cleanup(browser, pw):
    print("\nPress Enter to close browser...")
    input()
    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
