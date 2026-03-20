"""
Persistent scrape state manager.

Handles:
- Saving/loading the shuffled job queue so order is stable across restarts
- Rebuilding seen_place_ids from the database
- Resetting orphaned in_progress jobs on startup
- Graceful pause via signal or pause file
- Session stats that persist across runs
"""

import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.storage.database import Business, ScrapeJob


STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = STATE_DIR / "scrape_state.json"
PAUSE_FILE = STATE_DIR / ".pause"


class ScrapeState:
    """Manages all persistent state for the scraper."""

    def __init__(self, db: Session):
        self.db = db
        self.seen_place_ids: set[str] = set()
        self.job_queue: list[dict] = []  # [{term, state, city}, ...]
        self.queue_index: int = 0
        self.total_leads_all_time: int = 0
        self.total_sessions: int = 0
        self.session_leads: int = 0
        self.session_count: int = 0  # listings processed this session
        self._stop_requested: bool = False
        self._original_sigint = None
        self._original_sigterm = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, job_queue: list[tuple[str, str, str]]):
        """
        Load existing state or create fresh state from the given queue.
        Call this once at startup after building the full job list.
        """
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._rebuild_seen_place_ids()
        self._reset_orphaned_jobs()

        if STATE_FILE.exists():
            self._load_state()
            # Validate the loaded queue still matches (same layers/regions)
            new_keys = {f"{t}|{s}|{c}" for t, s, c in job_queue}
            old_keys = {f"{j['term']}|{j['state']}|{j['city']}" for j in self.job_queue}
            if new_keys == old_keys:
                print(f"[STATE] Resumed from saved state (position {self.queue_index}/{len(self.job_queue)})")
            else:
                print("[STATE] Job queue changed (different layers/regions). Rebuilding queue.")
                self._create_fresh_state(job_queue)
        else:
            self._create_fresh_state(job_queue)

        # Remove pause file if present from last run
        if PAUSE_FILE.exists():
            PAUSE_FILE.unlink()

        self.total_sessions += 1
        self.session_leads = 0
        self.session_count = 0
        self._save_state()

        print(f"[STATE] Known place_ids from DB: {len(self.seen_place_ids)}")
        print(f"[STATE] Total leads all time: {self.total_leads_all_time}")
        print(f"[STATE] Session #{self.total_sessions}")

    def _create_fresh_state(self, job_queue: list[tuple[str, str, str]]):
        """Create fresh state from a new shuffled queue."""
        self.job_queue = [
            {"term": t, "state": s, "city": c} for t, s, c in job_queue
        ]
        self.queue_index = 0
        self.total_leads_all_time = self.db.query(Business).count()
        self.total_sessions = 0
        self._save_state()
        print(f"[STATE] Created fresh state with {len(self.job_queue)} jobs")

    def _rebuild_seen_place_ids(self):
        """Load all known place_ids from the businesses table."""
        rows = self.db.query(Business.place_id).all()
        self.seen_place_ids = {r[0] for r in rows if r[0]}

    def _reset_orphaned_jobs(self):
        """Reset jobs stuck as in_progress (from a previous crash) back to pending."""
        orphaned = (
            self.db.query(ScrapeJob)
            .filter(ScrapeJob.status == "in_progress")
            .all()
        )
        if orphaned:
            for job in orphaned:
                job.status = "pending"
            self.db.commit()
            print(f"[STATE] Reset {len(orphaned)} orphaned in_progress jobs to pending")

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save_state(self):
        """Save current state to JSON file."""
        data = {
            "job_queue": self.job_queue,
            "queue_index": self.queue_index,
            "total_leads_all_time": self.total_leads_all_time,
            "total_sessions": self.total_sessions,
            "last_saved": datetime.now(timezone.utc).isoformat(),
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        """Load state from JSON file."""
        data = json.loads(STATE_FILE.read_text())
        self.job_queue = data.get("job_queue", [])
        self.queue_index = data.get("queue_index", 0)
        self.total_leads_all_time = data.get("total_leads_all_time", 0)
        self.total_sessions = data.get("total_sessions", 0)

    def save_progress(self):
        """Save current progress. Call after each completed job."""
        self._save_state()

    # ------------------------------------------------------------------
    # Job iteration
    # ------------------------------------------------------------------

    def get_pending_jobs(self) -> list[dict]:
        """Return remaining jobs from current queue position, skipping done ones."""
        remaining = self.job_queue[self.queue_index:]
        return remaining

    def advance(self):
        """Move to the next job in the queue and persist."""
        self.queue_index += 1
        self._save_state()

    def record_leads(self, count: int):
        """Record leads found in the current job."""
        self.session_leads += count
        self.total_leads_all_time += count
        self._save_state()

    # ------------------------------------------------------------------
    # Retry errored jobs
    # ------------------------------------------------------------------

    def get_errored_jobs(self) -> list[ScrapeJob]:
        """Get all jobs that errored and could be retried."""
        return (
            self.db.query(ScrapeJob)
            .filter(ScrapeJob.status == "error")
            .all()
        )

    def reset_errored_jobs(self) -> int:
        """Reset all errored jobs to pending so they get retried."""
        errored = self.get_errored_jobs()
        for job in errored:
            job.status = "pending"
            job.error_message = None
        self.db.commit()
        return len(errored)

    # ------------------------------------------------------------------
    # Graceful shutdown / pause
    # ------------------------------------------------------------------

    def install_signal_handlers(self):
        """Install SIGINT/SIGTERM handlers for graceful shutdown."""
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal — flag stop, don't kill immediately."""
        sig_name = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n[STATE] {sig_name} received. Will stop after current job finishes...")
        print("[STATE] Press Ctrl+C again to force quit (may lose current job progress).")
        self._stop_requested = True
        # Restore original handler so second Ctrl+C actually kills
        signal.signal(signal.SIGINT, self._original_sigint or signal.SIG_DFL)
        signal.signal(signal.SIGTERM, self._original_sigterm or signal.SIG_DFL)

    def should_stop(self) -> bool:
        """Check if we should stop (signal received OR pause file exists)."""
        if self._stop_requested:
            return True
        if PAUSE_FILE.exists():
            print("[STATE] Pause file detected. Stopping after current job...")
            self._stop_requested = True
            return True
        return False

    def request_stop(self):
        """Programmatically request a stop (e.g. from session limit)."""
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Status summary
    # ------------------------------------------------------------------

    def print_summary(self):
        """Print end-of-session summary."""
        done_count = self.db.query(ScrapeJob).filter(ScrapeJob.status == "done").count()
        error_count = self.db.query(ScrapeJob).filter(ScrapeJob.status == "error").count()
        pending_count = self.db.query(ScrapeJob).filter(ScrapeJob.status == "pending").count()
        total_biz = self.db.query(Business).count()

        print("\n" + "=" * 50)
        print("SESSION SUMMARY")
        print("=" * 50)
        print(f"  Leads found this session: {self.session_leads}")
        print(f"  Listings processed:       {self.session_count}")
        print(f"  Queue position:           {self.queue_index}/{len(self.job_queue)}")
        print(f"  Jobs done:                {done_count}")
        print(f"  Jobs pending:             {pending_count}")
        print(f"  Jobs errored:             {error_count}")
        print(f"  Total businesses in DB:   {total_biz}")
        print(f"  Total sessions so far:    {self.total_sessions}")
        print("=" * 50)

        if pending_count > 0 or error_count > 0:
            print("Run the script again to continue from where you left off.")
        else:
            print("All jobs complete!")

        if error_count > 0:
            print(f"Tip: {error_count} errored jobs will be retried on next run.")
