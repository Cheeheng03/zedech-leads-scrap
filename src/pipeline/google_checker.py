"""Google search cross-check for high-score leads."""

import urllib.parse

from playwright.async_api import Page
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.scraper.browser import random_delay, random_mouse_move
from src.scraper.captcha import check_for_captcha, handle_captcha
from src.storage.database import Business


SOCIAL_DOMAINS = {"facebook.com", "fb.com", "instagram.com", "maps.google.com", "google.com/maps"}


async def google_check_business(page: Page, biz: Business) -> bool:
    """
    Search Google for the business. Returns True if confirmed no real website.
    """
    query = f"{biz.name} {biz.city or biz.state}"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"

    await random_mouse_move(page)
    await page.goto(url, wait_until="domcontentloaded")
    await random_delay(page, 2000, 4000)

    if await check_for_captcha(page):
        await handle_captcha(page)

    # Get top 5 result links
    results = await page.locator("div#search a[href]").all()
    hrefs: list[str] = []
    for r in results[:5]:
        href = await r.get_attribute("href")
        if href:
            hrefs.append(href.lower())

    # If all top results are social/maps links, confirmed no website
    if not hrefs:
        return True

    for href in hrefs:
        is_social_or_maps = any(domain in href for domain in SOCIAL_DOMAINS)
        if not is_social_or_maps:
            return False  # Found a real website

    return True


async def run_google_checks(page: Page, session: Session):
    """Run Google cross-checks on high-score leads."""
    min_score = settings.min_score_for_google_check
    businesses = (
        session.query(Business)
        .filter(
            Business.score >= min_score,
            Business.google_checked == False,
            Business.website_status.in_(["none", "social_only"]),
        )
        .order_by(Business.score.desc())
        .all()
    )

    print(f"Google-checking {len(businesses)} high-score leads (score >= {min_score})...")

    for i, biz in enumerate(businesses):
        print(f"  [{i + 1}/{len(businesses)}] Checking: {biz.name}")

        confirmed = await google_check_business(page, biz)
        biz.google_checked = True
        biz.google_confirmed_no_site = confirmed
        session.commit()

        status = "CONFIRMED no site" if confirmed else "might have site"
        print(f"    -> {status}")

        await random_delay(page, 3000, 6000)

    print("Google checks complete.")
