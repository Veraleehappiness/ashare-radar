"""Real single-symbol history ingestion and small-overlap incremental updates."""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from .akshare_adapter import get_daily_history
from .config import DEFAULT_START_DATE, DEFAULT_ADJUST, OVERLAP_CALENDAR_DAYS
from .storage import save_history, load_history
from .validator import normalize_history, validate_code


def download_stock_history(
    code: str,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
    root: Path | str | None = None,
):
    """Fetch, validate, and atomically save historical daily bars."""
    code = validate_code(code)
    data = get_daily_history(code, start_date, end_date, adjust=DEFAULT_ADJUST)
    return save_history(code, data, root)


def update_stock_history(
    code: str,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
    root: Path | str | None = None,
    retries: int = 2,
    sleep_seconds: float = 1.0,
):
    """Fetch last 8 calendar days overlapping persisted data; dedupe by trade day.

    Missing network response never destroys the previous valid Parquet. No new rows
    is a valid state (holiday or suspension), and is NOT a successful latest-day
    refresh. Return explicit row/time diagnostics.
    """
    code = validate_code(code)
    if retries < 0 or retries > 5:
        raise ValueError("retries should be between 0 and 5")
    old = load_history(code, root)
    requested = start_date
    if old is not None and not old.empty:
        overlap = old.date.iloc[-1].date() - timedelta(days=OVERLAP_CALENDAR_DAYS)
        requested = max(start_date, overlap.strftime("%Y%m%d"))
    begin = time.monotonic()
    issue = None
    for attempt in range(retries + 1):
        try:
            fresh = get_daily_history(code, requested, end_date, adjust=DEFAULT_ADJUST)
            break
        except Exception as exc:
            issue = exc
            if attempt < retries and sleep_seconds > 0:
                time.sleep(min(30, sleep_seconds * (2 ** attempt)))
    else:
        raise RuntimeError(f"历史行情下载失败 {code}: {type(issue).__name__}: {str(issue)[:180]}") from issue
    observed_provider = fresh.attrs.get("provider", "AKShare / unspecified")
    if fresh.empty:
        if old is None:
            raise RuntimeError(f"{code} 没有可入库的真实日K线")
        return {
            "code": code, "status": "ok", "rows": int(len(old)),
            "added_rows": 0,
            "first_date": old.date.iloc[0].strftime("%Y-%m-%d"),
            "last_date": old.date.iloc[-1].strftime("%Y-%m-%d"),
            "fetched_start": requested, "updated_file": None,
            "elapsed_seconds": round(time.monotonic() - begin, 3),
            "adjust": "none", "provider": observed_provider,
            "note": "停牌/休市或无新增日K线；原历史数据保留"
        }
    if old is None:
        merged = fresh
        added = len(fresh)
    else:
        before = set(old.date)
        # Source wins for overlapping dates; validate after complete merge.
        merged = pd.concat([old, fresh], ignore_index=True)
        merged = merged.drop_duplicates(subset="date", keep="last").sort_values("date")
        merged = normalize_history(merged)
        added = len(set(merged.date) - before)
    path = save_history(code, merged, root) if (added > 0 or old is None or not fresh.empty) else None
    return {
        "code": code, "status": "ok",
        "rows": int(len(merged)), "added_rows": int(added),
        "first_date": merged.date.iloc[0].strftime("%Y-%m-%d"),
        "last_date": merged.date.iloc[-1].strftime("%Y-%m-%d"),
        "fetched_start": requested,
        "updated_file": str(path) if path else None,
        "elapsed_seconds": round(time.monotonic() - begin, 3),
        "adjust": "none", "provider": observed_provider,
    }
