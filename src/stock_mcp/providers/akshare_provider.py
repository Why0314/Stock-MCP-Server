from __future__ import annotations

from dataclasses import dataclass
import re

import akshare as ak
import pandas as pd

from stock_mcp.models import KlineBar, Quote
from stock_mcp.utils.symbol import infer_market, normalize_symbol, to_digits


@dataclass(frozen=True)
class ProviderFailure(Exception):
    source: str
    message: str

    def __str__(self) -> str:
        return f"{self.source}: {self.message}"


class AKShareProvider:
    def get_quotes(self, codes: list[str], as_of: str) -> list[Quote]:
        a_codes = [normalize_symbol(code) for code in codes if infer_market(code) in {"A", "BJ"}]
        etf_codes = [to_digits(code) for code in codes if infer_market(code) == "ETF"]
        results: list[Quote] = []

        if a_codes:
            try:
                a_frame = ak.stock_zh_a_spot()
                results.extend(self._select_quotes(a_frame, a_codes, market="A", as_of=as_of, source="akshare.stock_zh_a_spot"))
            except Exception as exc:  # pragma: no cover - network/runtime path
                raise ProviderFailure("akshare.stock_zh_a_spot", str(exc)) from exc

        if etf_codes:
            try:
                etf_frame = ak.fund_etf_spot_em()
                results.extend(
                    self._select_quotes(
                        etf_frame,
                        etf_codes,
                        market="ETF",
                        as_of=as_of,
                        source="akshare.fund_etf_spot_em",
                    )
                )
            except Exception as exc:  # pragma: no cover - network/runtime path
                try:
                    delayed_frame = ak.fund_etf_fund_daily_em()
                    results.extend(
                        self._select_etf_daily_quotes(
                            frame=delayed_frame,
                            codes=etf_codes,
                            as_of=as_of,
                            source="akshare.fund_etf_fund_daily_em(delayed)",
                        )
                    )
                except Exception as delayed_exc:  # pragma: no cover - network/runtime path
                    raise ProviderFailure(
                        "akshare.fund_etf_spot_em",
                        f"{exc}; delayed fallback failed: {delayed_exc}",
                    ) from delayed_exc

        return sorted(results, key=lambda item: item.code)

    def get_kline(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str,
        name: str = "",
    ) -> list[KlineBar]:
        digits = to_digits(code)
        market = infer_market(code)

        try:
            if market == "ETF":
                try:
                    frame = ak.fund_etf_hist_em(symbol=digits, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
                    source = "akshare.fund_etf_hist_em"
                except Exception:
                    frame = ak.fund_etf_hist_sina(symbol=normalize_symbol(code),)
                    source = "akshare.fund_etf_hist_sina"
                    frame = self._filter_sina_etf_hist(frame=frame, start_date=start_date, end_date=end_date)
            else:
                frame = ak.stock_zh_a_hist(symbol=digits, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
                source = "akshare.stock_zh_a_hist"
        except Exception as exc:  # pragma: no cover - network/runtime path
            raise ProviderFailure(f"akshare.{market.lower()}_hist", str(exc)) from exc

        if frame.empty:
            return []

        return self._build_kline_items(frame=frame, code=digits, name=name, source=source)

    def _select_quotes(
        self,
        frame: pd.DataFrame,
        codes: list[str],
        market: str,
        as_of: str,
        source: str,
    ) -> list[Quote]:
        selected = frame[frame["代码"].astype(str).isin(codes)].copy()
        return [
            Quote(
                code=to_digits(str(row["代码"])),
                name=str(row["名称"]),
                market=market,
                price=_optional_float(row.get("最新价")),
                change_pct=_optional_float(row.get("涨跌幅")),
                volume=_optional_float(row.get("成交量")),
                amount=_optional_float(row.get("成交额")),
                turnover_rate=_optional_float(row.get("换手率")),
                open_price=_optional_float(row.get("今开") if "今开" in row else row.get("开盘价")),
                high_price=_optional_float(row.get("最高") if "最高" in row else row.get("最高价")),
                low_price=_optional_float(row.get("最低") if "最低" in row else row.get("最低价")),
                previous_close=_optional_float(row.get("昨收")),
                data_source=source,
                as_of=as_of,
            )
            for row in selected.to_dict("records")
        ]

    def _select_etf_daily_quotes(
        self,
        frame: pd.DataFrame,
        codes: list[str],
        as_of: str,
        source: str,
    ) -> list[Quote]:
        selected = frame[frame["基金代码"].astype(str).isin(codes)].copy()
        date_columns = [column for column in selected.columns if re.match(r"\d{4}-\d{2}-\d{2}-单位净值", str(column))]
        latest_date = date_columns[0].split("-单位净值")[0] if date_columns else as_of.split(" ")[0]
        return [
            Quote(
                code=str(row["基金代码"]),
                name=str(row["基金简称"]),
                market="ETF",
                price=_safe_float(row.get("市价")),
                change_pct=_safe_percent(row.get("增长率")),
                volume=None,
                amount=None,
                turnover_rate=None,
                open_price=None,
                high_price=None,
                low_price=None,
                previous_close=None,
                data_source=source,
                as_of=latest_date,
            )
            for row in selected.to_dict("records")
        ]

    def _build_kline_items(
        self,
        frame: pd.DataFrame,
        code: str,
        name: str,
        source: str,
    ) -> list[KlineBar]:
        return [
            KlineBar(
                code=code,
                name=name,
                date=_normalize_date(row["日期"] if "日期" in row else row["date"]),
                open_price=float(row["开盘"] if "开盘" in row else row["open"]),
                high_price=float(row["最高"] if "最高" in row else row["high"]),
                low_price=float(row["最低"] if "最低" in row else row["low"]),
                close_price=float(row["收盘"] if "收盘" in row else row["close"]),
                previous_close=None,
                volume=_optional_float(row.get("成交量", row.get("volume"))),
                amount=_optional_float(row.get("成交额", row.get("amount"))),
                turnover_rate=_optional_float(row.get("换手率")),
                data_source=source,
            )
            for row in frame.to_dict("records")
        ]

    def _filter_sina_etf_hist(self, frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        result = frame.copy()
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        start = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        if pd.notna(start):
            result = result[result["date"] >= start]
        if pd.notna(end):
            result = result[result["date"] <= end]
        return result.reset_index(drop=True)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _safe_percent(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.notna(timestamp):
        return timestamp.strftime("%Y-%m-%d")
    return str(value)
