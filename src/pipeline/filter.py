"""Website status classification for businesses."""

from sqlalchemy.orm import Session

from src.storage.database import Business


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


def classify_website_status(website: str | None) -> str:
    """Classify a website URL into status categories."""
    if not website:
        return "none"

    url_lower = website.lower()

    if any(domain in url_lower for domain in SOCIAL_DOMAINS):
        return "social_only"

    return "active"


def reclassify_all(session: Session) -> int:
    """Re-classify website_status for all businesses."""
    businesses = session.query(Business).all()
    updated = 0
    for biz in businesses:
        new_status = classify_website_status(biz.website)
        if biz.website_status != new_status:
            biz.website_status = new_status
            updated += 1
    session.commit()
    print(f"Reclassified {updated} businesses.")
    return updated
