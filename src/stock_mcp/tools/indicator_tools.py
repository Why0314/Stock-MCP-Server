from __future__ import annotations

from stock_mcp.services.indicator_service import IndicatorService
from stock_mcp.services.wyckoff_service import WyckoffService


def get_indicators(
    indicator_service: IndicatorService,
    code: str,
    period: str = "daily",
    lookback: int = 120,
) -> dict:
    return indicator_service.get_indicators(code=code, period=period, lookback=lookback)


def analyze_wyckoff(
    wyckoff_service: WyckoffService,
    code: str,
    lookback: int = 120,
) -> dict:
    return wyckoff_service.analyze(code=code, lookback=lookback)

