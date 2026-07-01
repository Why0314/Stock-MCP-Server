from pathlib import Path

from stock_mcp.config_loader import load_named_records


def test_load_named_records_reads_yaml_list(tmp_path: Path) -> None:
    config_path = tmp_path / "watchlist.yaml"
    config_path.write_text(
        "watchlist:\n  - code: '000338'\n    name: '潍柴动力'\n    market: 'A'\n",
        encoding="utf-8",
    )

    result = load_named_records(config_path, "watchlist")

    assert result == [{"code": "000338", "name": "潍柴动力", "market": "A"}]

