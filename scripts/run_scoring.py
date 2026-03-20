"""Run Phase 2 scoring on collected data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import settings
from src.pipeline.filter import reclassify_all
from src.pipeline.scorer import run_scoring
from src.pipeline.google_checker import run_google_checks
from src.scraper.browser import close_browser, launch_browser
from src.storage.database import get_session, init_db


async def main():
    init_db()
    db = get_session()

    print("=== Phase 2: Scoring Pipeline ===\n")

    # Step 1: Reclassify website statuses
    print("Step 1: Reclassifying website statuses...")
    reclassify_all(db)
    print()

    # Step 2: Score all businesses
    print("Step 2: Scoring businesses...")
    run_scoring(db)
    print()

    # Step 3: Google cross-check for high-score leads
    print("Step 3: Google cross-check for high-score leads...")
    print("This requires a browser. Launch? (y/n): ", end="")
    choice = input().strip().lower()

    if choice == "y":
        pw, browser, context, page = await launch_browser(headless=settings.headless)
        try:
            await run_google_checks(page, db)
        finally:
            await close_browser(pw, browser)
    else:
        print("Skipping Google checks.")

    db.close()
    print("\nScoring pipeline complete!")


if __name__ == "__main__":
    asyncio.run(main())
