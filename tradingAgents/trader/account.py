"""虚拟账户 — 资金管理 + 交易执行 (PostgreSQL-backed)"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from tradingAgents.config.settings import settings
from tradingAgents.trader.trade_rules import compute_trade_costs, is_same_china_trade_date

logger = logging.getLogger(__name__)

# Price-refresh TTL: skip repeated market-price fetches within this window
_PRICE_CACHE_TTL_SECONDS = 60.0
CN_TZ = ZoneInfo("Asia/Shanghai")


class VirtualAccount:
    """Trading account with PostgreSQL persistence via AccountRepository.

    Sync methods (buy/sell) operate in-memory and persist.
    Async methods (abuy/asell) are preferred for production use.
    """

    def __init__(self, initial_capital: float = 1_000_000, persist: bool = False):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict = {}
        self.orders: list[dict] = []
        self.trade_log: list[dict] = []
        self._account_id: int | None = None
        self._repo = None
        self._persist = persist
        self._last_price_refresh: float = 0

    # ── Properties ──

    @property
    def positions_value(self) -> float:
        return sum(
            p.get("current_price", 0) * p.get("quantity", 0)
            for p in self.positions.values()
        )

    @property
    def total_value(self) -> float:
        return self.cash + self.positions_value

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.initial_capital

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_value / self.initial_capital - 1) if self.initial_capital > 0 else 0

    # ── Async DB-backed methods ──

    async def _ensure_account(self):
        if self._account_id is None or self._repo is None:
            await self.aload(force=True)

    async def aload(self, force: bool = False):
        """Load account, positions, and recent orders from database."""
        if self._account_id is not None and not force:
            return
        from tradingAgents.data.database.account_repo import AccountRepository

        self._repo = AccountRepository()
        account = await self._repo.get_or_create()
        self._account_id = account.id
        self.cash = account.cash
        self.initial_capital = account.initial_capital

        positions = await self._repo.get_positions(self._account_id)
        self.positions = {}
        for p in positions:
            available_qty = p.quantity
            if p.market == "a_stock" and settings.a_share_t1_enabled:
                try:
                    available_qty = await self._repo.available_sell_quantity(self._account_id, p.symbol)
                except Exception:
                    available_qty = p.quantity
            self.positions[p.symbol] = {
                "name": p.name, "quantity": p.quantity,
                "avg_cost": p.avg_cost, "current_price": p.current_price,
                "market": p.market, "available_quantity": available_qty,
            }

        orders = await self._repo.get_orders(self._account_id, limit=200)
        self.orders = [_order_to_dict(o) for o in reversed(orders)]
        self.trade_log = list(self.orders)

    async def arefresh_market_prices(self, force: bool = False) -> dict:
        """Mark open positions to latest quotes and persist current prices.

        Orders store the execution price. Portfolio PnL needs a separate
        mark-to-market refresh, otherwise a newly bought position stays at
        avg_cost forever and unrealized PnL appears as zero.

        Rate-limited: skips refresh when called within _PRICE_CACHE_TTL_SECONDS
        unless *force* is True.
        """
        if not force and (time.monotonic() - self._last_price_refresh) < _PRICE_CACHE_TTL_SECONDS:
            return {"updated": 0, "failed": 0, "cached": True}
        await self._ensure_account()
        if not self.positions:
            return {"updated": 0, "failed": 0}

        updated = 0
        failed = 0
        for symbol, pos in list(self.positions.items()):
            try:
                price = await asyncio.to_thread(_latest_position_price, symbol, pos.get("market", "a_stock"))
            except Exception as exc:
                logger.debug("Quote refresh failed for %s: %s", symbol, exc)
                failed += 1
                continue

            if price <= 0:
                failed += 1
                continue

            old_price = float(pos.get("current_price") or 0)
            if abs(price - old_price) < 1e-8:
                continue

            pos["current_price"] = price
            if self._repo and self._account_id is not None:
                await self._repo.update_position_price(self._account_id, symbol, price)
            updated += 1

        if updated:
            await self.aload(force=True)
            await self._record_snapshot("mark_to_market")
        self._last_price_refresh = time.monotonic()
        return {"updated": updated, "failed": failed}

    def load(self, force: bool = False) -> None:
        """Best-effort synchronous DB refresh for FastAPI sync endpoints."""
        if not self._persist:
            return
        try:
            _run_coro_blocking(self.aload(force=force))
        except Exception as exc:
            logger.warning("Account DB refresh failed, using in-memory state: %s", exc)

    async def abuy(self, symbol: str, name: str, price: float, quantity: int,
                   market: str = "a_stock", reason: str = "") -> Optional[dict]:
        await self._ensure_account()
        costs = compute_trade_costs(
            "buy",
            market,
            price,
            quantity,
            commission_rate=settings.commission_rate,
            min_commission=settings.min_commission,
            transfer_fee_rate=settings.transfer_fee_rate,
            stamp_duty_rate=settings.stamp_duty_rate,
        )
        if self.cash < costs.gross_amount + costs.total_fee:
            return None

        order = await self._repo.execute_order(
            self._account_id, symbol, name, market, "buy", price, quantity, reason
        )
        if order is None:
            return None
        order_dict = _order_to_dict(order)
        await self.aload(force=True)
        await self._record_snapshot("order:buy")
        return order_dict

    async def asell(self, symbol: str, price: float, quantity: int,
                    reason: str = "") -> Optional[dict]:
        await self._ensure_account()
        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        available_qty = int(pos.get("available_quantity", pos.get("quantity", 0)) or 0)
        if pos.get("market", "a_stock") == "a_stock" and settings.a_share_t1_enabled and available_qty <= 0:
            return None
        order = await self._repo.execute_order(
            self._account_id,
            symbol,
            pos.get("name", ""),
            pos.get("market", "a_stock"),
            "sell",
            price,
            quantity,
            reason,
        )
        if order is None:
            return None
        order_dict = _order_to_dict(order)
        await self.aload(force=True)
        await self._record_snapshot("order:sell")
        return order_dict

    async def _record_snapshot(self, source: str) -> None:
        if self._account_id is None:
            return
        try:
            from tradingAgents.data.database.portfolio_repo import PortfolioRepository

            await PortfolioRepository().add_snapshot(self._account_id, self.to_dict(), source=source)
        except Exception as exc:
            logger.warning("Portfolio snapshot failed: %s", exc)

    # ── Sync wrappers (backward compat) ──

    def can_buy(self, price: float, quantity: int) -> bool:
        costs = compute_trade_costs(
            "buy",
            "a_stock",
            price,
            quantity,
            commission_rate=settings.commission_rate,
            min_commission=settings.min_commission,
            transfer_fee_rate=settings.transfer_fee_rate,
            stamp_duty_rate=settings.stamp_duty_rate,
        )
        return self.cash >= costs.gross_amount + costs.total_fee

    def buy(self, symbol: str, name: str, price: float, quantity: int,
            reason: str = "", market: str = "a_stock") -> Optional[dict]:
        if self._persist:
            try:
                return _run_coro_blocking(
                    self.abuy(symbol, name, price, quantity, market=market, reason=reason)
                )
            except Exception as exc:
                logger.warning("Persistent buy failed, falling back to memory: %s", exc)

        costs = compute_trade_costs(
            "buy",
            market,
            price,
            quantity,
            commission_rate=settings.commission_rate,
            min_commission=settings.min_commission,
            transfer_fee_rate=settings.transfer_fee_rate,
            stamp_duty_rate=settings.stamp_duty_rate,
        )
        cost = costs.gross_amount + costs.total_fee
        if self.cash < cost:
            return None
        self.cash -= cost
        effective_price = cost / quantity if quantity else price
        if symbol in self.positions:
            old_qty = self.positions[symbol]["quantity"]
            old_cost = self.positions[symbol]["avg_cost"]
            new_qty = old_qty + quantity
            self.positions[symbol]["quantity"] = new_qty
            self.positions[symbol]["avg_cost"] = (old_cost * old_qty + effective_price * quantity) / new_qty
        else:
            self.positions[symbol] = {
                "name": name, "quantity": quantity,
                "avg_cost": effective_price, "current_price": price, "market": market,
            }
        order = {
            "order_id": len(self.orders) + 1,
            "symbol": symbol, "name": name, "action": "buy",
            "price": price, "quantity": quantity, "cost": costs.gross_amount,
            "fee": costs.total_fee, "cash_amount": cost,
            "reason": reason, "timestamp": datetime.now().isoformat(),
            "status": "filled",
        }
        self.orders.append(order)
        self.trade_log.append(order)
        self.positions[symbol]["available_quantity"] = self._available_sell_quantity(symbol)
        return order

    def sell(self, symbol: str, price: float, quantity: int, reason: str = "") -> Optional[dict]:
        if self._persist:
            try:
                return _run_coro_blocking(self.asell(symbol, price, quantity, reason=reason))
            except Exception as exc:
                logger.warning("Persistent sell failed, falling back to memory: %s", exc)

        if symbol not in self.positions:
            return None
        pos = self.positions[symbol]
        sell_qty = min(quantity, self._available_sell_quantity(symbol))
        if sell_qty <= 0:
            return None
        costs = compute_trade_costs(
            "sell",
            pos.get("market", "a_stock"),
            price,
            sell_qty,
            commission_rate=settings.commission_rate,
            min_commission=settings.min_commission,
            transfer_fee_rate=settings.transfer_fee_rate,
            stamp_duty_rate=settings.stamp_duty_rate,
        )
        revenue = costs.gross_amount - costs.total_fee
        self.cash += revenue
        pos["quantity"] -= sell_qty
        if pos["quantity"] <= 0:
            del self.positions[symbol]
        else:
            pos["available_quantity"] = self._available_sell_quantity(symbol)
        order = {
            "order_id": len(self.orders) + 1,
            "symbol": symbol, "name": pos.get("name", ""), "action": "sell",
            "price": price, "quantity": sell_qty, "cost": costs.gross_amount,
            "fee": costs.total_fee, "cash_amount": revenue,
            "revenue": revenue, "reason": reason,
            "timestamp": datetime.now().isoformat(), "status": "filled",
        }
        self.orders.append(order)
        self.trade_log.append(order)
        return order

    def get_position_summary(self) -> list[dict]:
        return [
            {
                "symbol": s, "name": p.get("name", ""),
                "market": p.get("market", "a_stock"),
                "quantity": p["quantity"], "avg_cost": p["avg_cost"],
                "available_quantity": p.get("available_quantity", p.get("quantity", 0)),
                "current_price": p.get("current_price", 0),
                "market_value": p.get("current_price", 0) * p.get("quantity", 0),
                "pnl": (p.get("current_price", 0) - p["avg_cost"]) * p.get("quantity", 0),
                "pnl_pct": (p.get("current_price", 0) / p["avg_cost"] - 1) if p["avg_cost"] > 0 else 0,
            }
            for s, p in self.positions.items()
        ]

    def _available_sell_quantity(self, symbol: str) -> int:
        pos = self.positions.get(symbol)
        if not pos:
            return 0
        total_qty = int(pos.get("quantity", 0) or 0)
        if pos.get("market", "a_stock") != "a_stock" or not settings.a_share_t1_enabled:
            return total_qty

        same_day_buy_qty = 0
        for order in self.orders:
            if order.get("symbol") != symbol or str(order.get("action", "")).lower() != "buy":
                continue
            try:
                created_at = datetime.fromisoformat(str(order.get("timestamp", "")))
            except ValueError:
                continue
            if is_same_china_trade_date(created_at):
                same_day_buy_qty += int(order.get("quantity") or 0)
        return max(total_qty - same_day_buy_qty, 0)

    def to_dict(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "total_value": self.total_value,
            "total_pnl": self.total_pnl,
            "total_pnl_pct": self.total_pnl_pct,
            "positions": self.get_position_summary(),
        }


def _order_to_dict(order) -> dict:
    action = getattr(order.action, "value", order.action)
    market = "a_stock"
    costs = compute_trade_costs(
        action,
        market,
        order.price,
        order.quantity,
        commission_rate=settings.commission_rate,
        min_commission=settings.min_commission,
        transfer_fee_rate=settings.transfer_fee_rate,
        stamp_duty_rate=settings.stamp_duty_rate,
    )
    data = {
        "order_id": order.id,
        "symbol": order.symbol,
        "name": order.name,
        "action": action,
        "price": order.price,
        "quantity": order.quantity,
        "cost": order.cost,
        "fee": costs.total_fee,
        "cash_amount": order.cost + costs.total_fee if action == "buy" else order.cost - costs.total_fee,
        "reason": order.reason,
        "timestamp": _to_china_iso(order.created_at),
        "status": "filled",
    }
    if action == "sell":
        data["revenue"] = order.cost - costs.total_fee
    return data


def _to_china_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CN_TZ).isoformat()


def _latest_position_price(symbol: str, market: str) -> float:
    from tradingAgents.data.providers.a_stock import AStockProvider
    from tradingAgents.engine.dataflows.interface import Market
    from tradingAgents.engine.dataflows.yfinance import YFinanceProvider

    if market == "a_stock":
        quote = AStockProvider().get_realtime_quote(symbol, Market.A)
    elif market == "hk_stock":
        quote = YFinanceProvider().get_realtime_quote(symbol, Market.HK)
    else:
        quote = YFinanceProvider().get_realtime_quote(symbol, Market.US)
    return float(getattr(quote, "price", 0) or 0)


def _run_coro_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()
