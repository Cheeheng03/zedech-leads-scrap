"""
Create a pause file to signal the running scraper to stop gracefully
after its current job finishes.

Usage: python3 scripts/pause_scrape.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PAUSE_FILE = Path(__file__).resolve().parent.parent / "data" / ".pause"


def main():
    PAUSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAUSE_FILE.touch()
    print(f"Pause file created: {PAUSE_FILE}")
    print("The scraper will stop after its current job finishes.")
    print("The pause file is auto-removed on next startup.")


if __name__ == "__main__":
    main()
