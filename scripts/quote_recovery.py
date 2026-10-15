"""Resilient public A-share spot quotes with strict validation and provenance."""
from __future__ import annotations

import time
import queue
import threading
import pandas as pd

MIN_VALID_QUOTES = 1200
MUST = {"代码", "名称", "最新价", "成交额"}


def normalize_candidate(frame, provider):
    if not isinstance(frame, pd.DataFrame) or not MUST.issubset(frame.columns):
        raise ValueError(f"{provider}: unsupported quote schema")
    raw = frame.copy()
    if provider == "AKShare / 新浪":
        raw["成交量"] = pd.to_numeric(raw.get("成交量"), errors="coerce") / 100.0
    codes = (raw["代码"].astype(str).str.strip()
             .str.replace(r"^(?:sh|sz|bj)", "", regex=True, case=False)
             .str.replace(r"\.0$", "", regex=True).str.zfill(6))
    raw["代码"] = codes
    prices = pd.to_numeric(raw["最新价"], errors="coerce")
    turnover = pd.to_numeric(raw["成交额"], errors="coerce")
    good_codes = codes.str.fullmatch(r"\d{6}")
    eligible = good_codes & prices.gt(0) & turnover.ge(0)
    if eligible.sum() < MIN_VALID_QUOTES:
        raise ValueError(
            f"{provider}: only {int(eligible.sum())} valid snapshots "
            f"(6digit={int(good_codes.sum())}, price>0={int(prices.gt(0).sum())},"
            f" amount>=0={int(turnover.ge(0).sum())}); "
            f"first_raw_code={str(frame['代码'].iloc[0])[:30] if len(frame) else 'empty'}"
        )
    return raw


def bounded_call(fn, timeout_seconds=28):
    """AKShare spot endpoints sometimes hang without a socket timeout.

    A daemon thread is bounded from the caller's perspective. No data are
    returned if the source did not complete before the deadline.
    """
    mailbox = queue.Queue(maxsize=1)

    def work():
        try:
            mailbox.put((True, fn()))
        except Exception as exc:
            mailbox.put((False, exc))

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    try:
        success, payload = mailbox.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError(f"行情源超时（超过{timeout_seconds}秒）") from exc
    if not success:
        raise payload
    return payload


def fetch_quotes(sleep=time.sleep):
    import akshare as ak
    errors = []
    for provider, fn, attempts in [
        ("AKShare / 东方财富", ak.stock_zh_a_spot_em, 3),
        ("AKShare / 新浪", ak.stock_zh_a_spot, 2),
    ]:
        for attempt in range(attempts):
            try:
                return normalize_candidate(bounded_call(fn), provider), provider
            except Exception as exc:
                errors.append(
                    f"{provider}[{attempt+1}]: {type(exc).__name__}: {str(exc)[:160]}"
                )
                if attempt + 1 < attempts:
                    sleep(2**attempt)
    raise RuntimeError("所有实时行情数据源均不可用；拒绝以旧行情伪装成最新数据。 " + " | ".join(errors))
