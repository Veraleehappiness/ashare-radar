import akshare as ak
import pandas as pd


def get_daily_history(code, start_date="20150101", end_date="20991231"):
    df = ak.stock_zh_a_hist(
        symbol=str(code),
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"
    )

    mapping = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount"
    }

    df = df.rename(columns=mapping)
    return df
