"""Backfill post-trade review returns for simulated decisions."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingAgents.data.storage.event_store import append_event
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider

REVIEW_HORIZONS = {
    "1D": 1,
    "5D": 5,
    "20D": 20,
}


def backfill_review_returns(
    runs: list[dict[str, Any]],
    *,
    force_latest: bool = False,
) -> dict[str, Any]:
    """Backfill due 1D/5D/20D returns for prior simulated candidates."""
    rows = []
    provider_cache = {}
    now = datetime.now()

    for run in runs:
        market = run.get("market", "a_stock")
        provider = provider_cache.get(market)
        if provider is None:
            provider = _provider_for(market)
            provider_cache[market] = provider

        created_at = _parse_dt(run.get("created_at"))
        due_horizons = ["latest"] if force_latest else _due_horizons(created_at, now)
        if not due_horizons:
            continue

        for candidate in run.get("top_candidates", []):
            symbol = candidate.get("symbol")
            entry = float(candidate.get("price") or 0)
            if not symbol or entry <= 0:
                continue
            current_price = _current_price(provider, symbol, market)
            if current_price <= 0:
                continue
            ret = current_price / entry - 1
            for horizon in due_horizons:
                rows.append(append_event("review_backfill", {
                    "run_id": run.get("run_id"),
                    "created_at": run.get("created_at"),
                    "market": market,
                    "symbol": symbol,
                    "name": candidate.get("name"),
                    "action": candidate.get("action"),
                    "entry_price": round(entry, 4),
                    "current_price": round(current_price, 4),
                    "score": candidate.get("final_score"),
                    "sentiment_average": candidate.get("sentiment", {}).get("average"),
                    "quality_score": candidate.get("scores", {}).get("quality"),
                    "momentum_score": candidate.get("scores", {}).get("momentum"),
                    "horizon": horizon,
                    "return_pct": round(ret, 4),
                    "status": "backfilled",
                }))

    return {
        "status": "completed",
        "count": len(rows),
        "rows": rows[:50],
        "force_latest": force_latest,
    }


def _due_horizons(created_at: datetime | None, now: datetime) -> list[str]:
    if created_at is None:
        return []
    elapsed_days = max((now - created_at).days, 0)
    return [label for label, days in REVIEW_HORIZONS.items() if elapsed_days >= days]


def _provider_for(market: str):
    if market == "a_stock":
        return AStockProvider()
    return YFinanceProvider()


def _current_price(provider, symbol: str, market: str) -> float:
    try:
        quote = provider.get_realtime_quote(symbol, Market(market))
        return float(getattr(quote, "price", 0) or 0)
    except Exception:
        return 0


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
