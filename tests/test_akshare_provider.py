import pandas as pd

from stock_mcp.providers.akshare_provider import AKShareProvider, ProviderFailure


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


def test_select_quotes_matches_eastmoney_digit_codes() -> None:
    provider = AKShareProvider()
    frame = pd.DataFrame(
        [
            {
                "代码": "000338",
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

    result = provider._select_quotes(frame, ["000338"], market="A", as_of="2026-07-01 15:00:00", source="akshare.stock_zh_a_spot_em")

    assert result[0].code == "000338"
    assert result[0].data_source == "akshare.stock_zh_a_spot_em"


def test_get_a_share_spot_frame_prefers_eastmoney(monkeypatch) -> None:
    provider = AKShareProvider()
    frame = pd.DataFrame([{"代码": "000338"}])

    monkeypatch.setattr("stock_mcp.providers.akshare_provider.ak.stock_zh_a_spot_em", lambda: frame)
    monkeypatch.setattr(
        "stock_mcp.providers.akshare_provider.ak.stock_zh_a_spot",
        lambda: (_ for _ in ()).throw(AssertionError("legacy sina path should not be used")),
    )

    result_frame, source = provider._get_a_share_spot_frame()

    assert result_frame is frame
    assert source == "akshare.stock_zh_a_spot_em"


def test_get_a_share_spot_frame_falls_back_to_sina(monkeypatch) -> None:
    provider = AKShareProvider()
    frame = pd.DataFrame([{"代码": "sz000338"}])

    monkeypatch.setattr(
        "stock_mcp.providers.akshare_provider.ak.stock_zh_a_spot_em",
        lambda: (_ for _ in ()).throw(RuntimeError("eastmoney unavailable")),
    )
    monkeypatch.setattr("stock_mcp.providers.akshare_provider.ak.stock_zh_a_spot", lambda: frame)

    result_frame, source = provider._get_a_share_spot_frame()

    assert result_frame is frame
    assert source == "akshare.stock_zh_a_spot"


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


def test_secid_mapping_matches_exchange_prefixes() -> None:
    provider = AKShareProvider()

    assert provider._secid_for_symbol("000338") == "0.000338"
    assert provider._secid_for_symbol("600000") == "1.600000"
    assert provider._secid_for_symbol("513120") == "1.513120"
    assert provider._secid_for_symbol("830799") == "0.830799"


def test_build_quote_from_eastmoney_payload_maps_fields() -> None:
    provider = AKShareProvider()

    result = provider._build_quote_from_eastmoney_payload(
        {
            "f57": "000338",
            "f58": "潍柴动力",
            "f43": 27.91,
            "f170": 1.23,
            "f47": 1000,
            "f48": 2000,
            "f168": 3.5,
            "f46": 27.5,
            "f44": 28.2,
            "f45": 27.3,
            "f60": 27.57,
        },
        code="000338",
        as_of="2026-07-09 09:00:00",
    )

    assert result.code == "000338"
    assert result.name == "潍柴动力"
    assert result.market == "A"
    assert result.price == 27.91
    assert result.previous_close == 27.57
    assert result.data_source == "eastmoney.stock.get"


def test_build_kline_frame_from_eastmoney_maps_payload() -> None:
    provider = AKShareProvider()

    frame = provider._build_kline_frame_from_eastmoney(
        {
            "data": {
                "klines": [
                    "2026-07-09,27.95,28.04,28.35,27.93,124837,351541767.78,1.5,1.04,0.29,0.17"
                ]
            }
        },
        symbol="000338",
    )

    assert frame.iloc[0]["股票代码"] == "000338"
    assert frame.iloc[0]["开盘"] == 27.95
    assert frame.iloc[0]["收盘"] == 28.04
    assert frame.iloc[0]["最高"] == 28.35


def test_get_kline_prefers_direct_a_share_history(monkeypatch) -> None:
    provider = AKShareProvider()
    frame = provider._build_kline_frame_from_eastmoney(
        {
            "data": {
                "klines": [
                    "2026-07-09,27.95,28.04,28.35,27.93,124837,351541767.78,1.5,1.04,0.29,0.17"
                ]
            }
        },
        symbol="000338",
    )

    monkeypatch.setattr(provider, "_get_a_share_hist_direct", lambda symbol, start_date, end_date, adjust: frame)
    monkeypatch.setattr(
        "stock_mcp.providers.akshare_provider.ak.stock_zh_a_hist",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy akshare A-share path should not be used")),
    )

    result = provider.get_kline(code="000338", start_date="20260101", end_date="20260709", adjust="qfq")

    assert result[0].code == "000338"
    assert result[0].data_source == "eastmoney.stock.kline"
    assert result[0].close_price == 28.04


def test_get_quotes_uses_direct_path_and_delayed_etf_fallback(monkeypatch) -> None:
    provider = AKShareProvider()

    monkeypatch.setattr(
        provider,
        "_get_realtime_quotes_direct",
        lambda normalized_codes, as_of: (
            [
                provider._build_quote_from_eastmoney_payload(
                    {
                        "f57": "000338",
                        "f58": "潍柴动力",
                        "f43": 27.91,
                        "f170": 1.23,
                        "f47": 1000,
                        "f48": 2000,
                        "f168": 3.5,
                        "f46": 27.5,
                        "f44": 28.2,
                        "f45": 27.3,
                        "f60": 27.57,
                    },
                    code="000338",
                    as_of=as_of,
                )
            ],
            ["513120: timeout"],
        ),
    )
    monkeypatch.setattr(
        "stock_mcp.providers.akshare_provider.ak.fund_etf_fund_daily_em",
        lambda: pd.DataFrame(
            [
                {
                    "基金代码": "513120",
                    "基金简称": "港股创新药ETF",
                    "2026-06-30-单位净值": "0.9633",
                    "增长率": "7.42%",
                    "市价": "0.9710",
                }
            ]
        ),
    )

    result = provider.get_quotes(["000338", "513120"], as_of="2026-07-09 09:00:00")

    assert [item.code for item in result] == ["000338", "513120"]
    assert result[0].data_source == "eastmoney.stock.get"
    assert result[1].data_source == "akshare.fund_etf_fund_daily_em(delayed)"


def test_get_quotes_raises_when_all_direct_paths_fail(monkeypatch) -> None:
    provider = AKShareProvider()

    monkeypatch.setattr(provider, "_get_realtime_quotes_direct", lambda normalized_codes, as_of: ([], ["000338: timeout"]))
    monkeypatch.setattr(
        "stock_mcp.providers.akshare_provider.ak.fund_etf_fund_daily_em",
        lambda: (_ for _ in ()).throw(RuntimeError("delayed unavailable")),
    )

    try:
        provider.get_quotes(["000338"], as_of="2026-07-09 09:00:00")
    except ProviderFailure as exc:
        assert exc.source == "eastmoney.stock.get"
        assert "000338: timeout" in exc.message
    else:
        raise AssertionError("ProviderFailure not raised")
