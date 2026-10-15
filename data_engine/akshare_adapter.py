"""AKShare A-share daily OHLCV adapter. No mocked data in production."""
from __future__ import annotations

from datetime import date
import pandas as pd
from .validator import normalize_history, validate_code

MAP = {
    "日期": "date", "开盘": "open", "最高": "high",
    "最低": "low", "收盘": "close", "成交量": "volume",
    "成交额": "amount", "换手率": "turnover",
}


def get_daily_history(
    code: str,
    start_date: str = "20150101",
    end_date: str | None = None,
    adjust: str = "",
) -> pd.DataFrame:
    """Get real history; default no adjustment for safely appendable candles.

    This API has no guarantee of uptime; callers implement retry/backoff.
    In particular, do not silently switch sources or substitute fake bars.
    """
    validate_code(code)
    if adjust != "":
        raise ValueError("当前增量历史库仅支持不复权行情；前复权需单独全量重建")
    if end_date is None:
        end_date = date.today().strftime("%Y%m%d")
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        if len(value) != 8 or not value.isdigit():
            raise ValueError(f"{name} 必须为 YYYYMMDD")
    if start_date > end_date:
        raise ValueError("开始日期不得晚于结束日期")
    import akshare as ak  # optional for unit tests; required for real downloads
    raw = ak.stock_zh_a_hist(
        symbol=code, period="daily", start_date=start_date,
        end_date=end_date, adjust=adjust,
    )
    if raw is None or not isinstance(raw, pd.DataFrame):
        raise RuntimeError(f"AKShare 返回数据无效: {code}")
    return normalize_history(raw.rename(columns=MAP))
