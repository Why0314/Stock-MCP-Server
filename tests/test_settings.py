from pathlib import Path

from stock_mcp.settings import load_settings


def test_load_settings_reads_configured_paths(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "STOCK_ENV=test",
                "STOCK_HISTORY_DATA_DIR=/tmp/history-data",
                "STOCK_FIN_DATA_DIR=/tmp/fin-data",
                "STOCK_CONFIG_DIR=/tmp/config-data",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(dotenv_path)

    assert settings.env == "test"
    assert settings.history_data_dir == Path("/tmp/history-data")
    assert settings.fin_data_dir == Path("/tmp/fin-data")
    assert settings.config_dir == Path("/tmp/config-data")

