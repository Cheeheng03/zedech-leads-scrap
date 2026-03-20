"""Run scraper for a specific region only. Allows parallel scraping by state.

Usage:
    python3 scripts/run_scrape_region.py "Johor"
    python3 scripts/run_scrape_region.py "Melaka"
    python3 scripts/run_scrape_region.py "Selangor,Kuala Lumpur"
"""

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.regions import REGIONS
from src.config.search_terms import get_terms
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


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/run_scrape_region.py \"State1,State2\"")
        print(f"Available: {', '.join(REGIONS.keys())}")
        sys.exit(1)

    target_states = [s.strip() for s in sys.argv[1].split(",")]

    # Validate
    for s in target_states:
        if s not in REGIONS:
            print(f"Unknown state: '{s}'")
            print(f"Available: {', '.join(REGIONS.keys())}")
            sys.exit(1)

    layers = [l.strip() for l in settings.scrape_layers.split(",")]
    terms = get_terms(layers)

    print(f"States: {target_states}")
    print(f"Layers: {layers} ({len(terms)} terms)")
    print()

    init_db()
    db = get_session()

    # Build job list for target states only
    jobs_list: list[tuple[str, str, str]] = []
    for state_name in target_states:
        for city in REGIONS[state_name]:
            for term in terms:
                jobs_list.append((term, state_name, city))

    random.shuffle(jobs_list)

    # Filter to pending/error jobs
    pending = []
    for term, state_name, city in jobs_list:
        region = f"{city}, {state_name}"
        job = get_or_create_job(db, term, region)
        if job.status in ("done",):
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
        print("All jobs done for these states!")
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
        print("\nStopped. Progress saved.")
    finally:
        await close_browser(pw, browser)
        db.close()

    print(f"\nDone! Leads found: {total_leads}")


if __name__ == "__main__":
    asyncio.run(main())
