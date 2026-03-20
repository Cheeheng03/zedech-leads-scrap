"""Extract business data from Google Maps page elements."""

import re

from playwright.async_api import Locator, Page

from src.config.selectors import DetailSelectors, FeedSelectors


SOCIAL_DOMAINS = [
    "facebook.com", "fb.com", "fb.me",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "linkedin.com",
    "wa.me", "api.whatsapp.com",
    "linktr.ee",
    "shopee.", "lazada.",
]


def classify_url(url: str) -> str:
    """Classify a URL as 'none', 'social_only', or 'active'."""
    if not url:
        return "none"
    url_lower = url.lower()
    if any(domain in url_lower for domain in SOCIAL_DOMAINS):
        return "social_only"
    return "active"


async def card_is_sponsored(card: Locator) -> bool:
    """Check if a result card is a sponsored listing."""
    try:
        text = await card.inner_text()
        first_line = text.strip().split("\n")[0].strip().lower()
        if first_line in ("sponsored", "ad"):
            return True
    except Exception:
        pass
    return False


async def get_card_website_status(card: Locator) -> tuple[str, str]:
    """
    Check website button on card and read the actual href.
    Returns (status, url) where status is 'none' | 'social_only' | 'active'.
    """
    btn = card.locator(FeedSelectors.WEBSITE_BUTTON).first
    if await btn.count() == 0:
        return "none", ""

    try:
        href = await btn.get_attribute("href") or ""
        return classify_url(href), href
    except Exception:
        return "active", ""  # Can't read href, assume real to be safe


async def extract_from_card(card: Locator, state: str, city: str, search_term: str) -> dict | None:
    """
    Extract as much data as possible from the card HTML without clicking in.

    From the card we can get:
    - name (aria-label on the article)
    - rating + review count (span[role="img"] aria-label like "4.7 stars 166 Reviews")
    - category + address (from card text)
    - website URL (from a[data-value="Website"] href)
    - place_id, coordinates, google_maps_url (from the card link href)
    - phone (regex on card text for Malaysian phone patterns)
    """
    try:
        name = await card.get_attribute("aria-label") or ""
        # Clean "· Visited link" suffix
        name = re.sub(r"\s*·\s*Visited link\s*$", "", name).strip()
        if not name:
            return None
    except Exception:
        return None

    data: dict = {
        "name": name,
        "state": state,
        "city": city,
        "sector_query": search_term,
    }

    # Place link — contains place_id, coords, google maps URL
    try:
        link = card.locator(FeedSelectors.CARD_LINK).first
        if await link.count() > 0:
            href = await link.get_attribute("href") or ""
            data["google_maps_url"] = href

            # Place ID: !1s0x304ac704a15e67c9:0x69d1405c2731eb1c
            place_match = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href)
            if place_match:
                data["place_id"] = place_match.group(1)

            # Coordinates: !3d5.368733!4d100.4143155
            coord_match = re.search(r"!3d(-?[\d.]+)!4d(-?[\d.]+)", href)
            if coord_match:
                data["latitude"] = float(coord_match.group(1))
                data["longitude"] = float(coord_match.group(2))
        else:
            return None
    except Exception:
        return None

    if "place_id" not in data:
        data["place_id"] = f"{name}_{city}"

    # Rating + reviews from span[role="img"]
    try:
        rating_el = card.locator('span[role="img"]').first
        if await rating_el.count() > 0:
            label = await rating_el.get_attribute("aria-label") or ""
            # "4.7 stars 166 Reviews"
            r_match = re.search(r"([\d.]+)\s*star", label, re.IGNORECASE)
            if r_match:
                data["rating"] = float(r_match.group(1))
            rev_match = re.search(r"([\d,]+)\s*Review", label, re.IGNORECASE)
            if rev_match:
                data["reviews_count"] = int(rev_match.group(1).replace(",", ""))
    except Exception:
        pass

    # Card text — extract category, address, phone
    try:
        text = await card.inner_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Phone: match Malaysian patterns like 07-352 2352, 012-345 6789, 011-1600 1366
        for line in lines:
            phone_match = re.search(r"(0\d{1,2}[- ]?\d{3,4}[- ]?\d{4})", line)
            if phone_match:
                data["phone"] = phone_match.group(1)
                break

        # Category is usually after the rating line, before address
        # Format: "Category · Address" or just "Category"
        for line in lines:
            if "·" in line and not line.startswith("Open") and not line.startswith("Close"):
                parts = line.split("·", 1)
                cat = parts[0].strip()
                if cat and cat not in (name, "Sponsored", "Ad"):
                    data["category"] = cat
                if len(parts) > 1:
                    addr = parts[1].strip()
                    if addr:
                        data["address"] = addr
                break
    except Exception:
        pass

    return data


async def extract_detail_panel(
    page: Page, card_data: dict
) -> dict | None:
    """
    Extract additional details from the detail panel that aren't on the card.
    Merges with existing card_data.

    Main things we get from detail panel that card doesn't have:
    - Full address (card may truncate)
    - Phone (if not on card)
    - Website URL (confirmed)
    - Photo count
    """
    # Wait for detail panel to load (address button is a reliable signal)
    try:
        await page.wait_for_selector(DetailSelectors.ADDRESS, timeout=8000)
    except Exception:
        return card_data  # Return card data even if detail panel fails

    data = dict(card_data)

    # Full address (detail panel has the complete one)
    try:
        addr_el = page.locator(DetailSelectors.ADDRESS).first
        if await addr_el.count() > 0:
            addr_text = await addr_el.get_attribute("aria-label") or await addr_el.inner_text()
            data["address"] = addr_text.replace("Address: ", "").strip()
    except Exception:
        pass

    # Phone (detail panel is more reliable)
    try:
        phone_el = page.locator(DetailSelectors.PHONE).first
        if await phone_el.count() > 0:
            phone_attr = await phone_el.get_attribute("data-item-id") or ""
            match = re.search(r"phone:tel:(\d+)", phone_attr)
            if match:
                raw = match.group(1)
                # Format nicely
                if len(raw) >= 10:
                    data["phone"] = f"{raw[:3]}-{raw[3:6]} {raw[6:]}"
                elif len(raw) >= 9:
                    data["phone"] = f"{raw[:2]}-{raw[2:5]} {raw[5:]}"
                else:
                    data["phone"] = raw
            else:
                data["phone"] = (await phone_el.inner_text()).strip()
    except Exception:
        pass

    # Website (confirmed from detail panel)
    try:
        web_el = page.locator(DetailSelectors.WEBSITE).first
        if await web_el.count() > 0:
            href = await web_el.get_attribute("href") or ""
            data["website"] = href
            data["website_status"] = classify_url(href)
    except Exception:
        pass

    # Category (detail panel may be more specific)
    try:
        cat_el = page.locator(DetailSelectors.CATEGORY).first
        if await cat_el.count() > 0:
            data["category"] = (await cat_el.inner_text()).strip()
    except Exception:
        pass

    # Photo count (only on detail panel)
    try:
        photo_el = page.locator(DetailSelectors.PHOTO_COUNT).first
        if await photo_el.count() > 0:
            photo_text = await photo_el.inner_text()
            match = re.search(r"([\d,]+)\s*photo", photo_text, re.IGNORECASE)
            if match:
                data["photo_count"] = int(match.group(1).replace(",", ""))
    except Exception:
        pass

    # Update google_maps_url to the detail page URL (more specific)
    data["google_maps_url"] = page.url

    return data
