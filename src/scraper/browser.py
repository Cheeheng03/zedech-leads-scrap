"""Playwright browser setup with anti-detection."""

import random

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


async def launch_browser(headless: bool = False) -> tuple:
    """Launch browser with anti-detection settings. Returns (playwright, browser, context, page)."""
    pw = await async_playwright().start()

    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        locale="en-MY",
        timezone_id="Asia/Kuala_Lumpur",
        geolocation={"latitude": 3.1390, "longitude": 101.6869},
        permissions=["geolocation"],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    )

    # Remove webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    page = await context.new_page()
    return pw, browser, context, page


async def random_delay(page: Page, min_ms: int = 2000, max_ms: int = 5000):
    """Wait a random amount of time."""
    await page.wait_for_timeout(random.randint(min_ms, max_ms))


async def random_mouse_move(page: Page):
    """Move mouse to a random position to appear human."""
    x = random.randint(100, 800)
    y = random.randint(100, 500)
    await page.mouse.move(x, y)


async def close_browser(pw, browser: Browser):
    """Gracefully close browser and playwright."""
    await browser.close()
    await pw.stop()
