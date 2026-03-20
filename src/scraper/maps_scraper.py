"""Main scraping logic: search, scroll, extract from Google Maps."""

import urllib.parse
from datetime import datetime, timezone

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.config.selectors import FeedSelectors
from src.scraper.browser import random_delay, random_mouse_move
from src.scraper.captcha import check_for_captcha, handle_captcha
from src.scraper.parser import (
    card_is_sponsored,
    get_card_website_status,
    extract_from_card,
    extract_detail_panel,
)
from src.storage.database import (
    Session,
    ScrapeJob,
    upsert_business,
    mark_job_started,
    mark_job_done,
    mark_job_error,
)


async def scroll_sidebar(page: Page):
    """Scroll the results sidebar to load all results."""
    feed = page.locator(FeedSelectors.FEED)
    if await feed.count() == 0:
        return

    prev_count = 0
    stale_rounds = 0
    while stale_rounds < 3:
        await feed.evaluate("el => el.scrollBy(0, 800)")
        await random_delay(page, 1500, 2500)

        cards = page.locator(FeedSelectors.CARDS)
        count = await cards.count()

        if count == prev_count:
            stale_rounds += 1
        else:
            stale_rounds = 0
        prev_count = count

        end_marker = page.locator('span:has-text("You\'ve reached the end")')
        if await end_marker.count() > 0:
            break


async def search_maps(page: Page, term: str, city: str) -> str:
    """Navigate to Google Maps and perform a search. Returns the search URL."""
    query = f"{term} near {city}, Malaysia"
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"

    await page.goto(url, wait_until="domcontentloaded")
    await random_delay(page, 3000, 5000)

    if await check_for_captcha(page):
        await handle_captcha(page)

    return url


async def _return_to_results(page: Page, search_url: str):
    """Return to the results feed after viewing a detail panel.

    Strategy: press Escape to close detail panel, then verify feed is visible.
    If that fails, re-navigate to the search URL.
    """
    # Try Escape first — closes the detail panel overlay
    try:
        await page.keyboard.press("Escape")
        await random_delay(page, 800, 1500)

        # Check if feed is back
        feed = page.locator(FeedSelectors.FEED)
        if await feed.count() > 0:
            # Verify cards are still there
            cards = page.locator(FeedSelectors.CARDS)
            if await cards.count() > 0:
                return
    except Exception:
        pass

    # Escape didn't work — try go_back
    try:
        await page.go_back()
        await random_delay(page, 1500, 2500)
        feed = page.locator(FeedSelectors.FEED)
        if await feed.count() > 0:
            return
    except Exception:
        pass

    # Last resort — re-navigate to search URL
    await page.goto(search_url, wait_until="domcontentloaded")
    await random_delay(page, 3000, 5000)


async def scrape_search(
    page: Page,
    session: Session,
    job: ScrapeJob,
    term: str,
    state: str,
    city: str,
    seen_place_ids: set[str],
    session_count: int,
    session_limit: int,
) -> tuple[int, int]:
    """
    Scrape one search query. Returns (new_leads_found, updated_session_count).

    Speed strategy:
      1. Read website href from card — if real website, SKIP (no click)
      2. Extract name/rating/reviews/category/address/coords from card HTML
      3. Only click in for leads (no website or social-only) to get phone + confirm
    """
    mark_job_started(session, job)
    leads_found = 0

    try:
        search_url = await search_maps(page, term, city)

        try:
            await page.wait_for_selector(FeedSelectors.FEED, timeout=10000)
        except Exception:
            mark_job_done(session, job, 0)
            return 0, session_count

        await scroll_sidebar(page)

        # Collect all card data FIRST before clicking into any
        # This avoids stale locator issues after navigation
        cards = page.locator(FeedSelectors.CARDS)
        total_cards = await cards.count()

        card_infos: list[dict] = []
        for i in range(total_cards):
            card = cards.nth(i)

            if await card_is_sponsored(card):
                continue

            website_status, website_url = await get_card_website_status(card)
            if website_status == "active":
                continue

            card_data = await extract_from_card(card, state, city, term)
            if card_data is None:
                continue

            card_data["website"] = website_url
            card_data["website_status"] = website_status

            place_id = card_data.get("place_id", "")
            if place_id in seen_place_ids:
                continue

            card_infos.append(card_data)

        # Now click into each lead one by one
        for card_data in card_infos:
            if session_limit > 0 and session_count >= session_limit:
                print(f"  Session limit ({session_limit}) reached. Stopping.")
                break

            place_id = card_data["place_id"]
            name = card_data.get("name", "?")
            maps_url = card_data.get("google_maps_url", "")

            if not maps_url:
                continue

            if await check_for_captcha(page):
                await handle_captcha(page)

            await random_mouse_move(page)
            await random_delay(page)

            # Navigate directly to the listing URL (more reliable than clicking)
            try:
                await page.goto(maps_url, wait_until="domcontentloaded")
                await random_delay(page, 2000, 4000)
            except Exception as e:
                print(f"  Skip {name}: navigation failed ({e})")
                continue

            # Extract details from the detail panel
            detail = await extract_detail_panel(page, card_data)
            if detail is None:
                continue

            website_status = detail.get("website_status", card_data["website_status"])

            seen_place_ids.add(place_id)
            detail["scraped_at"] = datetime.now(timezone.utc)

            if website_status in ("none", "social_only"):
                detail["website_status"] = website_status
                upsert_business(session, detail)
                leads_found += 1
                session_count += 1
                print(f"  [{session_count}] {name} | "
                      f"{detail.get('phone', 'no phone')} | "
                      f"{website_status}")

        mark_job_done(session, job, leads_found)

    except Exception as e:
        mark_job_error(session, job, str(e))
        print(f"  Error: {e}")

    return leads_found, session_count
