from __future__ import annotations

from stock_mcp.services.kline_service import KlineService


def get_kline(
    service: KlineService,
    code: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> dict:
    return service.get_kline(code=code, start_date=start_date, end_date=end_date, adjust=adjust)

