"""Configuration for the *experimental* A-share historical data store."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = Path(os.environ.get("ASHARE_HISTORY_DIR", str(BASE_DIR / "database" / "stocks")))
DEFAULT_START_DATE = "20150101"
# Raw (unadjusted) OHLC allows true incremental append; qfq backward
# adjustment can change historical rows and MUST be completely rebuilt.
DEFAULT_ADJUST = ""
OVERLAP_CALENDAR_DAYS = 8
