"""Strict OHLCV and date validation before persisting third-party prices."""
from __future__ import annotations

import re
import pandas as pd

REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")


def validate_code(code: str) -> str:
    code = str(code)
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("股票代码必须为六位数字")
    return code


def normalize_history(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("历史行情不是 DataFrame")
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"缺少必要列: {missing}")
    if frame.empty:
        raise ValueError("行情为空")
    x = frame.copy()
    dates = pd.to_datetime(x["date"], errors="coerce")
    if dates.isna().any() or dates.dt.tz is not None:
        raise ValueError("日期缺失或包含时区")
    # Trading days are date-only, no partial/unfinished intraday candles.
    if (dates.dt.normalize() != dates).any():
        raise ValueError("日线日期包含盘中时间")
    x["date"] = dates.dt.normalize()
    for col in ("open", "high", "low", "close", "volume", "amount"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    if x[list(REQUIRED_COLUMNS[1:])].isna().any().any():
        raise ValueError("价格或成交数据存在非数字/空值")
    numeric = x[list(REQUIRED_COLUMNS[1:])]
    import numpy as np
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("存在 NaN 或 Infinity")
    if (x[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC 价格必须大于零")
    if (x[["volume", "amount"]] < 0).any().any():
        raise ValueError("成交量及成交额不能为负")
    if (x["high"] < x[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError("最高价低于开收盘或最低价")
    if (x["low"] > x[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("最低价高于开收盘或最高价")
    if x["date"].duplicated().any():
        raise ValueError("重复交易日期")
    if not x["date"].is_monotonic_increasing:
        raise ValueError("交易日期未按升序排列")
    keep = list(REQUIRED_COLUMNS)
    for optional in ("turnover",):
        if optional in x.columns:
            x[optional] = pd.to_numeric(x[optional], errors="coerce")
            keep.append(optional)
    return x.loc[:, keep].reset_index(drop=True)


def validate_history(frame: pd.DataFrame) -> bool:
    normalize_history(frame)
    return True
