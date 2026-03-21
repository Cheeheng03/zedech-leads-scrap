"""Run scraper for NEWLY ADDED B2B search terms alongside existing scrapers.

Only contains terms that did NOT exist in the original 3 layers.
No overlap with running scrapers — safe to run in parallel.

Usage:
    python3 scripts/run_scrape_new_terms.py
    python3 scripts/run_scrape_new_terms.py "Johor"
    python3 scripts/run_scrape_new_terms.py "Selangor,Kuala Lumpur"
"""

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.regions import REGIONS
from src.config.settings import settings
from src.scraper.browser import close_browser, launch_browser, random_delay
from src.scraper.maps_scraper import scrape_search
from src.storage.database import (
    Business,
    get_or_create_job,
    get_session,
    init_db,
    ScrapeJob,
)

# ─── ONLY genuinely new terms (not in original 3 layers) ───────────────

NEW_TERMS: list[str] = [
    # Construction (compound terms not in old layers)
    "construction company", "building contractor", "maintenance company",
    "cleaning company",

    # Digital-ready trades (specific, not in old layers)
    "aircond service", "electrical contractor", "plumber",
    "landscaping", "security company", "fire safety",

    # Hospitality & property (ALL new)
    "homestay", "airbnb", "resort", "chalet", "villa",
    "guest house", "budget hotel",
    "property management", "real estate agent",

    # Events (ALL new)
    "event management", "event space", "wedding planner",
    "catering company", "canopy rental",

    # Industrial (only terms not in old layer 3)
    "metal fabrication", "glass supplier", "timber supplier",
    "car detailing", "fleet management", "OEM", "printing company",

    # Health & wellness (ALL new)
    "clinic", "dental", "physiotherapy", "spa",
    "traditional medicine", "wellness center",

    # Education (ALL new)
    "tuition centre", "training centre", "driving school",

    # Professional services (ALL new)
    "accounting firm", "audit firm", "consultant",
    "engineering firm", "surveyor",

    # Logistics & transport (ALL new)
    "transport company", "logistics", "freight", "warehousing",
    "cold storage", "movers",

    # Niche high-value (only terms not in old layers)
    "signage company", "signboard",
    "alarm system", "automation",
    "CCTV", "carpet supplier", "uniform supplier",
]


async def main():
    # Parse args
    target_states = list(REGIONS.keys())  # default: all states

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        target_states = [s.strip() for s in sys.argv[1].split(",")]

    # Validate states
    for s in target_states:
        if s not in REGIONS:
            print(f"Unknown state: '{s}'")
            print(f"Available: {', '.join(REGIONS.keys())}")
            sys.exit(1)

    print("=" * 50)
    print("NEW B2B TERMS SCRAPER (runs alongside existing)")
    print("=" * 50)
    print(f"States: {', '.join(target_states)}")
    print(f"New terms: {len(NEW_TERMS)}")
    print()

    init_db()
    db = get_session()

    # Build job list
    jobs_list: list[tuple[str, str, str]] = []
    for state_name in target_states:
        for city in REGIONS[state_name]:
            for term in NEW_TERMS:
                jobs_list.append((term, state_name, city))

    random.shuffle(jobs_list)

    # Filter to pending/error jobs
    pending = []
    for term, state_name, city in jobs_list:
        region = f"{city}, {state_name}"
        job = get_or_create_job(db, term, region)
        if job.status == "done":
            continue
        if job.status == "in_progress":
            job.status = "pending"
            db.commit()
        if job.status == "error":
            job.status = "pending"
            job.error_message = None
            db.commit()
        pending.append((term, state_name, city, job))

    print(f"Total queries: {len(jobs_list)}, Pending: {len(pending)}")

    if not pending:
        print("All jobs done!")
        db.close()
        return

    # Load seen place_ids from DB for dedup
    seen_place_ids: set[str] = {
        r[0] for r in db.query(Business.place_id).all() if r[0]
    }
    print(f"Known place_ids: {len(seen_place_ids)}\n")

    pw, browser, context, page = await launch_browser(headless=settings.headless)
    session_count = 0
    total_leads = 0

    try:
        for idx, (term, state_name, city, job) in enumerate(pending):
            region = f"{city}, {state_name}"
            print(f"[{idx + 1}/{len(pending)}] '{term}' near {region}")

            leads, session_count = await scrape_search(
                page=page,
                session=db,
                job=job,
                term=term,
                state=state_name,
                city=city,
                seen_place_ids=seen_place_ids,
                session_count=session_count,
                session_limit=0,  # unlimited
            )

            total_leads += leads
            if leads > 0:
                print(f"  +{leads} leads (total: {total_leads})")

            await random_delay(page, settings.delay_min_ms, settings.delay_max_ms)

    except KeyboardInterrupt:
        print("\nStopped. Progress saved via scrape_jobs table.")
    finally:
        await close_browser(pw, browser)
        db.close()

    print(f"\nDone! New leads found: {total_leads}")


if __name__ == "__main__":
    asyncio.run(main())
