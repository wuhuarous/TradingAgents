"""Simulation-first stock selection and auto trading loop.

The goal is not to promise a fixed return. It turns the user's target
annual return into a measurable objective and records every decision for
review and later parameter tuning.
"""
from __future__ import annotations

import json
import math
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tradingAgents.config.settings import settings
from tradingAgents.data.database.data_quality_repo import (
    persist_financial_snapshot_sync,
    persist_market_quotes_sync,
    persist_news_items_sync,
)
from tradingAgents.data.news.quality import standardize_news_item
from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.data.social.sources import fetch_social_sentiment
from tradingAgents.data.social.sentiment import analyze_sentiment
from tradingAgents.data.storage.event_store import append_event, append_events, read_events
from tradingAgents.data.universe import get_universe, list_markets
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.trader.account import VirtualAccount
from tradingAgents.trader.trade_rules import (
    can_buy_at_price,
    can_sell_at_price,
    is_suspended_or_untradable,
    max_order_quantity_by_volume,
)

logger = logging.getLogger(__name__)

DEFAULT_TARGET_ANNUAL_RETURN = 0.50
MEMORY_DIR = Path(settings.memory_dir)
RUN_LOG = MEMORY_DIR / "simulation_runs.jsonl"
LEGACY_RUN_LOG = Path("memory") / "simulation_runs.jsonl"
FULL_MARKET_DEEP_SCAN_LIMIT = 32


@dataclass
class StrategyConfig:
    target_annual_return: float = DEFAULT_TARGET_ANNUAL_RETURN
    min_buy_score: float = 72.0
    max_positions: int = 5
    position_ratio: float = 0.18
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.22


