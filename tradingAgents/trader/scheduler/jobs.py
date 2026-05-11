"""定时任务实现 — 盘前分析 / 开盘执行 / 盘中监控 / 收盘结算"""
import asyncio
import logging
from datetime import datetime

from tradingAgents.config.settings import settings
from tradingAgents.data.universe import get_universe
from tradingAgents.engine.dataflows.interface import Market
from tradingAgents.engine.dataflows.yfinance import YFinanceProvider
from tradingAgents.data.providers.a_stock import AStockProvider
from tradingAgents.utils.timezone import CN_TZ

logger = logging.getLogger(__name__)


def _now_cn_iso() -> str:
    return datetime.now(tz=CN_TZ).isoformat()

def _run_async(coro, timeout: int = 5):
    """Run async coroutine from APScheduler background thread."""
    async def _with_timeout():
        return await asyncio.wait_for(coro, timeout=timeout)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_with_timeout())
    import concurrent.futures
    future = asyncio.run_coroutine_threadsafe(_with_timeout(), loop)
    return future.result(timeout=timeout + 1)


def _safe_run_async(coro, fallback, timeout: int = 5):
    try:
        return _run_async(coro, timeout=timeout)
    except Exception as e:
        logger.warning("Async scheduler dependency unavailable, using fallback: %s", e)
        return fallback


def pre_market_analysis_job() -> dict:
    """盘前分析：对监视列表运行 AI 多智能体分析，生成交易计划并持久化到 PostgreSQL"""
    if not settings.scheduler_live_data_enabled:
        return {
            "status": "completed",
            "timestamp": _now_cn_iso(),
            "candidates": 0,
            "plans_generated": 0,
            "results": [],
            "mode": "dry_run",
            "message": "scheduler_live_data_enabled=false; skipped external data scan",
        }

    results = []
    candidates = []

    a_provider = AStockProvider()
    for sym, _ in get_universe("a_stock", role="watchlist"):
        try:
            q = a_provider.get_realtime_quote(sym, Market.A)
            if q.price > 0 and abs(q.change_pct) > 0.01:
                candidates.append({"symbol": sym, "market": "a_stock", "change": q.change_pct, "name": q.name})
        except Exception as e:
            logger.debug("Pre-market A-stock %s failed: %s", sym, e)

    us_provider = YFinanceProvider()
    for sym, _ in get_universe("hk_stock", role="watchlist"):
        try:
            q = us_provider.get_realtime_quote(sym, Market.HK)
            if q.price > 0 and abs(q.change_pct) > 0.01:
                candidates.append({"symbol": sym, "market": "hk_stock", "change": q.change_pct, "name": q.name})
        except Exception as e:
            logger.debug("Pre-market HK %s failed: %s", sym, e)

    for sym, _ in get_universe("us_stock", role="watchlist"):
        try:
            q = us_provider.get_realtime_quote(sym, Market.US)
            if q.price > 0 and abs(q.change_pct) > 0.01:
                candidates.append({"symbol": sym, "market": "us_stock", "change": q.change_pct, "name": q.name})
        except Exception as e:
            logger.debug("Pre-market US %s failed: %s", sym, e)

    candidates.sort(key=lambda x: abs(x["change"]), reverse=True)

    plans_added = 0
    for c in candidates[:5]:
        try:
            from tradingAgents.engine.graph.workflow import run_analysis
            result = run_analysis(c["symbol"], c["market"])
            decision = result.get("trader_decision", {})
            if decision.get("action") in ("buy", "hold"):
                _run_async(_save_plan(
                    symbol=c["symbol"], name=c["name"], market=c["market"],
                    action=decision.get("action", "hold"),
                    confidence=decision.get("confidence", 0),
                    price=decision.get("price", 0),
                    quantity=decision.get("quantity", 0),
                    reason=decision.get("reason", ""),
                ))
                plans_added += 1
            results.append({"symbol": c["symbol"], "decision": decision.get("action"), "confidence": decision.get("confidence")})
        except Exception as e:
            logger.warning("Analysis failed for %s: %s", c["symbol"], e)

    logger.info("Pre-market analysis: %d candidates, %d plans saved to DB", len(candidates), plans_added)
    return {
        "status": "completed",
        "timestamp": _now_cn_iso(),
        "candidates": len(candidates),
        "plans_generated": plans_added,
        "results": results,
    }


