from __future__ import annotations

import pandas as pd

from stock_mcp.services.kline_service import KlineService


class IndicatorService:
    def __init__(self, kline_service: KlineService) -> None:
        self._kline_service = kline_service

    def get_indicators(self, code: str, period: str = "daily", lookback: int = 120) -> dict:
        del period
        kline = self._kline_service.get_kline(code=code, start_date="20100101", end_date="20500101")
        if kline.get("error"):
            return {"code": code, "error": kline["error"]}

        frame = pd.DataFrame(kline["items"]).tail(lookback).reset_index(drop=True)
        if frame.empty:
            return {"code": code, "error": {"message": "No kline data for indicator calculation.", "source": "indicator_service"}}

        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["high"] = pd.to_numeric(frame["high"], errors="coerce")
        frame["low"] = pd.to_numeric(frame["low"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")

        close = frame["close"]
        volume = frame["volume"]
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        volume_ma5 = volume.rolling(5).mean().iloc[-1]
        volume_ratio = _safe_div(volume.iloc[-1], volume_ma5)

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        rsi14 = 100 - (100 / (1 + rs.iloc[-1]))

        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - prev_close).abs(),
                (frame["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr14 = true_range.rolling(14).mean().iloc[-1]

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        hist = dif - dea

        return {
            "code": code,
            "ma5": _to_float(ma5),
            "ma10": _to_float(ma10),
            "ma20": _to_float(ma20),
            "volume_ma5": _to_float(volume_ma5),
            "volume_ratio": _to_float(volume_ratio),
            "rsi14": _to_float(rsi14),
            "atr14": _to_float(atr14),
            "macd": {
                "dif": _to_float(dif.iloc[-1]),
                "dea": _to_float(dea.iloc[-1]),
                "hist": _to_float(hist.iloc[-1]),
            },
            "data_source": kline["data_source"],
        }


def _safe_div(left: float | None, right: float | None) -> float | None:
    if left is None or right in (None, 0):
        return None
    return float(left / right)


def _to_float(value) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), 4)

