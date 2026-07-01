import pandas as pd

from stock_mcp.providers.akshare_provider import AKShareProvider


def test_select_quotes_maps_prefixed_a_share_codes() -> None:
    provider = AKShareProvider()
    frame = pd.DataFrame(
        [
            {
                "代码": "sz000338",
                "名称": "潍柴动力",
                "最新价": 27.8,
                "涨跌幅": 2.018,
                "成交量": 97099884.0,
                "成交额": 2751394387.0,
                "换手率": 2.3,
                "今开": 28.11,
                "最高": 29.0,
                "最低": 27.6,
                "昨收": 27.25,
            }
        ]
    )

    result = provider._select_quotes(frame, ["sz000338"], market="A", as_of="2026-07-01 15:00:00", source="akshare.stock_zh_a_spot")

    assert result[0].code == "000338"
    assert result[0].price == 27.8


def test_select_etf_daily_quotes_maps_delayed_snapshot() -> None:
    provider = AKShareProvider()
    frame = pd.DataFrame(
        [
            {
                "基金代码": "513120",
                "基金简称": "港股创新药ETF",
                "2026-06-30-单位净值": "0.9633",
                "增长率": "7.42%",
                "市价": "0.9710",
            }
        ]
    )

    result = provider._select_etf_daily_quotes(
        frame=frame,
        codes=["513120"],
        as_of="2026-07-01 15:00:00",
        source="akshare.fund_etf_fund_daily_em(delayed)",
    )

    assert result[0].code == "513120"
    assert result[0].price == 0.971
    assert result[0].change_pct == 7.42
    assert result[0].as_of == "2026-06-30"