class QualityMomentumStrategy:
    """Quality stock selection with momentum, news sentiment, and review logs."""

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    def candidates(self, market: str = "a_stock", limit: int = 10, timeout_seconds: int = 45) -> list[dict[str, Any]]:
        scored = []
        mkt = Market(market)
        provider = _provider_for(market)
        full_pool = get_universe(market, role="all", limit=None)
        scan_limit = max(int(settings.full_market_deep_scan_limit or FULL_MARKET_DEEP_SCAN_LIMIT), limit * 2)
        pool = _prefilter_full_market(full_pool, market, provider, limit=scan_limit)

        for symbol, name in pool:
            result = self.score_symbol(symbol, name, market, mkt, provider)
            if result:
                scored.append(result)

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored[:limit]

    def fast_candidates(self, market: str = "a_stock", limit: int = 10) -> list[dict[str, Any]]:
        """Return responsive candidates for page loads and global boards.

        Live scoring remains available for explicit simulation runs. Page-load
        candidates must not block on dozens of quote/news/financial requests.
        """
        pool = get_universe(market, role="all", limit=None)
        candidates = [_fast_candidate(symbol, name, market, i) for i, (symbol, name) in enumerate(pool)]
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        return candidates[:limit]

    def all_market_rankings(self, limit: int = 10) -> dict[str, Any]:
        all_candidates: list[dict[str, Any]] = []
        market_summary = []

        for market in list_markets():
            candidates = self.fast_candidates(market=market, limit=limit)
            all_candidates.extend(candidates)
            if candidates:
                market_summary.append({
                    "market": market,
                    "count": len(candidates),
                    "avg_score": round(sum(c.get("final_score", 0) for c in candidates) / len(candidates), 1),
                    "buy_signals": len([c for c in candidates if c.get("action") == "BUY"]),
                    "top_symbol": candidates[0].get("symbol"),
                    "top_score": candidates[0].get("final_score"),
                })

        def quality_score(c: dict[str, Any]) -> float:
            return (
                c.get("scores", {}).get("quality", 0) * 0.36
                + c.get("scores", {}).get("growth", 0) * 0.28
                + c.get("scores", {}).get("valuation", 0) * 0.16
                + c.get("scores", {}).get("sentiment", 0) * 0.08
                - c.get("scores", {}).get("risk", 0) * 0.20
            )

        def potential_score(c: dict[str, Any]) -> float:
            return (
                c.get("scores", {}).get("momentum", 0) * 0.34
                + c.get("scores", {}).get("growth", 0) * 0.26
                + c.get("scores", {}).get("sentiment", 0) * 0.18
                + c.get("scores", {}).get("liquidity", 0) * 0.08
                - c.get("scores", {}).get("risk", 0) * 0.18
            )

        quality = sorted(
            [{**c, "board_score": round(quality_score(c), 1)} for c in all_candidates],
            key=lambda c: c.get("board_score", 0),
            reverse=True,
        )
        potential = sorted(
            [{**c, "board_score": round(potential_score(c), 1)} for c in all_candidates],
            key=lambda c: c.get("board_score", 0),
            reverse=True,
        )

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "markets": market_summary,
            "quality_top10": quality[:limit],
            "potential_top10": potential[:limit],
            "all": sorted(all_candidates, key=lambda c: c.get("final_score", 0), reverse=True)[: limit * 2],
        }

    def score_symbol(
        self,
        symbol: str,
        name: str,
        market: str,
        mkt: Market,
        provider,
    ) -> dict[str, Any] | None:
        try:
            quote = provider.get_realtime_quote(symbol, mkt)
            fin = provider.get_financials(symbol, mkt) or {}
            hist = provider.get_historical(symbol, mkt, period="6mo")
            news = provider.get_news(symbol, mkt, limit=6)
            news.extend(fetch_social_sentiment(symbol, name, market, limit=4))
        except Exception as exc:
            return {
                "symbol": symbol,
                "name": name,
                "market": market,
                "final_score": 0,
                "action": "SKIP",
                "risk_level": "unknown",
                "warnings": [f"数据获取失败: {str(exc)[:80]}"],
            }

        price = float(getattr(quote, "price", 0) or 0)
        if price <= 0:
            return None

        technical = _technical_snapshot(hist)
        sentiment = _sentiment_snapshot(news)
        fundamentals = _fundamental_snapshot(fin)
        _persist_strategy_news(news, market, symbol, name)
        market_quote_event = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            "symbol": symbol,
            "name": getattr(quote, "name", "") or name,
            "source": "strategy_quote",
            "asset_type": "stock",
            "price": price,
            "open": float(getattr(quote, "open", 0) or 0),
            "high": float(getattr(quote, "high", 0) or 0),
            "low": float(getattr(quote, "low", 0) or 0),
            "close": float(getattr(quote, "close", 0) or 0),
            "change_pct": float(getattr(quote, "change_pct", 0) or 0),
            "volume": float(getattr(quote, "volume", 0) or 0),
            "quality_score": 82 if price > 0 else 35,
        }
        append_event("market_quote", market_quote_event)
        persist_market_quotes_sync([market_quote_event])
        persist_financial_snapshot_sync(
            market=market,
            symbol=symbol,
            metrics=fundamentals,
            source="strategy_financials",
            raw_payload=fin,
        )
        append_event("strategy_input", {
            "market": market,
            "symbol": symbol,
            "name": name,
            "quote": {
                "price": price,
                "change_pct": float(getattr(quote, "change_pct", 0) or 0),
                "volume": float(getattr(quote, "volume", 0) or 0),
            },
            "fundamentals": fundamentals,
            "technical": technical,
            "sentiment": sentiment,
        })

        quality_score = _quality_score(fundamentals)
        growth_score = _growth_score(fundamentals)
        valuation_score = _valuation_score(fundamentals)
        momentum_score = _momentum_score(technical)
        sentiment_score = _sentiment_score(sentiment)
        liquidity_score = _liquidity_score(getattr(quote, "volume", 0), price)
        risk_score = _risk_score(fundamentals, technical, sentiment)

        final_score = (
            0.22 * quality_score
            + 0.18 * growth_score
            + 0.12 * valuation_score
            + 0.28 * momentum_score
            + 0.12 * sentiment_score
            + 0.08 * liquidity_score
            - 0.18 * risk_score
        )
        final_score = _clamp(final_score, 0, 100)

        risk_level = _risk_level(risk_score)
        action = _action_from_score(final_score, risk_level, momentum_score, sentiment_score)
        reasons, warnings = _explain(
            final_score,
            fundamentals,
            technical,
            sentiment,
            quality_score,
            growth_score,
            valuation_score,
            momentum_score,
            risk_score,
        )

        result = {
            "symbol": symbol,
            "name": getattr(quote, "name", "") or name,
            "market": market,
            "price": round(price, 3),
            "prev_close": round(float(getattr(quote, "close", 0) or 0), 3),
            "change_pct": round(float(getattr(quote, "change_pct", 0) or 0) * 100, 2),
            "volume": float(getattr(quote, "volume", 0) or 0),
            "amount": float(getattr(quote, "amount", 0) or 0),
            "final_score": round(final_score, 1),
            "action": action,
            "risk_level": risk_level,
            "scores": {
                "quality": round(quality_score, 1),
                "growth": round(growth_score, 1),
                "valuation": round(valuation_score, 1),
                "momentum": round(momentum_score, 1),
                "sentiment": round(sentiment_score, 1),
                "liquidity": round(liquidity_score, 1),
                "risk": round(risk_score, 1),
            },
            "fundamentals": fundamentals,
            "technical": technical,
            "sentiment": sentiment,
            "reasons": reasons,
            "warnings": warnings,
            "trade_plan": {
                "entry": round(price, 3),
                "stop_loss": round(price * (1 - self.config.stop_loss_pct), 3),
                "take_profit": round(price * (1 + self.config.take_profit_pct), 3),
                "position_ratio": self.config.position_ratio if action == "BUY" else 0,
            },
        }
        append_event("training_sample", {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            "symbol": symbol,
            "name": result["name"],
            "action": action,
            "final_score": result["final_score"],
            "risk_level": risk_level,
            "scores": result["scores"],
            "fundamentals": fundamentals,
            "technical": technical,
            "sentiment": sentiment,
            "trade_plan": result["trade_plan"],
            "quality_score": result["final_score"],
            "source": "quality_momentum_strategy",
        })
        _persist_factor_score(result)
        return result

    def run_cycle(self, account: VirtualAccount, market: str = "a_stock") -> dict[str, Any]:
        candidates = self.candidates(market=market, limit=12)
        orders = []
        decisions = []

        for symbol, pos in list(account.positions.items()):
            if pos.get("market", market) != market and market == "a_stock":
                continue
            matched = next((c for c in candidates if c["symbol"] == symbol), None)
            current_price = matched.get("price") if matched else pos.get("current_price", pos.get("avg_cost", 0))
            avg_cost = pos.get("avg_cost", 0)
            pnl_pct = (current_price / avg_cost - 1) if avg_cost else 0
            should_sell = (
                pnl_pct <= -self.config.stop_loss_pct
                or pnl_pct >= self.config.take_profit_pct
                or (matched and matched["final_score"] < 52)
                or (matched and matched["scores"]["sentiment"] < 35)
            )
            if should_sell and matched and is_suspended_or_untradable(
                current_price,
                matched.get("volume", 0),
                matched.get("amount", 0),
            ):
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "停牌或无成交量，模拟规则禁止卖出"})
                continue
            if should_sell and market == "a_stock" and settings.a_share_t1_enabled and int(pos.get("available_quantity", pos.get("quantity", 0)) or 0) <= 0:
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "A股 T+1，可卖数量为 0"})
                continue
            if should_sell and matched and not can_sell_at_price(market, symbol, current_price, matched.get("prev_close", 0), matched.get("name", "")):
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "跌停价附近，模拟规则禁止卖出"})
                continue
            if should_sell and current_price > 0:
                reason = _sell_reason(pnl_pct, matched)
                order = account.sell(symbol, current_price, pos.get("quantity", 0), reason)
                if order:
                    orders.append(order)
                    decisions.append({"symbol": symbol, "action": "SELL", "reason": reason})

        open_symbols = set(account.positions.keys())
        buy_list = [
            c for c in candidates
            if c["action"] == "BUY" and c["symbol"] not in open_symbols
        ]
        free_slots = max(self.config.max_positions - len(account.positions), 0)
        for candidate in buy_list[:free_slots]:
            if is_suspended_or_untradable(candidate["price"], candidate.get("volume", 0), candidate.get("amount", 0)):
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "停牌或无成交量，模拟规则禁止买入",
                })
                continue
            if not can_buy_at_price(
                market,
                candidate["symbol"],
                candidate["price"],
                candidate.get("prev_close", 0),
                candidate.get("name", ""),
            ):
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "涨停价附近，模拟规则禁止买入",
                })
                continue
            budget = account.total_value * self.config.position_ratio
            quantity = _quantity_for_market(budget, candidate["price"], market)
            max_qty = max_order_quantity_by_volume(
                candidate.get("volume", 0),
                settings.max_volume_participation_pct,
                market,
            )
            if market == "a_stock" and max_qty <= 0:
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "成交量不足，无法满足成交量参与上限",
                })
                continue
            if max_qty > 0:
                quantity = min(quantity, max_qty)
            if quantity <= 0:
                continue
            reason = "自动买入: " + "；".join(candidate["reasons"][:3])
            order = account.buy(
                candidate["symbol"],
                candidate["name"],
                candidate["price"],
                quantity,
                reason,
                market=market,
            )
            if order:
                account.positions[candidate["symbol"]]["market"] = market
                orders.append(order)
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY",
                    "score": candidate["final_score"],
                    "reason": reason,
                    "stop_loss": candidate["trade_plan"]["stop_loss"],
                    "take_profit": candidate["trade_plan"]["take_profit"],
                })

        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        run = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            "target_annual_return": self.config.target_annual_return,
            "account": account.to_dict(),
            "orders": orders,
            "decisions": decisions,
            "top_candidates": candidates[:8],
            "review": _review_snapshot(account, self.config),
        }
        _append_run(run)
        append_event("simulation_run", run)
        _persist_factor_scores(candidates, run_id)
        _append_review_backfill(run)
        return run

    async def arun_cycle(self, account: VirtualAccount, market: str = "a_stock") -> dict[str, Any]:
        """Async DB-safe variant used by FastAPI endpoints."""
        candidates = self.candidates(market=market, limit=12)
        orders = []
        decisions = []

        for symbol, pos in list(account.positions.items()):
            if pos.get("market", market) != market and market == "a_stock":
                continue
            matched = next((c for c in candidates if c["symbol"] == symbol), None)
            current_price = matched.get("price") if matched else pos.get("current_price", pos.get("avg_cost", 0))
            avg_cost = pos.get("avg_cost", 0)
            pnl_pct = (current_price / avg_cost - 1) if avg_cost else 0
            should_sell = (
                pnl_pct <= -self.config.stop_loss_pct
                or pnl_pct >= self.config.take_profit_pct
                or (matched and matched["final_score"] < 52)
                or (matched and matched["scores"]["sentiment"] < 35)
            )
            if should_sell and matched and is_suspended_or_untradable(
                current_price,
                matched.get("volume", 0),
                matched.get("amount", 0),
            ):
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "停牌或无成交量，模拟规则禁止卖出"})
                continue
            if should_sell and market == "a_stock" and settings.a_share_t1_enabled and int(pos.get("available_quantity", pos.get("quantity", 0)) or 0) <= 0:
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "A股 T+1，可卖数量为 0"})
                continue
            if should_sell and matched and not can_sell_at_price(market, symbol, current_price, matched.get("prev_close", 0), matched.get("name", "")):
                decisions.append({"symbol": symbol, "action": "SELL_BLOCKED", "reason": "跌停价附近，模拟规则禁止卖出"})
                continue
            if should_sell and current_price > 0:
                reason = _sell_reason(pnl_pct, matched)
                order = await account.asell(symbol, current_price, pos.get("quantity", 0), reason)
                if order:
                    orders.append(order)
                    decisions.append({"symbol": symbol, "action": "SELL", "reason": reason})

        open_symbols = set(account.positions.keys())
        buy_list = [
            c for c in candidates
            if c["action"] == "BUY" and c["symbol"] not in open_symbols
        ]
        free_slots = max(self.config.max_positions - len(account.positions), 0)
        for candidate in buy_list[:free_slots]:
            if is_suspended_or_untradable(candidate["price"], candidate.get("volume", 0), candidate.get("amount", 0)):
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "停牌或无成交量，模拟规则禁止买入",
                })
                continue
            if not can_buy_at_price(
                market,
                candidate["symbol"],
                candidate["price"],
                candidate.get("prev_close", 0),
                candidate.get("name", ""),
            ):
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "涨停价附近，模拟规则禁止买入",
                })
                continue
            budget = account.total_value * self.config.position_ratio
            quantity = _quantity_for_market(budget, candidate["price"], market)
            max_qty = max_order_quantity_by_volume(
                candidate.get("volume", 0),
                settings.max_volume_participation_pct,
                market,
            )
            if market == "a_stock" and max_qty <= 0:
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY_BLOCKED",
                    "score": candidate["final_score"],
                    "reason": "成交量不足，无法满足成交量参与上限",
                })
                continue
            if max_qty > 0:
                quantity = min(quantity, max_qty)
            if quantity <= 0:
                continue
            reason = "自动买入: " + "；".join(candidate["reasons"][:3])
            order = await account.abuy(
                candidate["symbol"],
                candidate["name"],
                candidate["price"],
                quantity,
                market=market,
                reason=reason,
            )
            if order:
                orders.append(order)
                decisions.append({
                    "symbol": candidate["symbol"],
                    "action": "BUY",
                    "score": candidate["final_score"],
                    "reason": reason,
                    "stop_loss": candidate["trade_plan"]["stop_loss"],
                    "take_profit": candidate["trade_plan"]["take_profit"],
                })

        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        run = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            "target_annual_return": self.config.target_annual_return,
            "account": account.to_dict(),
            "orders": orders,
            "decisions": decisions,
            "top_candidates": candidates[:8],
            "review": _review_snapshot(account, self.config),
        }
        _append_run(run)
        append_event("simulation_run", run)
        await _persist_factor_scores_async(candidates, run_id)
        _append_review_backfill(run)
        return run

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = []
        for path in (LEGACY_RUN_LOG, RUN_LOG):
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if rows:
            return rows[-limit:][::-1]
        return read_events("simulation_run", limit=limit)

    def summary(self, account: VirtualAccount) -> dict[str, Any]:
        actual_return = account.total_pnl_pct
        gap = self.config.target_annual_return - actual_return
        return {
            "mode": "simulation",
            "target_annual_return": self.config.target_annual_return,
            "current_return": actual_return,
            "target_gap": gap,
            "principle": "新闻情绪 + 营收成长 + 质量因子 + 趋势确认 + 风险止损",
            "rules": {
                "min_buy_score": self.config.min_buy_score,
                "max_positions": self.config.max_positions,
                "position_ratio": self.config.position_ratio,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
            },
        }


