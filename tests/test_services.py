from pathlib import Path

from stock_mcp.providers.akshare_provider import ProviderFailure
from stock_mcp.providers.csv_provider import LocalCsvDataProvider
from stock_mcp.services.daily_plan_service import DailyPlanService
from stock_mcp.services.indicator_service import IndicatorService
from stock_mcp.services.kline_service import KlineService
from stock_mcp.services.quote_service import QuoteService
from stock_mcp.services.wyckoff_service import WyckoffService
from stock_mcp.settings import Settings


class FakeAKShareProvider:
    def __init__(self, fail_quotes: bool = False, fail_kline: bool = False) -> None:
        self.fail_quotes = fail_quotes
        self.fail_kline = fail_kline

    def get_quotes(self, codes: list[str], as_of: str):
        if self.fail_quotes:
            raise ProviderFailure("akshare.fake", "quote failed")
        return [
            type(
                "QuoteRow",
                (),
                {
                    "code": code,
                    "name": f"Name-{code}",
                    "market": "ETF" if code.startswith("513") else "A",
                    "price": 10.5,
                    "change_pct": 1.2,
                    "volume": 1000.0,
                    "amount": 2000.0,
                    "turnover_rate": 3.1,
                    "open_price": 10.0,
                    "high_price": 10.8,
                    "low_price": 9.9,
                    "previous_close": 10.1,
                    "data_source": "akshare.fake",
                    "as_of": as_of,
                },
            )()
            for code in codes
        ]

    def get_kline(self, code: str, start_date: str, end_date: str, adjust: str, name: str = ""):
        del start_date, end_date, adjust, name
        if self.fail_kline:
            raise ProviderFailure("akshare.fake_hist", "kline failed")
        return [
            type(
                "Bar",
                (),
                {
                    "code": code,
                    "name": f"Name-{code}",
                    "date": f"2024-01-{day:02d}",
                    "open_price": 10 + day * 0.1,
                    "high_price": 10.5 + day * 0.1,
                    "low_price": 9.5 + day * 0.1,
                    "close_price": 10.2 + day * 0.1,
                    "volume": 1000.0 + day * 10,
                    "amount": 2000.0 + day * 100,
                    "turnover_rate": 1.0,
                    "data_source": "akshare.fake_hist",
                },
            )()
            for day in range(1, 40)
        ]


def test_quote_service_returns_structured_quotes() -> None:
    service = QuoteService(akshare_provider=FakeAKShareProvider())

    result = service.get_quotes(["000338", "513120"])

    assert result["data_source"] == "akshare.fake"
    assert result["items"][0]["code"] == "000338"
    assert result["items"][1]["market"] == "ETF"


def test_quote_service_returns_explicit_error_when_upstream_fails() -> None:
    service = QuoteService(akshare_provider=FakeAKShareProvider(fail_quotes=True))

    result = service.get_quotes(["000338"])

    assert result["items"] == []
    assert result["error"]["source"] == "akshare.fake"
    assert result["error"]["message"] == "quote failed"


def test_kline_service_falls_back_to_csv_when_akshare_fails(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "sz000338.csv").write_text(
        "\n".join(
            [
                "说明行",
                "股票代码,股票名称,交易日期,开盘价,最高价,最低价,收盘价,前收盘价,成交量,成交额,流通市值,总市值",
                "sz000338,潍柴动力,2024-01-02,10,11,9,10.5,10,1000,2000,1,2",
            ]
        ),
        encoding="gbk",
    )
    csv_provider = LocalCsvDataProvider(Settings(history_data_dir=history_dir))
    service = KlineService(akshare_provider=FakeAKShareProvider(fail_kline=True), csv_provider=csv_provider)

    result = service.get_kline(code="000338", start_date="20240101", end_date="20240131")

    assert result["data_source"] == "csv_fallback"
    assert result["items"][0]["close"] == 10.5


def test_indicator_and_wyckoff_services_return_expected_structure(tmp_path: Path) -> None:
    csv_provider = LocalCsvDataProvider(Settings(history_data_dir=tmp_path / "unused"))
    kline_service = KlineService(akshare_provider=FakeAKShareProvider(), csv_provider=csv_provider)
    indicator_service = IndicatorService(kline_service=kline_service)
    wyckoff_service = WyckoffService(kline_service=kline_service, indicator_service=indicator_service)

    indicators = indicator_service.get_indicators("000338", lookback=30)
    analysis = wyckoff_service.analyze("000338", lookback=30)

    assert indicators["ma5"] is not None
    assert set(analysis).issuperset({"stage", "support", "resistance", "summary"})


def test_daily_plan_service_outputs_items_structure(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "watchlist.yaml").write_text(
        "watchlist:\n  - code: \"000338\"\n    name: \"潍柴动力\"\n    market: \"A\"\n",
        encoding="utf-8",
    )
    (config_dir / "positions.yaml").write_text("positions:\n", encoding="utf-8")
    settings = Settings(config_dir=config_dir)
    quote_service = QuoteService(akshare_provider=FakeAKShareProvider())
    csv_provider = LocalCsvDataProvider(Settings(history_data_dir=tmp_path / "unused"))
    kline_service = KlineService(akshare_provider=FakeAKShareProvider(), csv_provider=csv_provider)
    indicator_service = IndicatorService(kline_service=kline_service)
    wyckoff_service = WyckoffService(kline_service=kline_service, indicator_service=indicator_service)
    service = DailyPlanService(settings=settings, quote_service=quote_service, wyckoff_service=wyckoff_service)

    result = service.generate_daily_plan()

    assert result["data_status"] == "ok"
    assert result["items"][0]["code"] == "000338"
    assert "action" in result["items"][0]
