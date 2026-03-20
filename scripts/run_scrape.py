"""Main orchestrator for Phase 1: scrape Google Maps for SMEs without websites."""

import asyncio
import random
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.regions import REGIONS
from src.config.search_terms import get_terms
from src.config.settings import settings
from src.scraper.browser import close_browser, launch_browser, random_delay
from src.scraper.maps_scraper import scrape_search
from src.storage.database import (
    get_or_create_job,
    get_session,
    init_db,
)
from src.storage.state import ScrapeState


async def main():
    # Parse layers from settings
    layers = [l.strip() for l in settings.scrape_layers.split(",")]
    terms = get_terms(layers)

    print(f"Layers: {layers}")
    print(f"Total search terms: {len(terms)}")
    print(f"Regions: {list(REGIONS.keys())}")
    print(f"Session limit: {settings.session_limit}")
    print()

    # Init DB
    init_db()
    db = get_session()

    # Build full job list: (term, state, city)
    jobs_list: list[tuple[str, str, str]] = []
    for state_name, cities in REGIONS.items():
        for city in cities:
            for term in terms:
                jobs_list.append((term, state_name, city))

    # Shuffle for anti-detection (only used if no saved state)
    random.shuffle(jobs_list)

    # Initialize state manager — loads saved queue or uses the shuffled one
    scrape_state = ScrapeState(db)
    scrape_state.initialize(jobs_list)
    scrape_state.install_signal_handlers()

    # Reset errored jobs so they get retried
    retried = scrape_state.reset_errored_jobs()
    if retried:
        print(f"[RETRY] Reset {retried} errored jobs for retry")

    # Get remaining jobs from saved queue position
    remaining_jobs = scrape_state.get_pending_jobs()

    # Filter to only pending/error jobs (skip done)
    pending: list[tuple[dict, any]] = []
    for job_info in remaining_jobs:
        region = f"{job_info['city']}, {job_info['state']}"
        job = get_or_create_job(db, job_info["term"], region)
        if job.status == "done":
            continue
        pending.append((job_info, job))

    print(f"Actionable queries remaining: {len(pending)}\n")

    if not pending:
        print("All jobs already done!")
        scrape_state.print_summary()
        db.close()
        return

    # Launch browser
    pw, browser, context, page = await launch_browser(headless=settings.headless)

    try:
        for idx, (job_info, job) in enumerate(pending):
            # Check all stop conditions
            if scrape_state.should_stop():
                print("\n[STOP] Graceful stop requested.")
                break

            if settings.session_limit > 0 and scrape_state.session_count >= settings.session_limit:
                print(f"\n[STOP] Session limit reached ({settings.session_limit}).")
                scrape_state.request_stop()
                break

            term = job_info["term"]
            state_name = job_info["state"]
            city = job_info["city"]
            region = f"{city}, {state_name}"

            print(f"[{scrape_state.queue_index + 1}/{len(scrape_state.job_queue)}] "
                  f"Searching: '{term}' near {region}")

            leads, scrape_state.session_count = await scrape_search(
                page=page,
                session=db,
                job=job,
                term=term,
                state=state_name,
                city=city,
                seen_place_ids=scrape_state.seen_place_ids,
                session_count=scrape_state.session_count,
                session_limit=settings.session_limit,
            )

            scrape_state.record_leads(leads)
            scrape_state.advance()

            print(f"  Found {leads} new leads "
                  f"(session: {scrape_state.session_leads}, "
                  f"all-time: {scrape_state.total_leads_all_time})")

            # Random delay between searches
            await random_delay(page, settings.delay_min_ms, settings.delay_max_ms)

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        scrape_state.save_progress()
    finally:
        scrape_state.save_progress()
        await close_browser(pw, browser)
        scrape_state.print_summary()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