def _provider_for(market: str):
    if market == "a_stock":
        return AStockProvider()
    return YFinanceProvider()


def _prefilter_full_market(
    pool: list[tuple[str, str]],
    market: str,
    provider,
    limit: int,
) -> list[tuple[str, str]]:
    """Reduce a full-market universe to a deep-scoring queue.

    The input universe is still the full market. For A-shares we can fetch one
    cached full quote snapshot, rank every valid listing by liquidity, trend,
    valuation and tradability, then run expensive financial/news/history scoring
    only on the leading names.
    """
    if market != "a_stock":
        return pool[:limit]

    try:
        full_quotes = provider._get_full_list()
    except Exception:
        full_quotes = {}
    if not full_quotes:
        return pool[:limit]

    ranked = []
    for index, (symbol, name) in enumerate(pool):
        quote = full_quotes.get(symbol)
        if not quote:
            continue
        price = float(quote.get("price") or 0)
        prev_close = float(quote.get("close") or 0)
        volume = float(quote.get("volume") or 0)
        amount = float(quote.get("amount") or 0)
        pe = float(quote.get("pe") or 0)
        pb = float(quote.get("pb") or 0)
        if price <= 0 or prev_close <= 0 or volume <= 0:
            continue
        change_pct = (price - prev_close) / prev_close
        turnover_score = min(math.log10(max(amount, volume * price, 1)) * 7, 70)
        momentum_score = _clamp(45 + change_pct * 500, 0, 100)
        valuation_score = 50
        if pe > 0:
            valuation_score += _clamp((45 - pe) / 45, -0.5, 1) * 22
        if pb > 0:
            valuation_score += _clamp((8 - pb) / 8, -0.5, 1) * 16
        seed_bonus = max(0, 10 - index / 800)
        score = turnover_score * 0.38 + momentum_score * 0.34 + valuation_score * 0.22 + seed_bonus
        ranked.append((score, symbol, name))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = [(symbol, name) for _, symbol, name in ranked[:limit]]
    return selected or pool[:limit]


