from __future__ import annotations

from stock_mcp.services.quote_service import QuoteService


def get_quotes(service: QuoteService, codes: list[str]) -> dict:
    return service.get_quotes(codes)

