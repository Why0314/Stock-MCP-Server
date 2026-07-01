from __future__ import annotations

from stock_mcp.services.daily_plan_service import DailyPlanService


def generate_daily_plan(
    service: DailyPlanService,
    use_watchlist: bool = True,
    use_positions: bool = True,
) -> dict:
    return service.generate_daily_plan(use_watchlist=use_watchlist, use_positions=use_positions)
