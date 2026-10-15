"""Scan the frozen 100-stock real Parquet pilot using the FOUR existing rules.

No synthetic prices, no broker orders, no fabricated profit statistics.
Only symbols with a sufficiently recent completed session enter today's scan.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

from data_engine.provider import HistoryProvider
from scripts.strategy_rules import STRATEGIES, evaluate_rules

FOUR = [s for s in STRATEGIES if s["state"]=="experimental"]


def scan(pool: dict, root: Path, report: dict, max_age_days: int = 5) -> dict:
    provider=HistoryProvider(root)
    attempted={str(row["code"]):row for row in pool["stocks"]}
    if len(attempted) != 100:
        raise ValueError("100股票池有重复或数量错误")
    health={str(r["code"]):r for r in report.get("items",[])}
    successful=[]
    failed=[]
    old=[]
    for code,meta in attempted.items():
        try:
            frame=provider.get_history(code,days=250)
            if len(frame)<130:
                old.append({"code":code,"reason":"less than 130 completed daily bars"})
                continue
            latest=frame.date.iloc[-1].date()
            if (date.today() - latest).days > max_age_days:
                old.append({"code":code,"reason":"older than scan freshness threshold","last_bar":latest.isoformat()})
                continue
            successful.append((code,meta,frame))
        except (FileNotFoundError,RuntimeError,ValueError) as exc:
            failed.append({"code":code,"error":str(exc)[:160]})
    signals=[]
    evaluated=0
    for code,meta,frame in successful:
        try:
            signals.extend(evaluate_rules(frame,code,meta.get("name",code)))
            evaluated += 1
        except Exception as exc:
            failed.append({"code":code,"error":"strategy: "+str(exc)[:150]})
    counts={s["id"]:0 for s in FOUR}
    for signal in signals:
        counts[signal["strategy_id"]]+=1
    # Unscanned and stale symbols are always visible. DO NOT claim all-market scan.
    return {
        "schema":1, "status":"complete" if evaluated == 100 else "partial",
        "generated_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "scope":"仅冻结的100只样本股票，非全市场；四套研究策略，非真实交易或收益保证",
        "pool_source_snapshot_at":pool.get("source_snapshot_at"),
        "history_refresh_generated_at":report.get("generated_at"),
        "attempted":100, "evaluated":evaluated,
        "stale_or_short":old, "missing_or_invalid":failed,
        "strategy_definitions":FOUR,
        "signal_count":len(signals),
        "signal_count_by_strategy":counts,
        "signals":signals[:300],
        "performance_evidence":"not tested — signals are hypotheses only",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pool",required=True)
    p.add_argument("--root",required=True)
    p.add_argument("--health",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    pool=json.loads(Path(args.pool).read_text(encoding="utf-8"))
    health=json.loads(Path(args.health).read_text(encoding="utf-8"))
    result=scan(pool,Path(args.root),health)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k in ("status","attempted","evaluated","signal_count","signal_count_by_strategy")},ensure_ascii=False))
    if result["evaluated"]==0:
        raise SystemExit("No stocks with usable, sufficiently fresh historical records")


if __name__=="__main__":
    main()
