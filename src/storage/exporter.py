"""Export leads to CSV/Excel."""

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from src.storage.database import Business


def query_leads(
    session: Session,
    min_score: int = 0,
    states: list[str] | None = None,
    website_status: list[str] | None = None,
    contacted: bool | None = None,
    sectors: list[str] | None = None,
) -> pd.DataFrame:
    """Query leads with optional filters, return as DataFrame."""
    q = session.query(Business).filter(Business.score >= min_score)

    if states:
        q = q.filter(Business.state.in_(states))
    if website_status:
        q = q.filter(Business.website_status.in_(website_status))
    if contacted is not None:
        q = q.filter(Business.contacted == contacted)
    if sectors:
        q = q.filter(Business.sector_query.in_(sectors))

    q = q.order_by(Business.score.desc())

    rows = []
    for biz in q.all():
        rows.append({
            "Name": biz.name,
            "Phone": biz.phone,
            "Address": biz.address,
            "City": biz.city,
            "State": biz.state,
            "Category": biz.category,
            "Sector": biz.sector_query,
            "Website Status": biz.website_status,
            "Rating": biz.rating,
            "Reviews": biz.reviews_count,
            "Photos": biz.photo_count,
            "Score": biz.score,
            "Score Breakdown": biz.score_breakdown,
            "Google Confirmed No Site": biz.google_confirmed_no_site,
            "Google Maps URL": biz.google_maps_url,
            "Contacted": biz.contacted,
            "Notes": biz.notes,
            "Scraped At": biz.scraped_at,
        })

    return pd.DataFrame(rows)


def export_csv(session: Session, output_path: str, **filters) -> str:
    """Export filtered leads to CSV."""
    df = query_leads(session, **filters)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Exported {len(df)} leads to {path}")
    return str(path)


def export_excel(session: Session, output_path: str, **filters) -> str:
    """Export filtered leads to Excel."""
    df = query_leads(session, **filters)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, engine="openpyxl")
    print(f"Exported {len(df)} leads to {path}")
    return str(path)
