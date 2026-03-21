"""Run Phase 2 scoring on collected data. No browser needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.filter import reclassify_all
from src.pipeline.scorer import run_scoring
from src.storage.database import get_session, init_db


def main():
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

    db.close()
    print("\nScoring pipeline complete!")


if __name__ == "__main__":
    main()
