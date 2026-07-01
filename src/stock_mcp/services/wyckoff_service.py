from __future__ import annotations

import pandas as pd

from stock_mcp.services.indicator_service import IndicatorService
from stock_mcp.services.kline_service import KlineService


class WyckoffService:
    def __init__(self, kline_service: KlineService, indicator_service: IndicatorService) -> None:
        self._kline_service = kline_service
        self._indicator_service = indicator_service

    def analyze(self, code: str, lookback: int = 120) -> dict:
        kline = self._kline_service.get_kline(code=code, start_date="20100101", end_date="20500101")
        if kline.get("error"):
            return {"code": code, "error": kline["error"]}

        frame = pd.DataFrame(kline["items"]).tail(lookback).reset_index(drop=True)
        if frame.empty:
            return {"code": code, "error": {"message": "No kline data for Wyckoff analysis.", "source": "wyckoff_service"}}

        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["high"] = pd.to_numeric(frame["high"], errors="coerce")
        frame["low"] = pd.to_numeric(frame["low"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
        indicators = self._indicator_service.get_indicators(code=code, lookback=lookback)

        latest = frame.iloc[-1]
        support = round(float(frame["low"].tail(20).quantile(0.2)), 2)
        resistance = round(float(frame["high"].tail(20).quantile(0.8)), 2)
        close = float(latest["close"])
        volume = float(latest["volume"]) if pd.notna(latest["volume"]) else 0.0
        volume_ma5 = indicators.get("volume_ma5") or 0.0
        ma20 = indicators.get("ma20") or close

        if close > resistance * 0.995 and volume_ma5 and volume > volume_ma5 * 1.5:
            stage = "markup_breakout"
            stage_name_cn = "放量突破"
            action_bias = "positive"
        elif close >= ma20 and volume_ma5 and volume <= volume_ma5:
            stage = "re_accumulation_backup"
            stage_name_cn = "再吸筹后的回踩确认"
            action_bias = "neutral_positive"
        elif close < support and volume_ma5 and volume > volume_ma5 * 1.3:
            stage = "markdown_break"
            stage_name_cn = "跌破支撑"
            action_bias = "negative"
        else:
            stage = "range_observation"
            stage_name_cn = "区间观察"
            action_bias = "neutral"

        return {
            "code": code,
            "stage": stage,
            "stage_name_cn": stage_name_cn,
            "effort_vs_result": action_bias,
            "volume_state": _describe_volume(volume=volume, volume_ma5=volume_ma5),
            "support": [support, round(support * 0.98, 2)],
            "resistance": [resistance, round(resistance * 1.02, 2)],
            "risk_reward": _estimate_risk_reward(close=close, support=support, resistance=resistance),
            "summary": _build_summary(stage_name_cn=stage_name_cn, support=support, resistance=resistance),
            "data_source": kline["data_source"],
        }


def _describe_volume(volume: float, volume_ma5: float) -> str:
    if not volume_ma5:
        return "unknown"
    if volume > volume_ma5 * 1.5:
        return "expanding"
    if volume < volume_ma5:
        return "pullback_volume_contracting"
    return "neutral"


def _estimate_risk_reward(close: float, support: float, resistance: float) -> float | None:
    risk = close - support
    reward = resistance - close
    if risk <= 0:
        return None
    return round(reward / risk, 2)


def _build_summary(stage_name_cn: str, support: float, resistance: float) -> str:
    return f"当前结构为{stage_name_cn}，重点观察 {support:.2f} 一线支撑与 {resistance:.2f} 一线压力。"

