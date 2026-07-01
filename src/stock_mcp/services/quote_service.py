from __future__ import annotations

from stock_mcp.models import DataError
from stock_mcp.providers.akshare_provider import AKShareProvider, ProviderFailure
from stock_mcp.utils.time import now_text


class QuoteService:
    def __init__(self, akshare_provider: AKShareProvider) -> None:
        self._akshare_provider = akshare_provider

    def get_quotes(self, codes: list[str]) -> dict:
        as_of = now_text()
        try:
            items = self._akshare_provider.get_quotes(codes=codes, as_of=as_of)
        except ProviderFailure as exc:
            return {
                "data_source": exc.source,
                "as_of": as_of,
                "items": [],
                "error": {
                    "source": exc.source,
                    "message": exc.message,
                },
            }

        return {
            "data_source": " / ".join(dict.fromkeys(item.data_source for item in items)) if items else "akshare",
            "as_of": as_of,
            "items": [
                {
                    "code": item.code,
                    "name": item.name,
                    "market": item.market,
                    "price": item.price,
                    "change_pct": item.change_pct,
                    "volume": item.volume,
                    "amount": item.amount,
                    "turnover_rate": item.turnover_rate,
                    "open": item.open_price,
                    "high": item.high_price,
                    "low": item.low_price,
                    "previous_close": item.previous_close,
                    "data_source": item.data_source,
                }
                for item in items
            ],
        }
