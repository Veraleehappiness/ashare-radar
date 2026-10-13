"""Transparent, non-executing A-share research strategy catalog.

These are HYPOTHESES, not proven profitable strategies or buy recommendations.
The caller must supply completed, chronologically ordered daily bars.
All comparisons use data at or before the signal close; orders are NOT simulated here.
"""

from __future__ import annotations
import math

STRATEGIES = [
    {
        "id": "bottom_reversal_v1",
        "name": "底部反转",
        "state": "experimental",
        "horizon": "20-120个交易日（研究假设）",
        "entry": "过去120日高点至近40日低点回撤≥22%；近10日低点不创新低；重新站上MA20；当日量≥前20日均量1.2倍且收涨",
        "exit_hypothesis": "跌破MA20或触发另行回测的风险预算止损",
        "evidence": "均值回归/底部修复研究假设，尚未经本平台样本外验证",
        "required_data": "至少130根已完成日K线",
    },
    {
        "id": "volume_breakout_v1",
        "name": "趋势放量突破",
        "state": "experimental",
        "horizon": "20-80个交易日（研究假设）",
        "entry": "当日收盘高于此前60日收盘最高值；MA20>MA60；当日成交量≥前20日均量1.5倍",
        "exit_hypothesis": "跌破MA20或波动率止损；需模拟次日可成交价格",
        "evidence": "趋势/动量文献存在跨市场证据，但不能推论本A股参数组合可盈利",
        "required_data": "至少130根已完成日K线",
    },
    {
        "id": "trend_pullback_v1",
        "name": "趋势回踩修复",
        "state": "experimental",
        "horizon": "20-80个交易日（研究假设）",
        "entry": "MA20>MA60；前3日至少有一日回踩MA20附近；今日收盘重新站上MA20且收涨",
        "exit_hypothesis": "跌破MA60或失去上升趋势结构",
        "evidence": "顺势低换手的可检验规则，目前无已证实的净收益优势",
        "required_data": "至少130根已完成日K线",
    },
    {
        "id": "short_rebound_v1",
        "name": "短期超跌反弹",
        "state": "experimental",
        "horizon": "5-20个交易日（研究假设，需考虑T+1）",
        "entry": "截至昨日的前5日累计回撤为7%-14%；今日收涨至少1%；价格没有远低于MA120",
        "exit_hypothesis": "单独验证3/5/10/20个交易日离场与波动风险",
        "evidence": "A股短期反转研究存在市场/样本依赖，容易受到流动性和冲击成本影响",
        "required_data": "至少130根已完成日K线",
    },
    {
        "id": "sector_rotation_v1",
        "name": "行业相对强度轮动",
        "state": "data_pending",
        "horizon": "20-60个交易日",
        "entry": "需要稳定的历史行业指数、实时成分归属以及可用行业ETF数据；不使用现有单日行业涨幅冒充历史轮动",
        "exit_hypothesis": "行业排名下滑或风险预算触发",
        "evidence": "待获取可审计的历史行业时间序列并做样本外研究",
        "required_data": "历史行业指数、成分股历史归属及可交易ETF",
    },
    {
        "id": "quality_value_v1",
        "name": "质量价值多因子",
        "state": "data_pending",
        "horizon": "60-250个交易日",
        "entry": "需要按实际披露日期对齐的财报、估值、现金流/盈利质量指标，防止未来信息泄漏",
        "exit_hypothesis": "质量恶化或估值极端",
        "evidence": "因子文献有相关证据，但必须控制A股披露时点和样本偏差",
        "required_data": "财务公告实际公布日期、历史市值与财报",
    },
    {
        "id": "low_volatility_v1",
        "name": "低波动风险控制",
        "state": "data_pending",
        "horizon": "60-250个交易日",
        "entry": "需要全市场完整历史收益和组合协方差；不是简单选历史波动最小的股票",
        "exit_hypothesis": "定期再平衡，组合波动目标与行业集中度上限",
        "evidence": "风险管理研究方向，不承诺收益增加或亏损减少",
        "required_data": "全市场历史价格、指数基准和组合持仓",
    },
]