def _fast_candidate(symbol: str, name: str, market: str, index: int) -> dict[str, Any]:
    """Fast cross-market placeholder used by the global ranking board.

    Detailed pages still refresh from live providers. The board must remain
    responsive even when an overseas quote provider rate-limits.
    """
    seed = sum(ord(ch) for ch in f"{market}:{symbol}:{name}")
    momentum = 62 + ((len(symbol) * 7 + index * 5) % 24)
    sentiment = 50 + ((len(name) * 3 + index * 4) % 18)
    quality = 62 + ((seed + index * 7) % 24)
    growth = 56 + ((seed // 3 + index * 9) % 26)
    valuation = 58 + ((index * 6) % 20)
    liquidity = 72 + ((index * 4) % 18)
    risk = max(22, 48 - (quality - 60) * 0.25 + (index % 4) * 3)
    final_score = _clamp(
        0.22 * quality + 0.18 * growth + 0.12 * valuation
        + 0.28 * momentum + 0.12 * sentiment + 0.08 * liquidity - 0.18 * risk,
        0,
        100,
    )
    action = _action_from_score(final_score, _risk_level(risk), momentum, sentiment)
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "price": 0,
        "change_pct": 0,
        "final_score": round(final_score, 1),
        "action": action,
        "risk_level": _risk_level(risk),
        "scores": {
            "quality": round(quality, 1),
            "growth": round(growth, 1),
            "valuation": round(valuation, 1),
            "momentum": round(momentum, 1),
            "sentiment": round(sentiment, 1),
            "liquidity": round(liquidity, 1),
            "risk": round(risk, 1),
        },
        "fundamentals": {},
        "technical": {},
        "sentiment": {"average": 0, "news_count": 0, "positive_count": 0, "negative_count": 0, "items": []},
        "reasons": ["全市场快速候选画像", "点进深度分析后刷新实时行情、财务和新闻"],
            "warnings": ["榜单使用快速候选画像，不直接作为买入依据；实时数据以深度分析和模拟训练结果为准"],
            "trade_plan": {
                "entry": 0,
                "stop_loss": 0,
                "take_profit": 0,
                "position_ratio": 0,
            },
    }


def _fundamental_snapshot(fin: dict[str, Any]) -> dict[str, float]:
    return {
        "pe": _first_number(fin, "pe", "pe_ratio", "forward_pe"),
        "pb": _first_number(fin, "pb", "pb_ratio"),
        "roe": _first_number(fin, "roe"),
        "revenue_growth": _first_number(fin, "revenue_growth"),
        "net_profit_growth": _first_number(fin, "net_profit_growth"),
        "gross_margin": _first_number(fin, "gross_margin"),
        "net_margin": _first_number(fin, "net_margin"),
        "debt_to_equity": _first_number(fin, "debt_to_equity"),
    }


def _technical_snapshot(hist: pd.DataFrame) -> dict[str, float | bool]:
    if hist is None or hist.empty:
        return {
            "return_20d": 0,
            "return_60d": 0,
            "volatility_20d": 0,
            "volume_ratio": 1,
            "above_ma20": False,
            "ma20_above_ma60": False,
            "breakout_20d": False,
        }

    close = _series(hist, "收盘", "Close", "close")
    volume = _series(hist, "成交量", "Volume", "volume")
    if close.empty:
        return {}

    latest = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else latest
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else ma20
    ret20 = (latest / float(close.iloc[-20]) - 1) if len(close) >= 20 and close.iloc[-20] else 0
    ret60 = (latest / float(close.iloc[-60]) - 1) if len(close) >= 60 and close.iloc[-60] else ret20
    returns = close.pct_change().dropna()
    vol20 = float(returns.tail(20).std() * math.sqrt(252)) if len(returns) >= 20 else 0
    vol_ratio = 1.0
    if not volume.empty and len(volume) >= 20:
        avg_vol = float(volume.tail(20).mean())
        vol_ratio = float(volume.iloc[-1] / avg_vol) if avg_vol else 1

    high_20 = float(close.tail(20).max()) if len(close) >= 20 else latest
    return {
        "return_20d": round(ret20, 4),
        "return_60d": round(ret60, 4),
        "volatility_20d": round(vol20, 4),
        "volume_ratio": round(vol_ratio, 3),
        "above_ma20": latest > ma20,
        "ma20_above_ma60": ma20 >= ma60,
        "breakout_20d": latest >= high_20 * 0.995,
    }


def _sentiment_snapshot(news_items: list[Any]) -> dict[str, Any]:
    scored = []
    for item in news_items or []:
        title = getattr(item, "title", "") or ""
        content = getattr(item, "content", "") or ""
        text = f"{title} {content}".strip()
        if not text:
            continue
        try:
            score = float(analyze_sentiment(text))
        except Exception:
            score = 0.0
        scored.append({
            "title": title[:120],
            "source": getattr(item, "source", "") or "news",
            "score": round(score, 3),
        })
    avg = sum(i["score"] for i in scored) / len(scored) if scored else 0
    return {
        "average": round(avg, 3),
        "news_count": len(scored),
        "positive_count": len([i for i in scored if i["score"] > 0.15]),
        "negative_count": len([i for i in scored if i["score"] < -0.15]),
        "items": scored[:5],
    }


def _persist_strategy_news(news_items: list[Any], market: str, symbol: str, name: str) -> None:
    events = []
    for item in news_items or []:
        title = getattr(item, "title", "") or ""
        content = getattr(item, "content", "") or ""
        text = f"{title} {content}".strip()
        try:
            score = float(analyze_sentiment(text)) if text else 0.0
        except Exception:
            score = 0.0
        try:
            events.append(standardize_news_item(
                item,
                market=market,
                symbol=symbol,
                sentiment=score,
                relevance_query=f"{name} {symbol}",
            ))
        except Exception:
            continue
    if events:
        append_events("news", events)
        persist_news_items_sync(events)


def _quality_score(f: dict[str, float]) -> float:
    roe = f.get("roe", 0)
    gross = f.get("gross_margin", 0)
    net = f.get("net_margin", 0)
    debt = f.get("debt_to_equity", 0)
    score = 45
    score += _scale(roe, 0.08, 0.25) * 30
    score += _scale(gross, 0.2, 0.6) * 12
    score += _scale(net, 0.08, 0.25) * 10
    if debt:
        score -= _scale(debt, 80, 250) * 18
    return _clamp(score, 0, 100)


def _growth_score(f: dict[str, float]) -> float:
    revenue = f.get("revenue_growth", 0)
    profit = f.get("net_profit_growth", 0)
    score = 45 + _scale(revenue, 0.03, 0.35) * 35 + _scale(profit, 0.03, 0.4) * 20
    return _clamp(score, 0, 100)


def _valuation_score(f: dict[str, float]) -> float:
    pe = f.get("pe", 0)
    pb = f.get("pb", 0)
    score = 55
    if pe > 0:
        score += _scale(45 - pe, 0, 35) * 25
    if pb > 0:
        score += _scale(8 - pb, 0, 7) * 20
    return _clamp(score, 0, 100)


def _momentum_score(t: dict[str, Any]) -> float:
    score = 35
    score += _scale(t.get("return_20d", 0), -0.05, 0.18) * 30
    score += _scale(t.get("return_60d", 0), -0.08, 0.35) * 25
    score += 8 if t.get("above_ma20") else -8
    score += 8 if t.get("ma20_above_ma60") else -6
    score += 6 if t.get("breakout_20d") else 0
    score += _scale(t.get("volume_ratio", 1), 0.8, 1.8) * 8
    return _clamp(score, 0, 100)


def _sentiment_score(s: dict[str, Any]) -> float:
    avg = s.get("average", 0)
    score = 50 + avg * 70
    score += min(s.get("positive_count", 0), 3) * 4
    score -= min(s.get("negative_count", 0), 3) * 6
    return _clamp(score, 0, 100)


def _liquidity_score(volume: float, price: float) -> float:
    turnover = max(volume * price, 0)
    if turnover <= 0:
        return 40
    return _clamp(35 + math.log10(turnover + 1) * 7, 0, 100)


def _risk_score(f: dict[str, float], t: dict[str, Any], s: dict[str, Any]) -> float:
    score = 25
    if f.get("roe", 0) < 0.05:
        score += 15
    if f.get("revenue_growth", 0) < -0.05:
        score += 18
    if f.get("pe", 0) > 80:
        score += 12
    if t.get("volatility_20d", 0) > 0.55:
        score += 18
    if not t.get("above_ma20"):
        score += 10
    if s.get("average", 0) < -0.25:
        score += 20
    score += s.get("negative_count", 0) * 4
    return _clamp(score, 0, 100)


def _risk_level(score: float) -> str:
    if score >= 72:
        return "extreme"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _action_from_score(score: float, risk_level: str, momentum: float, sentiment: float) -> str:
    if risk_level == "extreme":
        return "NO_ACTION"
    if score >= 72 and momentum >= 58 and sentiment >= 42:
        return "BUY"
    if score >= 60:
        return "WATCH"
    if score <= 42:
        return "AVOID"
    return "HOLD"


def _explain(
    final_score: float,
    f: dict[str, float],
    t: dict[str, Any],
    s: dict[str, Any],
    quality: float,
    growth: float,
    valuation: float,
    momentum: float,
    risk: float,
) -> tuple[list[str], list[str]]:
    reasons = []
    warnings = []
    if quality >= 65:
        reasons.append(f"质量因子较强，ROE {f.get('roe', 0) * 100:.1f}%")
    if growth >= 65:
        reasons.append(f"营收/利润成长较好，营收增速 {f.get('revenue_growth', 0) * 100:.1f}%")
    if valuation >= 65:
        reasons.append(f"估值相对可接受，PE {f.get('pe', 0):.1f}，PB {f.get('pb', 0):.1f}")
    if momentum >= 65:
        reasons.append(f"趋势确认，20日收益 {t.get('return_20d', 0) * 100:.1f}%")
    if s.get("average", 0) > 0.1:
        reasons.append(f"新闻情绪偏正面，平均情绪 {s.get('average', 0):.2f}")
    if final_score >= 72:
        reasons.append("综合分达到模拟买入阈值")

    if risk >= 55:
        warnings.append("风险分偏高，需降低仓位或等待确认")
    if s.get("negative_count", 0) > 0:
        warnings.append(f"存在 {s.get('negative_count')} 条偏负面新闻")
    if not t.get("above_ma20"):
        warnings.append("价格未站上 MA20，买点质量不足")
    if not reasons:
        reasons.append("暂未形成高胜率共振信号")
    return reasons, warnings


def _sell_reason(pnl_pct: float, matched: dict[str, Any] | None) -> str:
    if pnl_pct <= -0.08:
        return f"自动卖出: 触发止损，收益 {pnl_pct * 100:.1f}%"
    if pnl_pct >= 0.22:
        return f"自动卖出: 达到止盈，收益 {pnl_pct * 100:.1f}%"
    if matched and matched["scores"]["sentiment"] < 35:
        return "自动卖出: 舆情明显转弱"
    return "自动卖出: 综合评分跌破持仓阈值"


def _review_snapshot(account: VirtualAccount, config: StrategyConfig) -> dict[str, Any]:
    ret = account.total_pnl_pct
    return {
        "current_return": round(ret, 4),
        "target_annual_return": config.target_annual_return,
        "target_progress": round(ret / config.target_annual_return, 4) if config.target_annual_return else 0,
        "positions": len(account.positions),
        "lessons": [
            "记录每次买卖的分数、新闻情绪与营收指标，后续用实际收益校准权重",
            "若回撤扩大，优先提高买入阈值或降低单仓比例，而不是追加仓位",
        ],
    }


def _append_run(run: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False) + "\n")


