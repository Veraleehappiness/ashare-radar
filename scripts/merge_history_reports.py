"""Combine 5 isolated historical-update shards into one audited report.

Missing reports and failures are visible; neither can be counted as success.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def combine(pool:dict,reports:list[dict]) -> dict:
    expected={r["code"] for r in pool["stocks"]}
    if len(expected)!=100:
        raise ValueError("Expected exactly 100 unique stocks")
    seen={}
    for report in reports:
        for item in report.get("items",[]):
            code=item.get("code")
            if code not in expected or code in seen:
                raise ValueError(f"Unexpected or duplicated shard result: {code}")
            seen[code]=item
    for missing in sorted(expected-set(seen)):
        seen[missing]={"code":missing,"status":"failed","error":"missing batch result"}
    successes=[r for r in seen.values() if r.get("status")=="ok"]
    return {
        "schema":1,"generated_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "source_snapshot_at":pool.get("source_snapshot_at"),
        "requested":100,"succeeded":len(successes),"failed":100-len(successes),
        "success_rate_pct":round(100*len(successes)/100,2),
        "new_bars":sum(r.get("added_rows",0) for r in successes),
        "latest_available_date":max((r.get("last_date","") for r in successes),default=None),
        "result":"PASS" if len(successes)==100 else "INCOMPLETE",
        "items":[seen[r["code"]] for r in pool["stocks"]],
        "scope":"仅这100只研究样本；失败股票与未完成历史数据单独列示",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pool",required=True)
    p.add_argument("--reports-dir",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    reports=[json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(args.reports_dir).glob("report-*.json"))]
    if len(reports)>5:
        raise ValueError("Expected at most five shards")
    pool=json.loads(Path(args.pool).read_text(encoding="utf-8"))
    combined=combine(pool,reports)
    Path(args.out).write_text(json.dumps(combined,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in combined.items() if k in ("requested","succeeded","failed","new_bars","result")},ensure_ascii=False))


if __name__=="__main__":
    main()