_ACTIVE_IDS = {s["id"] for s in STRATEGIES if s["state"] == "experimental"}


def _finite(values):
    return all(math.isfinite(float(v)) for v in values)


def evaluate_rules(frame, code: str, name: str):
    """Return today's independently labeled hypotheses; no orders or expected returns.

    Required columns: date, close, low, high, volume. The upstream data builder
    already validates daily candles and excludes intraday unfinished bars.
    """
    required = {"date", "close", "high", "low", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError("Missing daily bar columns for strategy catalog")
    x = frame.sort_values("date", kind="stable")
    if len(x) < 130 or x["date"].duplicated().any():
        return []
    tail = x.tail(130)
    close = [float(v) for v in tail["close"].tolist()]
    low = [float(v) for v in tail["low"].tolist()]
    high = [float(v) for v in tail["high"].tolist()]
    vol = [float(v) for v in tail["volume"].tolist()]
    if not _finite(close + low + high + vol):
        return []
    if any(p <= 0 for p in close + low + high) or any(v < 0 for v in vol):
        return []
    if any(high[i] < max(low[i], close[i]) or low[i] > close[i] for i in range(len(close))):
        return []
    prev_vol20 = sum(vol[-21:-1]) / 20
    if prev_vol20 <= 0 or vol[-1] <= 0:
        return []
    p = close[-1]
    prior = close[-2]
    ma20 = sum(close[-20:]) / 20
    ma60 = sum(close[-60:]) / 60
    ma120 = sum(close[-120:]) / 120
    ratio = vol[-1] / prev_vol20
    old_high120 = max(high[-121:-1])
    low40 = min(low[-40:])
    drawdown = (old_high120 - low40) / old_high120
    low_new10 = min(low[-10:])
    low_before10 = min(low[-20:-10])
    prev60high = max(close[-61:-1])
    prior_5d_change = prior / close[-7] - 1
    pullback = min(close[-4:-1]) <= ma20 * 1.015
    signal_flags = {
        "bottom_reversal_v1": (
            drawdown >= .22 and low_new10 >= low_before10 * .995
            and p >= ma20 and p >= prior * 1.005
            and ratio >= 1.2 and p <= old_high120 * .92
        ),
        "volume_breakout_v1": (
            p > prev60high and ma20 > ma60 and ratio >= 1.5
        ),
        "trend_pullback_v1": (
            ma20 > ma60 and p >= ma20 and p > prior and pullback
            and ratio >= .75 and p <= prev60high * 1.08
        ),
        "short_rebound_v1": (
            -.14 <= prior_5d_change <= -.07
            and p >= prior * 1.01 and p >= ma120 * .92
            and ratio >= .75
        ),
    }
    assert set(signal_flags) == _ACTIVE_IDS, "Strategy catalog must match implementation"
    day = x["date"].iloc[-1]
    if hasattr(day, "strftime"):
        day = day.strftime("%Y-%m-%d")
    else:
        day = str(day)[:10]
    metrics = {
        "ma20": round(ma20, 4), "ma60": round(ma60, 4),
        "ma120": round(ma120, 4),
        "volume_ratio20": round(ratio, 3),
        "prior_60d_close_high": round(prev60high, 4),
        "observed_120d_to_40d_drawdown_pct": round(drawdown * 100, 3),
    }
    signals = []
    for definition in STRATEGIES:
        strategy_id = definition["id"]
        if not signal_flags.get(strategy_id):
            continue
        signals.append({
            "code": str(code).zfill(6), "name": str(name)[:100],
            "strategy_id": strategy_id,
            "strategy_name": definition["name"],
            "signal_date": day,
            "reference_close": round(p, 4),
            "price_adjustment": "none",
            "status": "hypothesis_only",
            "metrics": metrics,
            "execution": "信号收盘后才已知，不表示该收盘价可成交",
            "forward_performance": None,
        })
    return signals
