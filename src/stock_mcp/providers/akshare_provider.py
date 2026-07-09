from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import re

import akshare as ak
import pandas as pd
import requests

from stock_mcp.models import KlineBar, Quote
from stock_mcp.utils.symbol import infer_market, normalize_symbol, to_digits


@dataclass(frozen=True)
class ProviderFailure(Exception):
    source: str
    message: str

    def __str__(self) -> str:
        return f"{self.source}: {self.message}"


class AKShareProvider:
    _EASTMONEY_QUOTE_URL = "https://push2delay.eastmoney.com/api/qt/stock/get"
    _EASTMONEY_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f168,f169,f170"
    _EASTMONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"

    def get_quotes(self, codes: list[str], as_of: str) -> list[Quote]:
        normalized_codes = [normalize_symbol(code) for code in codes]
        direct_results, direct_failures = self._get_realtime_quotes_direct(normalized_codes=normalized_codes, as_of=as_of)
        results = {item.code: item for item in direct_results}

        missing_etf_codes = [
            to_digits(code)
            for code in normalized_codes
            if infer_market(code) == "ETF" and to_digits(code) not in results
        ]
        if missing_etf_codes:
            try:
                delayed_frame = ak.fund_etf_fund_daily_em()
                delayed_results = self._select_etf_daily_quotes(
                    frame=delayed_frame,
                    codes=missing_etf_codes,
                    as_of=as_of,
                    source="akshare.fund_etf_fund_daily_em(delayed)",
                )
                for item in delayed_results:
                    results[item.code] = item
            except Exception:
                pass

        if results:
            return sorted(results.values(), key=lambda item: item.code)

        message = "; ".join(direct_failures) if direct_failures else "no quote data returned"
        raise ProviderFailure("eastmoney.stock.get", message)

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

    def _get_a_share_spot_frame(self) -> tuple[pd.DataFrame, str]:
        try:
            return ak.stock_zh_a_spot_em(), "akshare.stock_zh_a_spot_em"
        except Exception:
            return ak.stock_zh_a_spot(), "akshare.stock_zh_a_spot"

    def _get_realtime_quotes_direct(self, normalized_codes: list[str], as_of: str) -> tuple[list[Quote], list[str]]:
        if not normalized_codes:
            return [], []

        results: list[Quote] = []
        failures: list[str] = []
        max_workers = min(8, len(normalized_codes)) or 1
        with requests.Session() as session:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self._fetch_single_quote, session, code, as_of): code for code in normalized_codes
                }
                for future in as_completed(future_map):
                    code = future_map[future]
                    try:
                        quote = future.result()
                    except Exception as exc:  # pragma: no cover - network/runtime path
                        failures.append(f"{to_digits(code)}: {exc}")
                        continue
                    if quote is not None:
                        results.append(quote)
                    else:
                        failures.append(f"{to_digits(code)}: empty data")
        return results, failures

    def _fetch_single_quote(self, session: requests.Session, code: str, as_of: str) -> Quote | None:
        response = session.get(
            self._EASTMONEY_QUOTE_URL,
            params={
                "secid": self._secid_for_symbol(code),
                "invt": "2",
                "fltt": "2",
                "fields": self._EASTMONEY_FIELDS,
                "ut": self._EASTMONEY_UT,
            },
            timeout=(3, 5),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("rc") != 0 or not payload.get("data"):
            raise ValueError(payload.get("data") or payload.get("rc") or "unexpected response")
        return self._build_quote_from_eastmoney_payload(payload["data"], code=code, as_of=as_of)

    def _build_quote_from_eastmoney_payload(self, data: dict, code: str, as_of: str) -> Quote:
        market = infer_market(code)
        return Quote(
            code=to_digits(code),
            name=str(data.get("f58") or ""),
            market=market,
            price=_optional_float(data.get("f43")),
            change_pct=_optional_float(data.get("f170")),
            volume=_optional_float(data.get("f47")),
            amount=_optional_float(data.get("f48")),
            turnover_rate=_optional_float(data.get("f168")),
            open_price=_optional_float(data.get("f46")),
            high_price=_optional_float(data.get("f44")),
            low_price=_optional_float(data.get("f45")),
            previous_close=_optional_float(data.get("f60")),
            data_source="eastmoney.stock.get",
            as_of=as_of,
        )

    def _secid_for_symbol(self, symbol: str) -> str:
        normalized = normalize_symbol(symbol)
        digits = to_digits(normalized)
        if normalized.startswith("sh"):
            return f"1.{digits}"
        return f"0.{digits}"

    def _select_quotes(
        self,
        frame: pd.DataFrame,
        codes: list[str],
        market: str,
        as_of: str,
        source: str,
    ) -> list[Quote]:
        canonical_codes = {normalize_symbol(code) for code in codes}
        matched_codes = frame["代码"].astype(str).map(self._canonicalize_quote_code)
        selected = frame[matched_codes.isin(canonical_codes)].copy()
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

    def _canonicalize_quote_code(self, code: str) -> str:
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if len(digits) == 6:
            return normalize_symbol(digits)
        return str(code).strip().lower()


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
