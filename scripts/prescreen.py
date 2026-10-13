"""Deterministic, diversified snapshot-to-history candidate selector.

This improves on a gainers-only pool without claiming complete historical A-share
coverage. Prices are public close-time research data; no trading orders.
"""
from __future__ import annotations
import pandas as pd

REQUIRED = {"code", "name", "price", "amount", "change_pct", "volume_ratio"}

def select_history_pool(market: pd.DataFrame, limit: int = 60):
    if not REQUIRED.issubset(market.columns):
        raise ValueError("Missing required snapshot columns for preselection")
    if not 3 <= limit <= 120:
        raise ValueError("history limit outside safe interval 3..120")
    x = market.copy()
    for col in ("price", "amount", "change_pct", "volume_ratio"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x["code"] = x["code"].astype(str).str.zfill(6)
    x["name"] = x["name"].astype(str)
    valid = (x["code"].str.fullmatch(r"\d{6}")
             & x["price"].between(2.5, 1000)
             & x["amount"].ge(15_000_000)
             & x["change_pct"].between(-12, 20)
             & ~x["name"].str.contains(r"ST|退", case=False, regex=True, na=False))
    x = x.loc[valid].drop_duplicates("code").copy()
    if x.empty:
        raise RuntimeError("No liquid, valid research candidates in market snapshot")
    x["liquidity"] = (x["amount"] / 1e8).clip(0, 30)
    x["activity"] = x["volume_ratio"].fillna(0).clip(0, 6)
    # Snapshot changes measure *today*, not long-term bottom/strength.
    # Decliners are intentionally sampled to reduce survivorship of gainers-only prefilter.
    segments = (
        ("decliners", x[x.change_pct.between(-12, 0.5)]
         .sort_values(["liquidity", "code"], ascending=[False, True])),
        ("risers", x[x.change_pct.between(1, 20)]
         .assign(rank=lambda t: 2*t.activity + t.change_pct.clip(0, 10) + .2*t.liquidity)
         .sort_values(["rank", "code"], ascending=[False, True])),
        ("liquid_breadth", x.sort_values(["liquidity", "code"], ascending=[False, True])),
    )
    counts = {"decliners": 0, "risers": 0, "liquid_breadth": 0}
    seen = set()
    picks = []
    # Fair round-robin 1/3 quota; each segment avoids selected codes.
    quota = (limit + 2) // 3
    for name, segment in segments:
        for code in segment.code.tolist():
            if len(picks) >= limit or counts[name] >= quota:
                break
            if code in seen:
                continue
            picks.append(code);seen.add(code);counts[name] += 1
    # Fill remaining slots without reranking based on future candles.
    for code in segments[2][1].code.tolist():
        if len(picks) >= limit:
            break
        if code not in seen:
            picks.append(code);seen.add(code)
            counts["liquid_breadth"] += 1
    result = x.set_index("code").loc[picks].reset_index()
    result.attrs["selection"] = {
        "requested_limit": limit,
        "selected_count": len(picks),
        "eligible_snapshot_count": int(len(x)),
        "bucket_counts": counts,
        "description": "流动性、弱势样本与活跃上涨样本均衡抽样；仅决定历史K线下载顺序，不构成完整全市场技术扫描",
        "exclusions": "剔除 ST/退、明显无效价格、成交额<1500万元及极端单日涨跌样本",
    }
    return result