async def _save_plan(symbol, name, market, action, confidence, price, quantity, reason):
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    await repo.add_plan(
        symbol=symbol, name=name, market=market, action=action,
        confidence=confidence, price=price, quantity=quantity,
        reason=reason, status="pending",
    )


def market_open_trading_job() -> dict:
    """开盘交易：从 DB 读取待执行计划，通过 VirtualAccount 执行交易"""
    plans = _safe_run_async(_get_pending_plans(), [])
    if not plans:
        return {"status": "no_plans", "timestamp": _now_cn_iso()}

    account = _safe_run_async(_get_or_create_account(), None)
    if not account:
        return {"status": "no_plans", "timestamp": _now_cn_iso()}
    positions = _safe_run_async(_get_positions(account["id"]), [])
    total_position = sum(p["quantity"] * p["current_price"] for p in positions)
    capital = account["initial_capital"]

    executed = []
    remaining = []

    for plan in plans:
        order_value = plan.get("quantity", 0) * plan.get("price", 0)
        if total_position + order_value > capital * settings.total_position_max_ratio:
            logger.info("Position ratio limit reached, skipping %s", plan["symbol"])
            remaining.append(plan)
            continue
        if order_value > capital * settings.single_position_max_ratio:
            logger.info("Single position limit exceeded for %s", plan["symbol"])
            plan["quantity"] = int(capital * settings.single_position_max_ratio / max(plan["price"], 0.01))
            if plan["quantity"] <= 0:
                remaining.append(plan)
                continue

        result = _safe_run_async(_execute_buy(
            symbol=plan["symbol"], name=plan["name"], price=plan["price"],
            quantity=plan["quantity"], market=plan.get("market", "a_stock"),
            reason=plan.get("reason", ""),
        ), None)
        if result:
            total_position += order_value
            executed.append({
                "symbol": plan["symbol"], "name": plan["name"],
                "action": "buy", "price": plan["price"],
                "quantity": plan["quantity"], "reason": plan.get("reason", ""),
                "executed_at": _now_cn_iso(),
            })
            _safe_run_async(_mark_plan_done(plan["id"]), None)
        else:
            remaining.append(plan)

    logger.info("Market open trading: %d executed, %d deferred", len(executed), len(remaining))
    return {
        "status": "executed",
        "timestamp": _now_cn_iso(),
        "executed": executed,
        "deferred": [{"symbol": p["symbol"], "reason": p.get("reason", "")} for p in remaining],
        "total_position": total_position,
    }


def simulation_auto_cycle_job() -> dict:
    """Run one simulated strategy cycle without manual clicking."""
    if not settings.auto_simulation_enabled:
        return {
            "status": "disabled",
            "timestamp": _now_cn_iso(),
            "message": "auto_simulation_enabled=false",
        }
    if not _is_cn_trading_window():
        return {
            "status": "skipped",
            "timestamp": _now_cn_iso(),
            "message": "outside A-share trading window",
        }

    async def _run():
        from tradingAgents.trader.account import VirtualAccount
        from tradingAgents.trader.auto_strategy import QualityMomentumStrategy

        account = VirtualAccount(persist=True)
        await account.aload(force=True)
        await account.arefresh_market_prices()
        return await QualityMomentumStrategy().arun_cycle(
            account,
            market=settings.auto_simulation_market,
        )

    run = _safe_run_async(_run(), None, timeout=180)
    if not run:
        return {
            "status": "failed",
            "timestamp": _now_cn_iso(),
            "message": "simulation cycle failed",
        }
    return {
        "status": "completed",
        "timestamp": _now_cn_iso(),
        "market": run.get("market"),
        "run_id": run.get("run_id"),
        "orders": len(run.get("orders") or []),
        "decisions": len(run.get("decisions") or []),
        "positions": run.get("review", {}).get("positions", 0),
        "current_return": run.get("review", {}).get("current_return", 0),
    }