def _persist_factor_score(candidate: dict[str, Any], run_id: str = "") -> None:
    try:
        asyncio.get_running_loop()
        return
    except RuntimeError:
        pass
    try:
        from tradingAgents.data.database.factor_repo import FactorScoreRepository

        asyncio.run(FactorScoreRepository().add_score(candidate, run_id=run_id))
    except Exception as exc:
        logger.debug("Factor score persistence failed for %s: %s", candidate.get("symbol"), exc)


def _persist_factor_scores(candidates: list[dict[str, Any]], run_id: str) -> None:
    for candidate in candidates:
        _persist_factor_score(candidate, run_id=run_id)


async def _persist_factor_scores_async(candidates: list[dict[str, Any]], run_id: str) -> None:
    try:
        from tradingAgents.data.database.factor_repo import FactorScoreRepository
        from tradingAgents.data.database.data_quality_repo import DataQualityRepository

        factor_repo = FactorScoreRepository()
        data_repo = DataQualityRepository()
        quote_rows = []
        for candidate in candidates:
            await factor_repo.add_score(candidate, run_id=run_id)
            quote_rows.append({
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "market": candidate.get("market", ""),
                "symbol": candidate.get("symbol", ""),
                "name": candidate.get("name", ""),
                "source": "strategy_candidate",
                "asset_type": "stock",
                "price": candidate.get("price", 0),
                "change_pct": (candidate.get("change_pct", 0) or 0) / 100,
                "quality_score": 82 if candidate.get("price") else 35,
            })
            await data_repo.add_financial_snapshot(
                market=str(candidate.get("market", "")),
                symbol=str(candidate.get("symbol", "")),
                metrics=candidate.get("fundamentals") or {},
                source="strategy_candidate",
                raw_payload=candidate.get("fundamentals") or {},
            )
        if quote_rows:
            await data_repo.add_market_quotes(quote_rows)
    except Exception as exc:
        logger.debug("Async factor score persistence failed for run %s: %s", run_id, exc)


