from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database" / "stocks"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_START_DATE = "20150101"
DEFAULT_ADJUST = "qfq"
