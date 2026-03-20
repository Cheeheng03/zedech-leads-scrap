"""Score businesses by quality signals."""

import json

from sqlalchemy.orm import Session

from src.storage.database import Business


REGISTERED_KEYWORDS = ["sdn bhd", "enterprise", "trading", "industries", "corporation"]
SERVICE_CATEGORIES = [
    "workshop", "repair", "service", "contractor", "maintenance",
    "clinic", "tuition", "bengkel", "perkhidmatan", "installation",
]


def score_business(biz: Business) -> tuple[int, dict]:
    """Calculate lead score and breakdown for a business."""
    breakdown: dict[str, int] = {}
    total = 0

    # Review count: 0-3 pts
    rc = biz.reviews_count or 0
    if rc == 0:
        breakdown["reviews"] = 0
    elif rc <= 10:
        breakdown["reviews"] = 1
    elif rc <= 50:
        breakdown["reviews"] = 2
    else:
        breakdown["reviews"] = 3
    total += breakdown["reviews"]

    # Rating: 0-2 pts
    r = biz.rating or 0
    if r < 3.5:
        breakdown["rating"] = 0
    elif r < 4.2:
        breakdown["rating"] = 1
    else:
        breakdown["rating"] = 2
    total += breakdown["rating"]

    # Photo count (low = needs help): 0-2 pts
    pc = biz.photo_count or 0
    if pc < 3:
        breakdown["photos"] = 2
    elif pc <= 10:
        breakdown["photos"] = 1
    else:
        breakdown["photos"] = 0
    total += breakdown["photos"]

    # Has phone number: 1 pt
    if biz.phone:
        breakdown["phone"] = 1
    else:
        breakdown["phone"] = 0
    total += breakdown["phone"]

    # Business name signals: 0-2 pts
    name_lower = (biz.name or "").lower()
    name_matches = sum(1 for kw in REGISTERED_KEYWORDS if kw in name_lower)
    breakdown["name_signals"] = min(name_matches, 2)
    total += breakdown["name_signals"]

    # Category is service-based: 1 pt
    cat_lower = (biz.category or "").lower()
    if any(svc in cat_lower for svc in SERVICE_CATEGORIES):
        breakdown["service_category"] = 1
    else:
        breakdown["service_category"] = 0
    total += breakdown["service_category"]

    # Social-only website: 1 pt
    if biz.website_status == "social_only":
        breakdown["social_only"] = 1
    else:
        breakdown["social_only"] = 0
    total += breakdown["social_only"]

    return total, breakdown


def run_scoring(session: Session):
    """Score all unscored businesses (website_status in none/social_only)."""
    businesses = (
        session.query(Business)
        .filter(Business.website_status.in_(["none", "social_only"]))
        .all()
    )

    scored = 0
    for biz in businesses:
        total, breakdown = score_business(biz)
        biz.score = total
        biz.score_breakdown = json.dumps(breakdown)
        scored += 1

    session.commit()
    print(f"Scored {scored} businesses.")
    return scored
