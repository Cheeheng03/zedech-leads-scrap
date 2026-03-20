"""
Show current scrape progress without running the scraper.

Usage: python3 scripts/scrape_status.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import Business, ScrapeJob, get_session, init_db

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "scrape_state.json"


def main():
    init_db()
    db = get_session()

    done = db.query(ScrapeJob).filter(ScrapeJob.status == "done").count()
    pending = db.query(ScrapeJob).filter(ScrapeJob.status == "pending").count()
    in_progress = db.query(ScrapeJob).filter(ScrapeJob.status == "in_progress").count()
    errored = db.query(ScrapeJob).filter(ScrapeJob.status == "error").count()
    total_jobs = db.query(ScrapeJob).count()

    total_biz = db.query(Business).count()
    no_website = db.query(Business).filter(Business.website_status == "none").count()
    social_only = db.query(Business).filter(Business.website_status == "social_only").count()

    # State file info
    queue_pos = "-"
    queue_total = "-"
    sessions = "-"
    last_saved = "-"
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        queue_pos = state.get("queue_index", "?")
        queue_total = len(state.get("job_queue", []))
        sessions = state.get("total_sessions", "?")
        last_saved = state.get("last_saved", "?")

    print("=" * 50)
    print("SCRAPE STATUS")
    print("=" * 50)
    print()
    print("Jobs:")
    print(f"  Done:        {done}")
    print(f"  Pending:     {pending}")
    print(f"  In Progress: {in_progress}")
    print(f"  Errored:     {errored}")
    print(f"  Total:       {total_jobs}")
    print()
    print("Businesses:")
    print(f"  Total:       {total_biz}")
    print(f"  No website:  {no_website}")
    print(f"  Social only: {social_only}")
    print()
    print("Queue:")
    print(f"  Position:    {queue_pos}/{queue_total}")
    print(f"  Sessions:    {sessions}")
    print(f"  Last saved:  {last_saved}")
    print()

    # Show errored jobs if any
    if errored > 0:
        print("Recent errors:")
        err_jobs = (
            db.query(ScrapeJob)
            .filter(ScrapeJob.status == "error")
            .order_by(ScrapeJob.finished_at.desc())
            .limit(5)
            .all()
        )
        for j in err_jobs:
            print(f"  [{j.search_term}] {j.region}: {j.error_message[:80] if j.error_message else '?'}")

    # By state breakdown
    print("\nLeads by state:")
    from sqlalchemy import func
    state_counts = (
        db.query(Business.state, func.count(Business.id))
        .group_by(Business.state)
        .all()
    )
    for state_name, count in state_counts:
        print(f"  {state_name}: {count}")

    db.close()


if __name__ == "__main__":
    main()
