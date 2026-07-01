from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_mcp.models import FinancialStatementRow, KlineBar
from stock_mcp.settings import Settings
from stock_mcp.utils.symbol import normalize_symbol

CSV_COLUMN_MAPPING = {
    "股票代码": "code",
    "股票名称": "name",
    "交易日期": "date",
    "开盘价": "open",
    "最高价": "high",
    "最低价": "low",
    "收盘价": "close",
    "前收盘价": "previous_close",
    "成交量": "volume",
    "成交额": "amount",
    "流通市值": "float_market_cap",
    "总市值": "total_market_cap",
}

CSV_ENCODINGS = ("utf-8", "gbk", "gb18030")


class LocalCsvDataProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load_price_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> list[KlineBar]:
        normalized_symbol = normalize_symbol(symbol)
        history_path = self._settings.require_history_data_dir() / f"{normalized_symbol}.csv"
        frame = self._read_history_frame(history_path)
        frame = self._filter_history_frame(frame, start_date=start_date, end_date=end_date, limit=limit)

        return [
            KlineBar(
                code=row["code"],
                name=row["name"],
                date=row["date"],
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                previous_close=_optional_float(row.get("previous_close")),
                volume=_optional_float(row.get("volume")),
                amount=_optional_float(row.get("amount")),
                data_source="csv",
            )
            for row in frame.to_dict("records")
        ]

    def load_financial_statements(
        self,
        symbol: str,
        limit: int | None = None,
    ) -> list[FinancialStatementRow]:
        normalized_symbol = normalize_symbol(symbol)
        symbol_dir = self._settings.require_fin_data_dir() / normalized_symbol
        if not symbol_dir.exists():
            raise FileNotFoundError(f"Financial data directory not found: {symbol_dir}")

        statement_files = sorted(symbol_dir.glob("*.csv"))
        if not statement_files:
            raise FileNotFoundError(f"No financial CSV files found under: {symbol_dir}")

        target_file = statement_files[0]
        frame = self._read_csv_with_fallback(target_file, skiprows=1)
        if limit:
            frame = frame.head(limit)

        return [
            FinancialStatementRow(
                symbol=str(row.get("stock_code", normalized_symbol)),
                statement_file=target_file.name,
                report_date=str(row.get("report_date", "")),
                publish_date=str(row.get("publish_date", "")),
                statement_format=str(row.get("statement_format", "")),
                values={key: _nan_to_none(value) for key, value in row.items()},
            )
            for row in frame.to_dict("records")
        ]

    def _read_history_frame(self, file_path: Path) -> pd.DataFrame:
        frame = self._read_csv_with_fallback(file_path, skiprows=1)
        frame = frame.rename(columns=CSV_COLUMN_MAPPING)
        missing_columns = [column for column in CSV_COLUMN_MAPPING.values() if column not in frame.columns]
        if missing_columns:
            raise ValueError(f"CSV file missing required columns: {missing_columns}")

        frame = frame[list(CSV_COLUMN_MAPPING.values())].copy()
        frame["code"] = frame["code"].ffill().astype(str).str.strip()
        frame["name"] = frame["name"].ffill().astype(str).str.strip()
        frame = frame[frame["date"].astype(str).str.contains(r"\d{4}-\d{2}-\d{2}", na=False)]

        for column in ("open", "high", "low", "close", "previous_close", "volume", "amount"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["code", "name", "date", "open", "high", "low", "close"])
        frame = frame.sort_values("date").reset_index(drop=True)
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        return frame

    def _filter_history_frame(
        self,
        frame: pd.DataFrame,
        start_date: str | None,
        end_date: str | None,
        limit: int | None,
    ) -> pd.DataFrame:
        result = frame.copy()
        if start_date:
            start_text = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
            if pd.notna(start_text):
                result = result[pd.to_datetime(result["date"]) >= start_text]
        if end_date:
            end_text = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
            if pd.notna(end_text):
                result = result[pd.to_datetime(result["date"]) <= end_text]
        if limit:
            result = result.tail(limit)
        return result.reset_index(drop=True)

    def _read_csv_with_fallback(self, file_path: Path, skiprows: int) -> pd.DataFrame:
        last_error: Exception | None = None
        for encoding in CSV_ENCODINGS:
            try:
                return pd.read_csv(file_path, encoding=encoding, skiprows=skiprows)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"Unable to decode CSV file: {file_path}") from last_error


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _nan_to_none(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    return value

