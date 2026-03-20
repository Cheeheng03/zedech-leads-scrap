"""CAPTCHA detection and human-in-the-loop solving."""

import subprocess

from playwright.async_api import Page

from src.config.selectors import CaptchaSelectors
from src.scraper.browser import random_delay


async def check_for_captcha(page: Page) -> bool:
    """Check if CAPTCHA or block page appeared."""
    indicators = [
        page.locator(CaptchaSelectors.RECAPTCHA_IFRAME),
        page.locator(CaptchaSelectors.CAPTCHA_FORM),
        page.locator(CaptchaSelectors.UNUSUAL_TRAFFIC),
        page.locator(CaptchaSelectors.NOT_A_ROBOT),
        page.locator(CaptchaSelectors.AUTOMATED_QUERIES),
    ]
    for indicator in indicators:
        if await indicator.count() > 0:
            return True
    return False


async def handle_captcha(page: Page):
    """Pause scraping and prompt human to solve CAPTCHA."""
    print("\n" + "=" * 50)
    print("CAPTCHA DETECTED - HUMAN INTERVENTION NEEDED")
    print("=" * 50)
    print("Please solve the CAPTCHA in the browser window.")
    print("Press ENTER here when done...")

    # macOS notification
    try:
        subprocess.run(
            [
                "osascript", "-e",
                'display notification "CAPTCHA detected - solve it in the browser" '
                'with title "Map Scraper"',
            ],
            check=False,
        )
    except Exception:
        pass

    # Terminal bell
    print("\a")

    input()

    # Verify CAPTCHA is gone
    if await check_for_captcha(page):
        print("CAPTCHA still present. Please solve it and press Enter again.")
        input()

    # Extra delay after CAPTCHA to avoid re-trigger
    await random_delay(page, 10000, 20000)
    print("Resuming scraping...")