def candidate_pool_refresh_job() -> dict:
    """Refresh full-market lightweight candidate pool for simulation runs."""
    try:
        from tradingAgents.data.database.candidate_pool import refresh_candidate_pool

        result = refresh_candidate_pool(market="a_stock", max_candidates=800)
        result["timestamp"] = _now_cn_iso()
        return result
    except Exception as exc:
        logger.warning("Candidate pool refresh failed: %s", exc)
        return {
            "status": "failed",
            "timestamp": _now_cn_iso(),
            "error": str(exc)[:300],
        }


def news_refresh_job() -> dict:
    """Refresh market news hourly into standardized storage."""
    from tradingAgents.server.routers.news_router import refresh_news_feed

    markets = ("a_stock", "hk_stock", "us_stock")
    result = {
        "status": "completed",
        "timestamp": _now_cn_iso(),
        "interval": "1h",
        "markets": {},
    }
    for market in markets:
        try:
            items = refresh_news_feed(market=market, limit=60)
            result["markets"][market] = {
                "count": len(items),
                "latest": items[0].get("published_at") if items else None,
                "sources": sorted({str(item.get("source") or "") for item in items if item.get("source")})[:8],
            }
        except Exception as exc:
            logger.warning("News refresh failed for %s: %s", market, exc)
            result["markets"][market] = {
                "count": 0,
                "error": str(exc)[:300],
            }
            result["status"] = "partial"
    return result


async def _get_pending_plans():
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    plans = await repo.get_pending_plans()
    return [
        {
            "id": p.id, "symbol": p.symbol, "name": p.name,
            "market": p.market, "action": p.action,
            "confidence": p.confidence, "price": p.price,
            "quantity": p.quantity, "reason": p.reason,
        }
        for p in plans
    ]


async def _get_positions(account_id):
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    positions = await repo.get_positions(account_id)
    return [
        {
            "symbol": p.symbol, "name": p.name, "market": p.market,
            "quantity": p.quantity, "avg_cost": p.avg_cost,
            "current_price": p.current_price,
        }
        for p in positions
    ]


async def _get_or_create_account():
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    acc = await repo.get_or_create()
    return {"id": acc.id, "initial_capital": acc.initial_capital, "cash": acc.cash}


async def _execute_buy(symbol, name, price, quantity, market, reason):
    from tradingAgents.trader.account import VirtualAccount
    acc = VirtualAccount()
    return await acc.abuy(symbol, name, price, quantity, market, reason)


async def _execute_sell(symbol, price, quantity, reason):
    from tradingAgents.trader.account import VirtualAccount
    acc = VirtualAccount()
    return await acc.asell(symbol, price, quantity, reason)


async def _mark_plan_done(plan_id):
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    await repo.mark_plan_executed(plan_id)


