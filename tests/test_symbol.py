from stock_mcp.utils.symbol import infer_market, normalize_symbol


def test_normalize_symbol_supports_prefixed_and_plain_codes() -> None:
    assert normalize_symbol("000338") == "sz000338"
    assert normalize_symbol("sh600519") == "sh600519"
    assert normalize_symbol("513120") == "sh513120"


def test_infer_market_routes_a_share_etf_and_bj() -> None:
    assert infer_market("000338") == "A"
    assert infer_market("513120") == "ETF"
    assert infer_market("920047") == "BJ"