def _append_review_backfill(run: dict[str, Any]) -> None:
    """Persist a first review sample immediately after a simulated cycle.

    Later jobs can enrich the same run with 1D/5D/20D returns.
    """
    for candidate in run.get("top_candidates", []):
        append_event("review_backfill", {
            "run_id": run.get("run_id"),
            "created_at": run.get("created_at"),
            "market": run.get("market"),
            "symbol": candidate.get("symbol"),
            "name": candidate.get("name"),
            "action": candidate.get("action"),
            "entry_price": candidate.get("price"),
            "score": candidate.get("final_score"),
            "sentiment_average": candidate.get("sentiment", {}).get("average"),
            "quality_score": candidate.get("scores", {}).get("quality"),
            "momentum_score": candidate.get("scores", {}).get("momentum"),
            "horizon": "T+0",
            "return_pct": 0,
            "status": "pending_1d_5d_20d",
        })


def _quantity_for_market(budget: float, price: float, market: str) -> int:
    if price <= 0 or budget <= 0:
        return 0
    lot = 100 if market == "a_stock" else 1
    qty = int(budget / price / lot) * lot
    return max(qty, lot) if budget >= price * lot else 0


def _series(df: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").dropna()
    return pd.Series(dtype=float)


def _first_number(data: dict[str, Any], *keys: str) -> float:
    for key in keys:
        val = data.get(key)
        try:
            if val is not None and val != "":
                return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0


def _scale(value: float, low: float, high: float) -> float:
    if high == low:
        return 0
    return _clamp((value - low) / (high - low), 0, 1)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
