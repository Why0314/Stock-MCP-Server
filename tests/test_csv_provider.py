from pathlib import Path

from stock_mcp.providers.csv_provider import LocalCsvDataProvider
from stock_mcp.settings import Settings


def test_load_price_history_standardizes_gbk_csv(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "sz002435.csv").write_text(
        "\n".join(
            [
                "说明行",
                "股票代码,股票名称,交易日期,开盘价,最高价,最低价,收盘价,前收盘价,成交量,成交额,流通市值,总市值",
                "sz002435,长江润发,2010-06-20,16.5,17.4,16.07,17.06,17.85,10056512.0,166704958.4,450384000.0,2251920000.0",
                ",,2010-06-21,16.6,17.5,16.17,17.16,17.06,10056513.0,166704959.4,450384001.0,2251920001.0",
            ]
        ),
        encoding="gbk",
    )
    provider = LocalCsvDataProvider(Settings(history_data_dir=history_dir))

    bars = provider.load_price_history("002435")

    assert len(bars) == 2
    assert bars[0].code == "sz002435"
    assert bars[0].name == "长江润发"
    assert bars[0].date == "2010-06-20"
    assert bars[-1].close_price == 17.16


def test_load_financial_statements_uses_configured_fin_dir(tmp_path: Path) -> None:
    fin_dir = tmp_path / "fin"
    symbol_dir = fin_dir / "sz002790"
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "sz002790_一般企业.csv").write_text(
        "\n".join(
            [
                "说明行",
                "stock_code,statement_format,report_date,publish_date,R_np@xbx",
                "sz002790,一般企业,20241231,2025-03-20,123456.78",
            ]
        ),
        encoding="gbk",
    )
    provider = LocalCsvDataProvider(Settings(fin_data_dir=fin_dir))

    statements = provider.load_financial_statements("002790")

    assert len(statements) == 1
    assert statements[0].symbol == "sz002790"
    assert statements[0].report_date == "20241231"
    assert statements[0].values["R_np@xbx"] == 123456.78
