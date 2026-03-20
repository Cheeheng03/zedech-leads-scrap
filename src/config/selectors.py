"""Centralized Google Maps CSS selectors — based on live probe 2026-03-20."""


class FeedSelectors:
    """Selectors for the results sidebar feed."""

    FEED = 'div[role="feed"]'
    # Real business cards have role="article", skips filter bar and "Results" header
    CARDS = 'div[role="feed"] div[role="article"]'
    CARD_LINK = "a[href*='maps/place']"
    WEBSITE_BUTTON = 'a[data-value="Website"]'


class DetailSelectors:
    """Selectors for the detail panel (after clicking into a listing)."""

    ADDRESS = 'button[data-item-id="address"]'
    PHONE = 'button[data-item-id^="phone:tel:"]'
    WEBSITE = 'a[data-item-id="authority"]'
    CATEGORY = 'button[jsaction*="category"]'
    RATING = 'span[role="img"]'
    REVIEWS = 'span[aria-label*="review"]'
    PHOTO_COUNT = 'button[jsaction*="heroHeaderImage"]'


class CaptchaSelectors:
    """Selectors for CAPTCHA / block page detection."""

    RECAPTCHA_IFRAME = 'iframe[src*="recaptcha"]'
    CAPTCHA_FORM = "#captcha-form"
    UNUSUAL_TRAFFIC = 'text="unusual traffic"'
    NOT_A_ROBOT = 'text="not a robot"'
    AUTOMATED_QUERIES = 'text="automated queries"'
