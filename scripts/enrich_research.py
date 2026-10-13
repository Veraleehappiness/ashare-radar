#!/usr/bin/env python3
"""Optional, attributable AlphaSift + AKQuant enrichment of the public market JSON.

IMPORTANT: these are research studies, NOT all-market predictive backtests.
Runs in isolated subprocesses. Never fabricates prices/metrics on failures.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
EXPERIMENTS = [("000725", "京东方A"), ("000100", "TCL科技")]


def safe_number(value):
    try:
        result = float(value)
        return round(result, 5) if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def attr(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def run_alphasift():
    from alphasift import screen
    result = screen("dual_low", market="cn", use_llm=False)
    picks = []
    for p in list(attr(result, "picks", []) or [])[:20]:
        code = str(attr(p, "code", "")).strip().zfill(6)
        if not (len(code) == 6 and code.isdigit()):
            continue
        picks.append({
            "code": code,
            "name": str(attr(p, "name", "")),
            "rank": len(picks) + 1,
            "final_score": safe_number(attr(p, "final_score")),
            "screen_score": safe_number(attr(p, "screen_score")),
            "price": safe_number(attr(p, "price")),
            "ranking_reason": str(attr(p, "ranking_reason", ""))[:500],
            "risk_summary": str(attr(p, "risk_summary", ""))[:500],
        })
    return {
        "status": "ok",
        "engine": "ZhuLinsen/alphasift",
        "strategy": "dual_low",
        "llm_used": False,
        "selection_count": len(picks),
        "snapshot_count": attr(result, "snapshot_count"),
        "after_filter_count": attr(result, "after_filter_count"),
        "strategy_version": str(attr(result, "strategy_version", "")),
        "snapshot_source": str(attr(result, "snapshot_source", ""))[:300],
        "degradation": str(attr(result, "degradation", ""))[:600],
        "picks": picks,
        "note": "AlphaSift 独立筛选结果，可能使用自身缓存/降级数据；与 AKShare 快照不同源，不能直接当成实时交易信号。",
    }


def daily_frame(symbol):
    import akshare as ak
    import pandas as pd
    now = datetime.now(TZ)
    year = now.year - 5
    start = f"{year}{now.month:02d}{now.day:02d}"
    df = ak.stock_zh_a_hist(
        symbol=symbol, period="daily", start_date=start,
        end_date=now.strftime("%Y%m%d"), adjust=""
    )
    df = df.rename(columns={
        "日期": "date", "开盘": "open", "最高": "high",
        "最低": "low", "收盘": "close", "成交量": "volume",
    })
    cols = ["date", "open", "high", "low", "close", "volume"]
    if not set(cols).issubset(df.columns):
        raise ValueError("K线必要字段缺失")
    df = df[cols].copy()
    df["date"] = pd.to_datetime(df.date, errors="coerce")
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=cols).drop_duplicates("date").sort_values("date")
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & df.volume.ge(0)]
    # Never backtest an unfinished current-session daily candle.
    if now.hour < 15 or (now.hour == 15 and now.minute < 15):
        df = df[df.date.dt.date < now.date()]
    if len(df) < 260:
        raise ValueError(f"有效完整日线仅 {len(df)} 根")
    if (now.date() - df.date.iloc[-1].date()).days > 5:
        raise ValueError("日线数据过期")
    df["symbol"] = symbol
    return df


def run_akquant():
    import pandas as pd
    from akquant import Strategy, NextOpen, run_backtest

    class MovingAverageResearch(Strategy):
        def on_bar(self, bar):
            history = self.get_history(60, bar.symbol, "close")
            if len(history) < 60:
                return
            ma20 = float(sum(history[-20:]) / 20)
            ma60 = float(sum(history[-60:]) / 60)
            position = self.get_position(bar.symbol)
            if position == 0 and bar.close > ma20 > ma60:
                self.buy(bar.symbol, 100)
            elif position > 0 and bar.close < ma20:
                self.close_position(bar.symbol)

    experiments = {}
    errors = []
    for code, name in EXPERIMENTS:
        try:
            frame = daily_frame(code)
            result = run_backtest(
                data=frame,
                strategy=MovingAverageResearch,
                symbols=code,
                initial_cash=100000.0,
                commission_rate=0.0003,
                stamp_tax_rate=0.0005,
                transfer_fee_rate=0.00001,
                min_commission=5.0,
                lot_size=100,
                t_plus_one=True,
                fill_policy=NextOpen(),
                show_progress=False,
            )
            m = result.metrics
            curve = result.equity_curve_daily
            if isinstance(curve, pd.DataFrame):
                # Column names vary across AKQuant versions.
                if "equity" in curve.columns:
                    series = curve["equity"]
                elif "total_value" in curve.columns:
                    series = curve["total_value"]
                else:
                    numeric = curve.select_dtypes(include="number")
                    if numeric.empty:
                        raise ValueError("权益曲线没有数值列")
                    series = numeric.iloc[:, -1]
            elif isinstance(curve, pd.Series):
                series = curve
            else:
                raise ValueError("AKQuant 权益曲线类型未知")
            points = []
            for date, equity in series.items():
                v = safe_number(equity)
                if v is not None:
                    points.append({"date": str(pd.Timestamp(date).date()), "equity": v})
            if len(points) < 60:
                raise ValueError("有效权益曲线少于60天")
            trades = result.trades_df
            metrics = {
                "total_return_pct": safe_number(m.total_return_pct),
                "max_drawdown_pct": safe_number(m.max_drawdown_pct),
                "sharpe": safe_number(m.sharpe_ratio),
                "trade_count": int(len(trades)) if isinstance(trades, pd.DataFrame) else 0,
                "days": len(points),
            }
            if metrics["total_return_pct"] is None or metrics["max_drawdown_pct"] is None:
                raise ValueError("关键绩效指标缺失")
            experiments[code] = {
                "engine": "AKQuant",
                "symbol": code, "name": name,
                "strategy": "MA20 / MA60 trend (research)",
                "last_bar": frame.date.iloc[-1].strftime("%Y-%m-%d"),
                "sample_start": frame.date.iloc[0].strftime("%Y-%m-%d"),
                "sample_end": frame.date.iloc[-1].strftime("%Y-%m-%d"),
                "scope": "预先指定的2只样本股票，非全市场历史选股回测",
                "data_adjust": "不复权",
                "trade_execution": "次日开盘撮合；T+1；100股整手",
                "metrics": metrics,
                "curve": points[::max(1, len(points)//200)][:240],
                "note": "AKQuant 的真实策略回测演示；不含历史退市股、复权影响、完整涨跌停成交审计；滑点功能版本差异需单独复核，非实盘盈利证明。",
            }
        except Exception as exc:
            errors.append(f"{code}: {type(exc).__name__}: {str(exc)[:220]}")
    return {"status": "ok" if experiments else "failed", "engine": "akfamily/akquant",
            "samples": experiments, "errors": errors, "requested": [c for c, _ in EXPERIMENTS]}


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".research_", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def worker(kind, path):
    try:
        payload = run_alphasift() if kind == "alphasift" else run_akquant()
        atomic_json(path, payload)
    except Exception as exc:
        atomic_json(path, {"status": "failed", "engine": kind,
                           "error": f"{type(exc).__name__}: {str(exc)[:350]}"})


def subprocess_research(kind, timeout):
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "result.json"
        try:
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker", kind, "--output", str(output)],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
            if not output.exists():
                return {"status": "failed", "engine": kind,
                        "error": f"no worker output (exit={completed.returncode}): {completed.stderr[-300:]}"}
            result = json.loads(output.read_text(encoding="utf-8"))
            return result
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "engine": kind, "error": f"超过 {timeout} 秒"}


def enrich(path, run_alpha=True, run_backtests=True):
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    if payload.get("status") != "ok" or not payload.get("stocks"):
        raise ValueError("未获得有效真实市场数据，拒绝研究增强")
    payload["research_updated_at"] = datetime.now(TZ).isoformat()
    if run_alpha:
        payload["alphasift"] = subprocess_research("alphasift", timeout=210)
    if run_backtests:
        payload["research_backtests"] = subprocess_research("akquant", timeout=240)
        sample = payload["research_backtests"].get("samples", {})
        if sample:
            payload["backtests"] = sample  # Matches existing V0.3 website reader.
    atomic_json(p, payload)
    print(json.dumps({"alphasift": payload.get("alphasift", {}).get("status"),
                      "akquant": payload.get("research_backtests", {}).get("status"),
                      "backtested": len(payload.get("backtests", {}))}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="market.json")
    parser.add_argument("--worker", choices=("alphasift", "akquant"))
    parser.add_argument("--output")
    parser.add_argument("--skip-alpha", action="store_true")
    parser.add_argument("--skip-akquant", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if not args.output:
            parser.error("--worker requires --output")
        worker(args.worker, args.output)
    else:
        enrich(args.input, not args.skip_alpha, not args.skip_akquant)
