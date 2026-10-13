#!/usr/bin/env python3
"""Forward-observe published strategy signals using real, archived end-of-day snapshots.

Measures future observations, NOT a hindsight-selected universe backtest, nor guaranteed
trading-session returns. Only public market data. No private holdings, API keys, or trades.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

TARGETS = (1, 5, 10, 20)  # number of successful subsequent sampled close observations
MAX_RECORDS = 2500


def finite_price(value):
    try:
        x = float(value)
    except (ValueError, TypeError):
        return None
    return round(x, 5) if math.isfinite(x) and x > 0 else None


def market_session(snapshot):
    """Use consensus of already-downloaded completed daily candles, not wall-clock weekdays."""
    stamp = snapshot.get("generated_at")
    try:
        collection_date = datetime.fromisoformat(stamp).date().isoformat()
    except (TypeError, ValueError):
        return None, "missing/invalid generated_at"
    dates = [
        x.get("last_bar")
        for x in (snapshot.get("histories") or {}).values()
        if isinstance(x, dict) and x.get("last_bar")
    ]
    if len(dates) < 3:
        return None, "fewer than three audited latest completed daily bars"
    common, count = Counter(dates).most_common(1)[0]
    if count / len(dates) < 0.8:
        return None, "latest daily-bar dates disagree across candidates"
    if common != collection_date:
        return None, "snapshot not aligned with completed trading-session date"
    try:
        date.fromisoformat(common)
    except ValueError:
        return None, "invalid daily-bar date"
    return common, None


def universe(snapshot):
    out = {}
    for entry in snapshot.get("stocks", []):
        code = str(entry.get("code", ""))
        if not (len(code) == 6 and code.isdecimal()):
            continue
        price = finite_price(entry.get("price"))
        # Treat a suspended stock or zero-turnover quote as unavailable for a new observation.
        amount = finite_price(entry.get("amount"))
        if price is not None and amount is not None:
            out[code] = {
                "close_proxy": price, "amount": amount,
                "name": str(entry.get("name", ""))[:100],
            }
    return out


def new_signals(snapshot, quotes, day):
    collected = {}
    signal_rows = []
    for index, record in enumerate(snapshot.get("candidates", [])[:10], 1):
        signal_rows.append(("custom", index, record))
    alpha = snapshot.get("alphasift") or {}
    if alpha.get("status") == "ok":
        for index, record in enumerate(alpha.get("picks", [])[:10], 1):
            signal_rows.append(("alphasift", index, record))
    for engine, rank, row in signal_rows:
        code = str(row.get("code", "")).strip()
        quote = quotes.get(code)
        if not quote:
            continue
        if engine == "custom":
            hist = (snapshot.get("histories") or {}).get(code) or {}
            if hist.get("last_bar") != day:
                continue
            hist_bars = hist.get("bars") or []
            actual_close = finite_price(hist_bars[-1].get("close")) if hist_bars else None
            if actual_close is None or abs(quote["close_proxy"] / actual_close - 1) > 0.015:
                continue  # stale/inconsistent price: never register a suspect signal
            label = str(row.get("signal", "unknown"))[:160]
        else:
            label = str(alpha.get("strategy", "unknown"))[:160]
            own_price = finite_price(row.get("price"))
            if own_price is not None and abs(own_price / quote["close_proxy"] - 1) > 0.05:
                continue
        key = f"{day}|{engine}|{code}|{label}"
        collected[key] = {
            "id": key, "start_date": day, "code": code, "name": quote["name"],
            "engine": engine, "strategy": label, "rank": rank,
            "initial_price": quote["close_proxy"],
            "reference_price_kind": "AKShare post-close market snapshot; not executable fill",
            "observations": [{"date": day, "price": quote["close_proxy"]}],
            "checkpoints": {},
            "missing_observations": 0,
        }
    return collected


def evolve(snapshot, original=None):
    old = original if isinstance(original, dict) else {}
    if old.get("schema") not in (None, 1):
        raise ValueError("Unsupported signal ledger schema")
    # Copy through JSON to avoid in-place mutations of callers' data.
    existing = json.loads(json.dumps(old.get("records") or [], ensure_ascii=False))
    result = {"schema": 1, "records": existing}
    day, issue = market_session(snapshot)
    if day is None:
        result["updated_at"] = old.get("updated_at")
        return result, {
            "status": "skipped", "reason": issue,
            "tracked_total": len(existing),
            "note": "Non-trading or unverified session; no forward-return data recorded",
        }
    quotes = universe(snapshot)
    if len(quotes) < 1000:
        result["updated_at"] = old.get("updated_at")
        return result, {"status": "skipped", "reason": "insufficient liquid-stock snapshot coverage",
                        "tracked_total": len(existing)}
    index = {record.get("id") for record in existing}
    # Save next-session prices for records that predate the completed day.
    for rec in existing:
        if rec.get("start_date", "") >= day:
            continue
        observations = rec.get("observations") or []
        if observations and observations[-1].get("date", "") >= day:
            continue
        stock = quotes.get(rec.get("code"))
        if not stock:
            rec["missing_observations"] = int(rec.get("missing_observations", 0)) + 1
            continue
        value = stock["close_proxy"]
        if finite_price(value) is None or finite_price(rec.get("initial_price")) is None:
            rec["missing_observations"] = int(rec.get("missing_observations", 0)) + 1
            continue
        observations.append({"date": day, "price": value})
        rec["observations"] = observations
        k = len(observations) - 1
        if k in TARGETS and str(k) not in rec.setdefault("checkpoints", {}):
            ret = round((value / rec["initial_price"] - 1) * 100, 4)
            rec["checkpoints"][str(k)] = {
                "sample_end_date": day,
                "sampled_price_change_pct": ret,
                "units": "successful future daily snapshots; NOT necessarily trading days",
            }
    added = 0
    for key, record in new_signals(snapshot, quotes, day).items():
        if key not in index:
            existing.append(record)
            added += 1
    existing.sort(key=lambda r: (r.get("start_date", ""), r.get("id", "")))
    dropped = max(0, len(existing) - MAX_RECORDS)
    if dropped:
        existing = existing[dropped:]
    result["records"] = existing
    result["updated_at"] = snapshot.get("generated_at")
    summary = {
        "status": "ok", "market_session": day,
        "tracked_total": len(existing), "added_today": added,
        "oldest_retained": existing[0].get("start_date") if existing else None,
        "truncated_old_records": dropped,
        "units": "N subsequent successfully observed EOD snapshots (not calendar/trading days)",
        "limitations": [
            "Observed unadjusted price changes are not actual executable returns",
            "No dividends, splits, fees, slippage, trading halts, delistings, or missed snapshots adjusted",
            "Cannot infer strategy advantage until enough forward observations accumulate",
            "AlphaSift and custom strategy signals are separately identified",
        ],
        "horizons": {},
    }
    for n in TARGETS:
        vals = [float(rec["checkpoints"][str(n)]["sampled_price_change_pct"])
                for rec in existing if str(n) in (rec.get("checkpoints") or {})]
        summary["horizons"][str(n)] = {
            "matured_signals": len(vals),
            "mean_sampled_change_pct": round(sum(vals) / len(vals), 4) if vals else None,
            "positive_ratio_pct": round(sum(v > 0 for v in vals) / len(vals) * 100, 2) if vals else None,
        }
    return result, summary


def atomic_write(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ledger_", suffix=".json", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", required=True)
    parser.add_argument("--previous")
    parser.add_argument("--ledger-out", required=True)
    args = parser.parse_args()
    p = Path(args.market)
    market = json.loads(p.read_text(encoding="utf-8"))
    if market.get("status") != "ok" or not market.get("stocks"):
        raise RuntimeError("Missing verified market snapshot; refuse to publish signal tracking")
    previous = None
    if args.previous and Path(args.previous).exists():
        previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    updated, summary = evolve(market, previous)
    market["signal_tracking"] = summary
    atomic_write(args.ledger_out, updated)
    atomic_write(p, market)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
