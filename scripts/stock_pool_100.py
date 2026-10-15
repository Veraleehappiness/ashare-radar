"""Select ONE stable and auditable 100-stock A-share pilot from a public snapshot.

Do NOT silently sample 100 at random each run. This selection freezes an index
from the last confirmed market.json snapshot, stores its provenance and keeps
the same symbols for all subsequent incremental updates.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

QUOTAS = {"SH_MAIN":35,"SZ_MAIN":30,"GEM":20,"STAR":12,"BSE":3}


def board_of(code: str) -> str | None:
    if code.startswith(("688","689")):
        return "STAR"
    if code.startswith(("600","601","603","605")):
        return "SH_MAIN"
    if code.startswith(("000","001","002","003")):
        return "SZ_MAIN"
    if code.startswith(("300","301")):
        return "GEM"
    if code.startswith(("8","4","92")):
        return "BSE"
    return None


def choose_pool(snapshot: dict) -> dict:
    records = snapshot.get("stocks", [])
    unique = set()
    buckets = {key: [] for key in QUOTAS}
    for item in records:
        code = str(item.get("code",""))
        label = str(item.get("name",""))
        board = board_of(code)
        if (len(code)!=6 or not code.isdigit() or not board or code in unique
                or not label or "ST" in label.upper() or "退" in label):
            continue
        try:
            value = float(item.get("amount") or 0)
            price = float(item.get("price") or 0)
        except (ValueError,TypeError):
            continue
        if value <= 0 or price <= 0:
            continue
        unique.add(code)
        buckets[board].append({
            "code":code, "name":label[:60], "board":board,
            "industry":str(item.get("industry") or "unknown")[:80],
            "selected_reason":"liquid_industry_diversified_pilot",
            "_liquidity":value,
        })
    selected = []
    for board, needed in QUOTAS.items():
        ordered = sorted(buckets[board],key=lambda s:(-s["_liquidity"],s["code"]))
        if len(ordered) < needed:
            raise ValueError(f"{board}: available {len(ordered)} < quota {needed}")
        groups = {}
        chosen=[]
        # First pass: diversify up to five symbols per industry.
        for stock in ordered:
            sector=stock["industry"]
            if groups.get(sector,0) >= 5:
                continue
            chosen.append(stock)
            groups[sector]=groups.get(sector,0)+1
            if len(chosen)==needed:
                break
        # Second pass: fill shortages with next liquid symbols.
        if len(chosen)<needed:
            occupied={s["code"] for s in chosen}
            for stock in ordered:
                if stock["code"] not in occupied:
                    chosen.append(stock)
                    occupied.add(stock["code"])
                if len(chosen)==needed:
                    break
        for stock in chosen:
            stock.pop("_liquidity",None)
        selected.extend(chosen)
    assert len(selected)==100 and len({x["code"] for x in selected})==100
    return {
        "schema":1, "pool_size":100, "quotas":QUOTAS,
        "source_snapshot_at":snapshot.get("generated_at"),
        "built_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "selection":"fixed 100 from verified public market snapshot; not whole-market survivorship-complete",
        "stocks":selected,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--market",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    pool=choose_pool(json.loads(Path(args.market).read_text(encoding="utf-8")))
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(pool,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Frozen 100-stock pool:",pool["quotas"],"snapshot",pool["source_snapshot_at"])


if __name__=="__main__":
    main()
