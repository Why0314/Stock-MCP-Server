from __future__ import annotations

from stock_mcp.models import DataError
from stock_mcp.providers.akshare_provider import AKShareProvider, ProviderFailure
from stock_mcp.providers.csv_provider import LocalCsvDataProvider


class KlineService:
    def __init__(
        self,
        akshare_provider: AKShareProvider,
        csv_provider: LocalCsvDataProvider,
    ) -> None:
        self._akshare_provider = akshare_provider
        self._csv_provider = csv_provider

    def get_kline(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> dict:
        akshare_error: ProviderFailure | None = None
        try:
            items = self._akshare_provider.get_kline(code=code, start_date=start_date, end_date=end_date, adjust=adjust)
            if items:
                return self._build_response(code=code, name=items[-1].name, data_source=items[-1].data_source, items=items)
        except ProviderFailure as exc:
            akshare_error = exc

        try:
            items = self._csv_provider.load_price_history(symbol=code, start_date=start_date, end_date=end_date)
        except Exception as exc:
            return {
                "code": code,
                "name": "",
                "data_source": "error",
                "items": [],
                "error": {
                    "message": str(exc),
                    "source": "csv_provider",
                    "upstream_error": str(akshare_error) if akshare_error else None,
                },
            }

        if not items:
            message = "No kline data found from AKShare or CSV fallback."
            return {
                "code": code,
                "name": "",
                "data_source": "error",
                "items": [],
                "error": DataError(
                    source="kline_service",
                    message=message,
                    code=code,
                    details={"upstream_error": str(akshare_error) if akshare_error else None},
                ).details
                | {"message": message, "source": "kline_service", "upstream_error": str(akshare_error) if akshare_error else None},
            }

        return self._build_response(code=code, name=items[-1].name, data_source="csv_fallback", items=items)

    def _build_response(self, code: str, name: str, data_source: str, items: list) -> dict:
        return {
            "code": code,
            "name": name,
            "data_source": data_source,
            "items": [
                {
                    "date": item.date,
                    "open": item.open_price,
                    "high": item.high_price,
                    "low": item.low_price,
                    "close": item.close_price,
                    "volume": item.volume,
                    "amount": item.amount,
                }
                for item in items
            ],
        }

