from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_mcp.config_loader import load_named_records
from stock_mcp.services.quote_service import QuoteService
from stock_mcp.services.wyckoff_service import WyckoffService
from stock_mcp.settings import Settings
from stock_mcp.utils.time import now_text


class DailyPlanService:
    def __init__(
        self,
        settings: Settings,
        quote_service: QuoteService,
        wyckoff_service: WyckoffService,
    ) -> None:
        self._settings = settings
        self._quote_service = quote_service
        self._wyckoff_service = wyckoff_service

    def generate_daily_plan(self, use_watchlist: bool = True, use_positions: bool = True) -> dict:
        records: list[dict] = []
        if use_watchlist:
            records.extend(load_named_records(self._settings.config_dir / "watchlist.yaml", "watchlist"))
        if use_positions:
            records.extend(load_named_records(self._settings.config_dir / "positions.yaml", "positions"))

        deduped = {str(item["code"]): item for item in records if "code" in item}
        codes = list(deduped)
        quotes = self._quote_service.get_quotes(codes)
        quote_map = {item["code"]: item for item in quotes.get("items", [])}
        items: list[dict] = []
        analyses = self._analyze_codes(codes)

        for code, record in deduped.items():
            analysis = analyses.get(code, {"code": code, "error": {"message": "analysis unavailable", "source": "daily_plan_service"}})
            if analysis.get("error"):
                items.append(
                    {
                        "code": code,
                        "name": record.get("name", ""),
                        "error": analysis["error"],
                    }
                )
                continue

            action, action_cn = _plan_action_from_stage(analysis["stage"])
            quote = quote_map.get(code, {})
            support_low, support_stop = analysis["support"]
            resistance_low, resistance_high = analysis["resistance"]
            items.append(
                {
                    "code": code,
                    "name": quote.get("name") or record.get("name", ""),
                    "price": quote.get("price"),
                    "stage": analysis["stage"],
                    "action": action,
                    "action_cn": action_cn,
                    "buy_zone": [support_low, round((support_low + resistance_low) / 2, 2)],
                    "stop_loss": support_stop,
                    "take_profit_or_reduce_zone": [resistance_low, resistance_high],
                    "reason": analysis["summary"],
                }
            )

        return {
            "as_of": now_text(),
            "data_status": "ok" if items else "empty",
            "items": items,
        }

    def _analyze_codes(self, codes: list[str]) -> dict[str, dict]:
        if not codes:
            return {}

        results: dict[str, dict] = {}
        max_workers = min(6, len(codes)) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self._wyckoff_service.analyze, code=code): code for code in codes}
            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    results[code] = future.result()
                except Exception as exc:  # pragma: no cover - defensive runtime path
                    results[code] = {"code": code, "error": {"message": str(exc), "source": "daily_plan_service"}}
        return results


def _plan_action_from_stage(stage: str) -> tuple[str, str]:
    mapping = {
        "markup_breakout": ("add", "加仓"),
        "re_accumulation_backup": ("wait", "等待"),
        "markdown_break": ("reduce", "减仓"),
        "range_observation": ("hold", "持有"),
    }
    return mapping.get(stage, ("wait", "等待"))
