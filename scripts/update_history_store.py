#!/usr/bin/env python3
"""Update real A-share daily parquet files and write audit report.

Examples:
  python -m scripts.update_history_store --codes 600519,000001 --start 20240101
  python -m scripts.update_history_store --pool tests/data/stock_pool_100.json --limit 5
No synthetic quotes, no broker orders. Returns nonzero if any requested stock fails.
"""
from __future__ import annotations
import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import monotonic
from zoneinfo import ZoneInfo

from data_engine.history_downloader import update_stock_history
from data_engine.validator import validate_code


def parse_codes(raw: str | None, pool: str | None):
    codes = []
    if raw:
        codes.extend(item.strip() for item in raw.replace(" ", ",").split(",") if item.strip())
    if pool:
        source = json.loads(Path(pool).read_text(encoding="utf-8"))
        rows = source.get("stocks") if isinstance(source, dict) else source
        if not isinstance(rows, list):
            raise ValueError("股票池必须是股票数组或含 stocks 数组的 JSON")
        codes.extend(str(item["code"] if isinstance(item, dict) else item) for item in rows)
    seen = set()
    unique = []
    for value in codes:
        code = validate_code(value)
        if code not in seen:
            unique.append(code)
            seen.add(code)
    if not unique:
        raise ValueError("请提供 --codes 或 --pool；拒绝无股票的空任务")
    return unique


def write_atomic(path: str | Path, result: dict):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".health-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as dest:
            json.dump(result, dest, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(codes: list[str], root: Path, start: str, report_path: Path, retries: int = 2):
    started = monotonic()
    results = []
    for index, code in enumerate(codes, 1):
        try:
            record = update_stock_history(
                code, start_date=start, root=root, retries=retries,
                sleep_seconds=1.0,
            )
            results.append(record)
            print(f"[{index}/{len(codes)}] {code} OK rows={record['rows']} new={record['added_rows']}", flush=True)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {str(exc)[:240]}"
            results.append({"code": code, "status": "failed", "error": reason})
            print(f"[{index}/{len(codes)}] {code} FAILED: {reason}", flush=True)
    ok = [r for r in results if r["status"] == "ok"]
    report = {
        "version": "V0.7.1-D",
        "data_kind": "unadjusted daily A-share OHLCV; third-party historical API",
        "provider": "AKShare / stock_zh_a_hist",
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "requested": len(codes),
        "succeeded": len(ok),
        "failed": len(codes) - len(ok),
        "success_rate_pct": round(100*len(ok)/len(codes), 2),
        "new_bars": sum(r["added_rows"] for r in ok),
        "duration_seconds": round(monotonic() - started, 2),
        "first_available_date": min((r["first_date"] for r in ok), default=None),
        "latest_available_date": max((r["last_date"] for r in ok), default=None),
        "result": "PASS" if len(ok)==len(codes) else "INCOMPLETE",
        "items": results,
    }
    write_atomic(report_path, report)
    print(json.dumps({k:v for k,v in report.items() if k!="items"},ensure_ascii=False,indent=2))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codes", default="")
    p.add_argument("--pool")
    p.add_argument("--limit",type=int,default=10)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--start",default="20240101")
    p.add_argument("--root",default="database/stocks")
    p.add_argument("--report",default="reports/history_health.json")
    p.add_argument("--retries",type=int,default=2)
    args=p.parse_args()
    if args.limit<1 or args.limit>100:
        p.error("--limit 必须在 1..100，规模扩大前先验收批处理")
    if args.offset < 0:
        p.error("--offset 不能为负")
    stocks=parse_codes(args.codes,args.pool)[args.offset:args.offset+args.limit]
    if not stocks:
        p.error("股票批次为空；拒绝发布空白历史数据报告")
    report=run(stocks,Path(args.root),args.start,Path(args.report),args.retries)
    raise SystemExit(0 if report["result"]=="PASS" else 1)


if __name__=="__main__":
    main()
