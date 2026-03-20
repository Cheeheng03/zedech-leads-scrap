"""CLI export of leads to CSV or Excel."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import get_session, init_db
from src.storage.exporter import export_csv, export_excel


def main():
    parser = argparse.ArgumentParser(description="Export leads to CSV or Excel")
    parser.add_argument("--format", choices=["csv", "excel"], default="csv")
    parser.add_argument("--output", "-o", default="data/leads_export")
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--states", nargs="*", help="Filter by state(s)")
    parser.add_argument("--status", nargs="*", default=["none", "social_only"],
                        help="Website status filter")
    parser.add_argument("--not-contacted", action="store_true",
                        help="Only show businesses not yet contacted")
    args = parser.parse_args()

    init_db()
    db = get_session()

    filters = {
        "min_score": args.min_score,
        "states": args.states,
        "website_status": args.status,
    }
    if args.not_contacted:
        filters["contacted"] = False

    ext = "csv" if args.format == "csv" else "xlsx"
    output = f"{args.output}.{ext}"

    if args.format == "csv":
        export_csv(db, output, **filters)
    else:
        export_excel(db, output, **filters)

    db.close()


if __name__ == "__main__":
    main()
