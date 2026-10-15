"""Resilience and 100-stock strategy bridge unit tests (synthetic fixtures only)."""
from __future__ import annotations
from collections import Counter
from datetime import date, timedelta
from unittest.mock import patch
from pathlib import Path

import pandas as pd
import pytest
from scripts.quote_recovery import fetch_quotes
from scripts.stock_pool_100 import QUOTAS, choose_pool, board_of
from scripts.scan_historical_100 import scan
from scripts.strategy_rules import STRATEGIES


def fake_spot(board, count, seq):
    prefix={"SH_MAIN":"600", "SZ_MAIN":"000", "GEM":"300", "STAR":"688","BSE":"800"}[board]
    rows=[]
    for i in range(count):
        code=f"{prefix}{i:03d}"
        rows.append({"code":code,"name":f"Sample{i}","price":10,
                     "amount":100000000-i*50,"industry":f"Sector {i%13}"})
    return rows


def test_fixed_pool_size_composition_diversity():
    source=[]
    for index,board in enumerate(QUOTAS):
        source.extend(fake_spot(board, QUOTAS[board]+5, index))
    result=choose_pool({"stocks":source,"generated_at":"2026-10-13T17:00:00+08:00"})
    assert result["pool_size"]==100
    assert result["source_snapshot_at"]=="2026-10-13T17:00:00+08:00"
    assert Counter(s["board"] for s in result["stocks"])==QUOTAS
    assert len({s["code"] for s in result["stocks"]})==100
    assert result["stocks"]==choose_pool({"stocks":source})["stocks"]


def test_snapshot_retry_and_sina_volume_in_lots():
    east={"tries":0}
    def bad_em():
        east["tries"]+=1
        raise ConnectionError("Eastmoney remote disconnect")
    rows=pd.DataFrame({"代码":[f"{i:06d}" for i in range(1500)],
                       "名称":["Synthetic"]*1500,
                       "最新价":[10.0]*1500,
                       "成交量":[10000]*1500,
                       "成交额":[5000000]*1500})
    class FakeAK:
        stock_zh_a_spot_em=staticmethod(bad_em)
        stock_zh_a_spot=staticmethod(lambda: rows)
    import sys
    with patch.dict(sys.modules,{"akshare":FakeAK}):
        frame, provider=fetch_quotes(sleep=lambda _:None)
    assert east["tries"]==3
    assert provider=="AKShare / 新浪"
    assert frame.iloc[0]["成交量"]==100  # 10,000 shares become 100 lots
    rows["代码"] = ["sh"+f"{i:06d}" for i in range(1500)]
    with patch.dict(sys.modules,{"akshare":FakeAK}):
        prefixed, source=fetch_quotes(sleep=lambda _:None)
    assert source=="AKShare / 新浪"
    assert prefixed.iloc[0]["代码"]=="000000"



def test_all_quote_sources_down_not_silent_success():
    class Unavailable:
        @staticmethod
        def stock_zh_a_spot_em():
            raise ConnectionError("offline")
        stock_zh_a_spot=stock_zh_a_spot_em
    import sys
    with patch.dict(sys.modules,{"akshare":Unavailable}):
        with pytest.raises(RuntimeError,match="所有实时行情数据源均不可用"):
            fetch_quotes(sleep=lambda _:None)


def test_all_four_strategies_present_in_real_store_scanner(tmp_path):
    active=[s for s in STRATEGIES if s["state"]=="experimental"]
    assert len(active)==4
    pool={"source_snapshot_at":"2026-10-13","stocks":[
        {"code":f"{x:06d}","name":f"Symbol{x}"} for x in range(100)]}
    fake_frame=pd.DataFrame({
        "date":pd.to_datetime([date.today()-timedelta(days=(160-i)) for i in range(160)]),
        "open":[10.0]*160,
        "high":[12.0]*160,
        "low":[9.0]*160,
        "close":[11.0]*160,
        "volume":[1000.0]*160,
        "amount":[100000]*160
    })
    class Provider:
        def __init__(self,root):
            pass
        def get_history(self,code,days):
            return fake_frame.copy()
    with patch("scripts.scan_historical_100.HistoryProvider",Provider):
        report=scan(pool,tmp_path,{"generated_at":"2026-10-13"},max_age_days=10)
    assert report["evaluated"]==100
    assert report["attempted"]==100
    assert set(report["signal_count_by_strategy"])=={s["id"] for s in active}
    assert report["status"]=="complete"
