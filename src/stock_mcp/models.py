from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    market: str
    price: float | None
    change_pct: float | None
    volume: float | None
    amount: float | None
    turnover_rate: float | None
    open_price: float | None
    high_price: float | None
    low_price: float | None
    previous_close: float | None
    data_source: str
    as_of: str


@dataclass(frozen=True)
class KlineBar:
    code: str
    name: str
    date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    previous_close: float | None
    volume: float | None
    amount: float | None
    turnover_rate: float | None = None
    data_source: str = "unknown"


@dataclass(frozen=True)
class FinancialStatementRow:
    symbol: str
    statement_file: str
    report_date: str
    publish_date: str
    statement_format: str
    values: dict[str, Any]
    source: str = "csv"


@dataclass(frozen=True)
class DataError:
    source: str
    message: str
    code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

