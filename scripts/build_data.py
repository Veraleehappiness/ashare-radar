#!/usr/bin/env python3
"""A-share market-only research data builder. NO synthetic prices or private holdings."""
from __future__ import annotations
import argparse
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from strategy_rules import STRATEGIES, evaluate_rules

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
COLUMNS = {
    "代码": "code", "名称": "name", "最新价": "price",
    "涨跌幅": "change_pct", "成交量": "volume", "成交额": "amount",
    "量比": "volume_ratio", "市盈率-动态": "pe", "市净率": "pb",
    "行业": "industry"
}
BAR_COLUMNS = {
    "日期": "date", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low", "成交量": "volume"
}

def scalar(x):
    if x is None: return None
    try:
        if pd.isna(x): return None
    except (TypeError, ValueError):
        return None
    if hasattr(x, "item"): x = x.item()
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, (int, float, str, bool)): return x
    return str(x)

def snapshot():
    import akshare as ak
    raw = ak.stock_zh_a_spot_em()
    x = raw.rename(columns=COLUMNS).copy()
    mandatory = {"code", "name", "price", "amount"}
    if not mandatory.issubset(x):
        raise RuntimeError("行情接口缺少字段: " + str(mandatory - set(x)))
    for c in ("change_pct", "volume", "volume_ratio", "pe", "pb"):
        if c not in x: x[c] = float("nan")
        x[c] = pd.to_numeric(x[c], errors="coerce")
    if "industry" not in x: x["industry"] = "未知"
    x["code"] = x["code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    x["name"] = x["name"].astype(str)
    x["price"] = pd.to_numeric(x["price"], errors="coerce")
    x["amount"] = pd.to_numeric(x["amount"], errors="coerce")
    raw_count = len(x)
    x = x[x.code.str.fullmatch(r"\d{6}") & x.price.gt(0) & x.amount.ge(0)]
    dupes = int(x.code.duplicated().sum())
    x = x.drop_duplicates("code").reset_index(drop=True)
    if len(x) < 1200:
        raise RuntimeError(f"有效股票只有 {len(x)} 只，不满足全市场质量阈值；拒绝发布")
    x.attrs["raw_count"] = raw_count
    x.attrs["duplicates"] = dupes
    x.attrs["discarded"] = raw_count - len(x)
    return x

def completed_bars(code: str, now: datetime):
    import akshare as ak
    raw = ak.stock_zh_a_hist(
        symbol=code, period="daily", start_date="20230101",
        end_date=now.strftime("%Y%m%d"), adjust=""
    )
    x = raw.rename(columns=BAR_COLUMNS).copy()
    needed = {"date", "open", "high", "low", "close", "volume"}
    if not needed.issubset(x):
        raise RuntimeError("历史日线必要字段缺失")
    x["date"] = pd.to_datetime(x.date, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.dropna(subset=list(needed))
    x = x[(x[["open", "high", "low", "close"]] > 0).all(axis=1) & x.volume.ge(0)]
    x = x[x.high.ge(x[["open", "low", "close"]].max(axis=1)) &
          x.low.le(x[["open", "high", "close"]].min(axis=1))]
    if now.hour < 15 or (now.hour == 15 and now.minute < 15):
        x = x[x.date.dt.date < now.date()]
    x = x.drop_duplicates("date").sort_values("date")
    if len(x) < 125: raise RuntimeError("不足125根有效、已完成日K线")
    age = (now.date() - x.date.iloc[-1].date()).days
    if age > 5: raise RuntimeError("日线数据超过5个自然日未更新")
    return x

def strategy(x):
    close = x.close.astype(float); vol = x.volume.astype(float)
    price = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean()); ma60 = float(close.tail(60).mean())
    vol_prev = float(vol.iloc[-21:-1].mean())
    ratio = float(vol.iloc[-1] / vol_prev) if vol_prev > 0 else 0
    high120 = float(close.iloc[-121:-1].max())
    low40 = float(close.tail(40).min())
    prev_high60 = float(close.iloc[-61:-1].max())
    drawdown = (high120 - low40) / high120 if high120 else 0
    rising = price > float(close.iloc[-2])
    rev = drawdown >= .20 and price >= ma20 and rising and ratio >= 1.2 and price <= high120 * .9
    brk = price > prev_high60 and ratio >= 1.6 and price >= ma20
    rep = price >= ma20 > ma60 and rising and ratio >= 1.1
    labels = ([ "底部反转" ] if rev else []) + (["放量突破"] if brk else []) + (["趋势修复"] if rep else [])
    reasons = []
    if rev: reasons.append("近120日高点至近40日低点回撤≥20%，站上MA20且放量")
    if brk: reasons.append("收盘突破此前60日收盘高点且量能≥1.6倍")
    if rep: reasons.append("MA20高于MA60，价格站上MA20且温和放量")
    score = min(100, max(0, min(30, (price / ma20 - 1)*300)) +
                max(0, min(30, (ratio - .8)*20)) +
                (20 if price > ma60 else 0) + (20 if rev or brk else 5 if rep else 0))
    return {
        "signal": "、".join(labels) if labels else "未触发",
        "score": round(score, 1), "reasons": reasons,
        "risk": "高" if price / ma20 > 1.18 or ratio > 5 else "一般",
        "ma20": round(ma20, 3), "ma60": round(ma60, 3),
        "volume_ratio_20d": round(ratio, 2),
        "history_last_date": x.date.iloc[-1].strftime("%Y-%m-%d")
    }

def build(out: Path, max_history: int):
    now = datetime.now(TZ)
    market = snapshot()
    stocks = []
    for row in market.to_dict("records"):
        stocks.append({k: scalar(row.get(k)) for k in
                       ("code", "name", "price", "change_pct", "volume",
                        "amount", "volume_ratio", "pe", "pb", "industry")})
    pool = market[(market.price >= 3) & (market.amount >= 20_000_000) &
                  market.change_pct.between(-4, 9.5)].copy()
    pool = pool[~pool.name.str.contains(r"ST|退", case=False, regex=True, na=False)]
    pool["rank_value"] = (pool.volume_ratio.fillna(0).clip(0, 5)*10 +
                          pool.change_pct.clip(lower=0)*2 +
                          (pool.amount/1e8).clip(0, 20))
    pool = pool.sort_values("rank_value", ascending=False).head(max_history)
    candidates, histories, warnings = [], {}, []
    library_signals, library_evaluated = [], 0
    audited = 0
    for item in pool.to_dict("records"):
        code = str(item["code"])
        try:
            x = completed_bars(code, now)
            audited += 1
            signal = strategy(x)
            histories[code] = {
                "code": code, "name": str(item["name"]),
                "last_bar": signal["history_last_date"],
                "adjust": "none", "source": "AKShare",
                "bars": [{"date": r.date.strftime("%Y-%m-%d"), "close": float(r.close),
                          "open": float(r.open), "high": float(r.high),
                          "low": float(r.low), "volume": float(r.volume)}
                         for r in x.tail(170).itertuples(index=False)]
            }
            try:
                library_signals.extend(evaluate_rules(x, code, str(item["name"])))
                library_evaluated += 1
            except Exception as strategy_error:
                warnings.append(f"{code} strategy catalog: {str(strategy_error)[:130]}")
            if signal["signal"] != "未触发":
                candidates.append({
                    "code": code, "name": str(item["name"]),
                    "price": scalar(item["price"]), "change_pct": scalar(item["change_pct"]),
                    **signal
                })
        except Exception as e:
            warnings.append(f"{code}: {str(e)[:180]}")
    if audited == 0:
        raise RuntimeError("候选股票历史日线全部获取失败；不发布只有行情快照的假完整报告")
    candidates.sort(key=lambda it: it["score"], reverse=True)
    sectors = []
    if "industry" in market:
        grouped = market.dropna(subset=["industry"]).groupby("industry")
        for name, part in grouped:
            if str(name) in ("未知", "", "nan") or len(part) < 3: continue
            sectors.append({"name": str(name),
                "change_pct": round(float(part.change_pct.mean()), 3),
                "count": int(len(part)), "amount": float(part.amount.sum())})
    sectors.sort(key=lambda x: x["change_pct"], reverse=True)
    payload = {
        "schema": 2, "status": "ok", "generated_at": now.isoformat(),
        "quote_collected_at": now.isoformat(),
        "quote_provider": "AKShare / 东方财富公开行情接口",
        "quote_kind": "采集时的网页行情快照，非交易所实时直连",
        "history_kind": "不复权、完整日K线",
        "coverage": {"market_count": int(len(stocks)),
                     "prescreen_count": int(len(pool)),
                     "history_attempted": int(len(pool)),
                     "history_succeeded": int(audited),
                     "signal_count": int(min(20, len(candidates))),
                     "scope": "全市场快照初筛 + 有限候选日线检查；并非全市场逐股历史回测"},
        "quality": {"rows": int(len(stocks)), "raw_rows": market.attrs.get("raw_count"),
                    "discarded_rows": market.attrs.get("discarded"),
                    "duplicate_codes": market.attrs.get("duplicates"),
                    "valid_price_ratio": 100.0},
        "stocks": stocks, "candidates": candidates[:20],
        "histories": histories, "sectors": sectors[:16],
        "backtests": {}, "warnings": warnings[:90],
        "strategy_library": {
            "status": "research_only",
            "version": "1.0",
            "rules": STRATEGIES,
            "evaluated_stocks": library_evaluated,
            "signal_count": len(library_signals),
            "signals": library_signals[:160],
            "scope": "仅初筛候选的历史K线，不是全市场扫描；信号是研究假设，未验证盈利",
            "execution": "今日收盘后才知道的规则触发，最早次日按实际可成交价模拟",
        },
        "source_projects": ["akfamily/akshare"]
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".market_", suffix=".json", dir=out.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    print(json.dumps({"status": "ok", "coverage": payload["coverage"],
                      "warnings": len(warnings)}, ensure_ascii=False))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--max-history", type=int, default=30)
    p.add_argument("--out", default="market.json")
    a = p.parse_args()
    if not 1 <= a.max_history <= 120: p.error("max-history must be 1..120")
    build(Path(a.out), a.max_history)
