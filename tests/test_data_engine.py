"""Offline V0.7 tests: synthetic fixtures ONLY, never fake production market data."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import sys
import pandas as pd
import pytest

from data_engine.akshare_adapter import get_daily_history
from data_engine.history_downloader import update_stock_history
from data_engine.provider import HistoryProvider
from data_engine.storage import load_history, save_history, history_path
from data_engine.validator import normalize_history, validate_history, validate_code


def bars(dates=("2026-01-05", "2026-01-06"), first=10.0):
    return pd.DataFrame({
        "date": pd.to_datetime(list(dates)),
        "open": [first] * len(dates),
        "high": [first + 2] * len(dates),
        "low": [first - 1] * len(dates),
        "close": [first + 1] * len(dates),
        "volume": [1000] * len(dates),
        "amount": [14000] * len(dates),
    })


def test_roundtrip_and_provider(tmp_path):
    original = bars()
    path = save_history("600519", original, tmp_path)
    assert path.is_file()
    got = load_history("600519", tmp_path)
    pd.testing.assert_frame_equal(got, original, check_dtype=False)
    provider = HistoryProvider(tmp_path)
    assert len(provider.get_history("600519", days=1)) == 1
    assert len(provider.get_history("600519", days=None)) == 2
    with pytest.raises(FileNotFoundError):
        provider.get_history("000001")


@pytest.mark.parametrize("bad_col,bad_val", [
    ("high", 1.0), ("low", 14.0), ("volume", -5),
    ("amount", -1), ("open", 0),
])
def test_validator_rejects_bad_ohlcv(bad_col, bad_val):
    x = bars()
    x.loc[0, bad_col] = bad_val
    with pytest.raises(ValueError):
        validate_history(x)


def test_validator_rejects_dates_nans_and_duplicate():
    data = bars()
    data.loc[1, "date"] = data.loc[0, "date"]
    with pytest.raises(ValueError, match="重复"):
        validate_history(data)
    data = bars().iloc[::-1]
    with pytest.raises(ValueError, match="升序"):
        validate_history(data)
    data = bars()
    data.loc[1, "close"] = float("nan")
    with pytest.raises(ValueError):
        validate_history(data)


def test_code_path_traversal_rejected(tmp_path):
    for invalid in ("../x", "60051", "600519.parquet", "TEST001"):
        with pytest.raises(ValueError):
            history_path(invalid, tmp_path)


def test_adapter_maps_real_akshare_column_names():
    raw = bars().rename(columns={
        "date":"日期", "open":"开盘", "high":"最高",
        "low":"最低", "close":"收盘", "volume":"成交量",
        "amount":"成交额",
    })
    fake = SimpleNamespace(stock_zh_a_hist=lambda **kwargs: raw)
    with patch.dict(sys.modules, {"akshare":fake}):
        x=get_daily_history("600519", start_date="20260101", end_date="20260108")
    assert list(x.columns) == ["date","open","high","low","close","volume","amount"]
    assert len(x)==2


def test_incremental_adds_only_missing_dates_and_is_idempotent(tmp_path):
    original=bars()
    save_history("600519", original, tmp_path)
    data=bars(("2026-01-06","2026-01-07"))
    with patch("data_engine.history_downloader.get_daily_history",return_value=data) as mocked:
        result=update_stock_history("600519",root=tmp_path,retries=0)
        assert mocked.call_args.args[1] == "20251229"
    assert result["added_rows"] == 1
    assert result["rows"] == 3
    with patch("data_engine.history_downloader.get_daily_history",return_value=data):
        repeat=update_stock_history("600519",root=tmp_path,retries=0)
    assert repeat["added_rows"]==0
    assert len(HistoryProvider(tmp_path).get_history("600519",days=None)) == 3


def test_network_failure_preserves_previous_database(tmp_path):
    save_history("600519", bars(), tmp_path)
    prior=history_path("600519",tmp_path).read_bytes()
    with patch("data_engine.history_downloader.get_daily_history",side_effect=ConnectionError("offline")):
        with pytest.raises(RuntimeError,match="历史行情下载失败"):
            update_stock_history("600519",root=tmp_path,retries=1,sleep_seconds=0)
    assert history_path("600519",tmp_path).read_bytes() == prior


def test_new_symbol_ingested(tmp_path):
    with patch("data_engine.history_downloader.get_daily_history",return_value=bars()):
        info=update_stock_history("000001",root=tmp_path,retries=0)
    assert info["rows"]==2 and info["added_rows"]==2
    assert info["adjust"] == "none"


def test_akshare_adapter_blocks_unfinished_daily_bar():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    data = bars(("2026-10-14", "2026-10-15")).rename(columns={
        "date":"日期", "open":"开盘", "high":"最高",
        "low":"最低", "close":"收盘", "volume":"成交量",
        "amount":"成交额",
    })
    fake = SimpleNamespace(stock_zh_a_hist=lambda **kwargs: data)
    before = datetime(2026, 10, 15, 10, 15, tzinfo=ZoneInfo("Asia/Shanghai"))
    after = datetime(2026, 10, 15, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    with patch.dict(sys.modules, {"akshare":fake}):
        with patch("data_engine.akshare_adapter._china_now", return_value=before):
            morning = get_daily_history("600519", "20261001", "20261015")
        with patch("data_engine.akshare_adapter._china_now", return_value=after):
            evening = get_daily_history("600519", "20261001", "20261015")
    assert morning.date.dt.strftime("%Y-%m-%d").tolist() == ["2026-10-14"]
    assert evening.date.dt.strftime("%Y-%m-%d").tolist() == ["2026-10-14", "2026-10-15"]


def test_no_bars_preserves_previous_file(tmp_path):
    save_history("600519", bars(), tmp_path)
    path = history_path("600519", tmp_path)
    previous = path.read_bytes()
    empty = pd.DataFrame(columns=bars().columns)
    with patch("data_engine.history_downloader.get_daily_history", return_value=empty):
        result = update_stock_history("600519", root=tmp_path, retries=0)
    assert result["added_rows"] == 0 and result["updated_file"] is None
    assert path.read_bytes() == previous
