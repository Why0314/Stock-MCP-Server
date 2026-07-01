from __future__ import annotations

import argparse

from stock_mcp.providers.akshare_provider import AKShareProvider
from stock_mcp.providers.csv_provider import LocalCsvDataProvider
from stock_mcp.services.daily_plan_service import DailyPlanService
from stock_mcp.services.indicator_service import IndicatorService
from stock_mcp.services.kline_service import KlineService
from stock_mcp.services.quote_service import QuoteService
from stock_mcp.services.wyckoff_service import WyckoffService
from stock_mcp.settings import Settings, load_settings
from stock_mcp.tools.indicator_tools import analyze_wyckoff, get_indicators
from stock_mcp.tools.kline_tools import get_kline
from stock_mcp.tools.plan_tools import generate_daily_plan
from stock_mcp.tools.quote_tools import get_quotes

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - depends on local install state
    FastMCP = None


def create_app(settings: Settings | None = None) -> dict[str, object]:
    resolved_settings = settings or load_settings()
    akshare_provider = AKShareProvider()
    csv_provider = LocalCsvDataProvider(settings=resolved_settings)
    quote_service = QuoteService(akshare_provider=akshare_provider)
    kline_service = KlineService(akshare_provider=akshare_provider, csv_provider=csv_provider)
    indicator_service = IndicatorService(kline_service=kline_service)
    wyckoff_service = WyckoffService(kline_service=kline_service, indicator_service=indicator_service)
    daily_plan_service = DailyPlanService(
        settings=resolved_settings,
        quote_service=quote_service,
        wyckoff_service=wyckoff_service,
    )
    return {
        "settings": resolved_settings,
        "quote_service": quote_service,
        "kline_service": kline_service,
        "indicator_service": indicator_service,
        "wyckoff_service": wyckoff_service,
        "daily_plan_service": daily_plan_service,
    }


def create_mcp_server(settings: Settings | None = None):
    if FastMCP is None:
        raise RuntimeError(
            "The 'mcp' package is not installed. Run `uv sync` or `pip install -e .` before starting the MCP server."
        )

    app = create_app(settings=settings)
    mcp = FastMCP("stock-mcp")

    @mcp.tool()
    def get_quotes_tool(codes: list[str]) -> dict:
        """获取 A 股、北交所和 ETF 最新行情。"""
        return get_quotes(app["quote_service"], codes)

    @mcp.tool()
    def get_kline_tool(code: str, start_date: str, end_date: str, adjust: str = "qfq") -> dict:
        """获取历史 K 线，AKShare 失败时自动回退到本地 CSV。"""
        return get_kline(app["kline_service"], code=code, start_date=start_date, end_date=end_date, adjust=adjust)

    @mcp.tool()
    def get_indicators_tool(code: str, period: str = "daily", lookback: int = 120) -> dict:
        """计算 MA、RSI、ATR、MACD 等指标。"""
        return get_indicators(app["indicator_service"], code=code, period=period, lookback=lookback)

    @mcp.tool()
    def analyze_wyckoff_tool(code: str, lookback: int = 120) -> dict:
        """输出简化版 Wyckoff 结构判断。"""
        return analyze_wyckoff(app["wyckoff_service"], code=code, lookback=lookback)

    @mcp.tool()
    def generate_daily_plan_tool(use_watchlist: bool = True, use_positions: bool = True) -> dict:
        """生成每日交易计划。"""
        return generate_daily_plan(app["daily_plan_service"], use_watchlist=use_watchlist, use_positions=use_positions)

    return mcp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stock MCP Server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport mode. Default: stdio.",
    )
    parser.add_argument(
        "--mount-path",
        default="/mcp",
        help="Mount path used by streamable-http or sse transports. Default: /mcp.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    server = create_mcp_server()
    mount_path = args.mount_path if args.transport != "stdio" else None
    server.run(transport=args.transport, mount_path=mount_path)


if __name__ == "__main__":
    main()