def intraday_monitoring_job() -> dict:
    """盘中监控：从 DB 读取持仓，检查止损/止盈"""
    if not _is_cn_trading_window():
        return {"status": "skipped", "timestamp": _now_cn_iso(), "message": "outside A-share trading window"}
    account = _safe_run_async(_get_or_create_account(), None)
    if not account:
        return {"status": "no_positions", "timestamp": _now_cn_iso()}
    positions = _safe_run_async(_get_positions(account["id"]), [])
    if not positions:
        return {"status": "no_positions", "timestamp": _now_cn_iso()}

    alerts = []
    a_provider = AStockProvider()
    us_provider = YFinanceProvider()

    for pos in positions:
        try:
            market = pos.get("market", "a_stock")
            mkt = Market.A if market == "a_stock" else (Market.HK if market == "hk_stock" else Market.US)
            provider = a_provider if market == "a_stock" else us_provider
            quote = provider.get_realtime_quote(pos["symbol"], mkt)
            if quote.price <= 0:
                continue

            pnl_pct = (quote.price / pos["avg_cost"] - 1) if pos["avg_cost"] > 0 else 0
            alert = None

            if pnl_pct <= -settings.daily_stop_loss_ratio:
                alert = {"type": "stop_loss", "symbol": pos["symbol"], "pnl_pct": round(pnl_pct, 4), "price": quote.price}
            elif pnl_pct >= 0.05:
                alert = {"type": "take_profit", "symbol": pos["symbol"], "pnl_pct": round(pnl_pct, 4), "price": quote.price}

            if alert:
                result = _safe_run_async(_execute_sell(
                    symbol=pos["symbol"], price=quote.price,
                    quantity=pos["quantity"], reason=f"{alert['type']} pnl={pnl_pct:.2%}",
                ), None)
                if result:
                    alerts.append(alert)
                    logger.warning("Alert: %s %s pnl=%.2f%%", alert["type"], pos["symbol"], pnl_pct * 100)

        except Exception as e:
            logger.debug("Intraday monitoring failed for %s: %s", pos["symbol"], e)

    return {
        "status": "monitored",
        "timestamp": _now_cn_iso(),
        "positions": len(positions),
        "alerts": alerts,
    }


def market_close_settlement_job() -> dict:
    """收盘结算：从 DB 读取持仓，计算当日盈亏并更新现价"""
    account = _safe_run_async(_get_or_create_account(), None)
    if not account:
        return {"status": "no_positions", "timestamp": _now_cn_iso()}
    positions = _safe_run_async(_get_positions(account["id"]), [])
    if not positions:
        return {"status": "no_positions", "timestamp": _now_cn_iso()}

    a_provider = AStockProvider()
    us_provider = YFinanceProvider()
    total_pnl = 0.0
    details = []

    for pos in positions:
        try:
            market = pos.get("market", "a_stock")
            mkt = Market.A if market == "a_stock" else (Market.HK if market == "hk_stock" else Market.US)
            provider = a_provider if market == "a_stock" else us_provider
            quote = provider.get_realtime_quote(pos["symbol"], mkt)

            pnl = (quote.price - pos["avg_cost"]) * pos["quantity"] if quote.price > 0 else 0
            pnl_pct = (quote.price / pos["avg_cost"] - 1) if pos["avg_cost"] > 0 else 0
            total_pnl += pnl

            if quote.price > 0:
                _safe_run_async(_update_position_price(account["id"], pos["symbol"], quote.price), None)

            details.append({
                "symbol": pos["symbol"], "name": pos["name"],
                "quantity": pos["quantity"], "avg_cost": pos["avg_cost"],
                "close_price": quote.price, "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
            })
        except Exception as e:
            logger.debug("Settlement failed for %s: %s", pos["symbol"], e)

    logger.info("Market close settlement: total PnL=%.2f, %d positions", total_pnl, len(details))
    return {
        "status": "settled",
        "timestamp": _now_cn_iso(),
        "total_pnl": round(total_pnl, 2),
        "positions": len(details),
        "details": details,
    }


def review_backfill_job() -> dict:
    """复盘回填：补齐模拟交易候选股 1D/5D/20D 后验收益"""
    from tradingAgents.trader.auto_strategy import QualityMomentumStrategy
    from tradingAgents.trader.review_backfill import backfill_review_returns

    strategy = QualityMomentumStrategy()
    result = backfill_review_returns(strategy.recent_runs(limit=100), force_latest=False)
    result["timestamp"] = _now_cn_iso()
    return result


def _is_cn_trading_window() -> bool:
    now = datetime.now(CN_TZ)
    minutes = now.hour * 60 + now.minute
    morning = 9 * 60 + 30 <= minutes <= 11 * 60 + 30
    afternoon = 13 * 60 <= minutes <= 14 * 60 + 55
    return morning or afternoon


async def _update_position_price(account_id, symbol, price):
    from tradingAgents.data.database.account_repo import AccountRepository
    repo = AccountRepository()
    await repo.update_position_price(account_id, symbol, price)
