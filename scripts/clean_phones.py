"""Clean phone numbers: remove spaces and dashes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import Business, get_session, init_db


def main():
    init_db()
    db = get_session()

    businesses = db.query(Business).filter(Business.phone.isnot(None)).all()

    updated = 0
    for biz in businesses:
        cleaned = biz.phone.replace(" ", "").replace("-", "")
        if cleaned != biz.phone:
            biz.phone = cleaned
            updated += 1

    db.commit()
    db.close()
    print(f"Cleaned {updated} phone numbers.")


if __name__ == "__main__":
    main()
