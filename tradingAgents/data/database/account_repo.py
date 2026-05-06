"""Account repository — PostgreSQL-backed CRUD for VirtualAccount"""
import logging
from datetime import datetime
from sqlalchemy import select
from tradingAgents.config.settings import settings
from tradingAgents.data.database.connection import get_pg_session
from tradingAgents.data.database.models import Account, Position, Order, OrderAction, TradingPlan
from tradingAgents.trader.trade_rules import compute_trade_costs, is_same_china_trade_date

logger = logging.getLogger(__name__)


class AccountRepository:
    """Async repository for account, positions, orders, and trading plans"""

    # ── Account ──

    async def get_or_create(self) -> Account:
        async with get_pg_session() as session:
            result = await session.execute(select(Account).order_by(Account.id.asc()).limit(1))
            account = result.scalar_one_or_none()
            if account is None:
                account = Account(
                    initial_capital=float(settings.initial_capital),
                    cash=float(settings.initial_capital),
                )
                session.add(account)
                await session.commit()
                await session.refresh(account)
            else:
                positions = await session.execute(
                    select(Position).where(Position.account_id == account.id).limit(1)
                )
                orders = await session.execute(
                    select(Order).where(Order.account_id == account.id).limit(1)
                )
                configured_capital = float(settings.initial_capital)
                if (
                    not positions.scalar_one_or_none()
                    and not orders.scalar_one_or_none()
                    and abs(float(account.initial_capital or 0) - configured_capital) > 1e-8
                ):
                    account.initial_capital = configured_capital
                    account.cash = configured_capital
                    await session.commit()
                    await session.refresh(account)
            return account

    async def get_account(self, account_id: int) -> Account | None:
        async with get_pg_session() as session:
            return await session.get(Account, account_id)

    async def update_cash(self, account_id: int, delta: float):
        async with get_pg_session() as session:
            acc = await session.get(Account, account_id)
            if acc:
                acc.cash += delta
                await session.commit()

    async def apply_initial_capital_if_unstarted(self, initial_capital: float) -> dict:
        """Apply configured initial capital to the current account when no trades exist."""
        async with get_pg_session() as session:
            result = await session.execute(select(Account).order_by(Account.id.asc()).limit(1))
            account = result.scalar_one_or_none()
            if account is None:
                account = Account(
                    initial_capital=float(initial_capital),
                    cash=float(initial_capital),
                )
                session.add(account)
                await session.commit()
                await session.refresh(account)
                return {"applied": True, "reason": "created", "account_id": account.id}

            positions = await session.execute(
                select(Position).where(Position.account_id == account.id).limit(1)
            )
            orders = await session.execute(
                select(Order).where(Order.account_id == account.id).limit(1)
            )
            if positions.scalar_one_or_none() or orders.scalar_one_or_none():
                return {
                    "applied": False,
                    "reason": "account_has_trades",
                    "account_id": account.id,
                    "current_initial_capital": account.initial_capital,
                    "current_cash": account.cash,
                }

            account.initial_capital = float(initial_capital)
            account.cash = float(initial_capital)
            await session.commit()
            return {
                "applied": True,
                "reason": "unstarted_account",
                "account_id": account.id,
                "initial_capital": account.initial_capital,
                "cash": account.cash,
            }

    # ── Positions ──

    async def get_positions(self, account_id: int) -> list[Position]:
        async with get_pg_session() as session:
            result = await session.execute(
                select(Position).where(Position.account_id == account_id)
            )
            return list(result.scalars().all())

    async def upsert_position(self, account_id: int, symbol: str, name: str,
                              market: str, quantity: int, avg_cost: float):
        async with get_pg_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.account_id == account_id,
                    Position.symbol == symbol,
                )
            )
            pos = result.scalar_one_or_none()
            if pos:
                new_qty = pos.quantity + quantity
                if new_qty > 0 and quantity > 0:
                    pos.avg_cost = (
                        (pos.avg_cost * pos.quantity + avg_cost * quantity) / new_qty
                    )
                pos.quantity = new_qty
                pos.current_price = avg_cost
                pos.market = market
                pos.name = name or pos.name
                if pos.quantity <= 0:
                    await session.delete(pos)
            elif quantity > 0:
                pos = Position(
                    account_id=account_id, symbol=symbol, name=name,
                    market=market, quantity=quantity, avg_cost=avg_cost,
                    current_price=avg_cost,
                )
                session.add(pos)
            await session.commit()

    async def update_position_price(self, account_id: int, symbol: str, price: float):
        async with get_pg_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.account_id == account_id,
                    Position.symbol == symbol,
                )
            )
            pos = result.scalar_one_or_none()
            if pos:
                pos.current_price = price
                await session.commit()

    async def delete_position(self, account_id: int, symbol: str):
        async with get_pg_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.account_id == account_id,
                    Position.symbol == symbol,
                )
            )
            pos = result.scalar_one_or_none()
            if pos:
                await session.delete(pos)
                await session.commit()

    # ── Orders ──

    async def add_order(self, account_id: int, symbol: str, name: str,
                        action: str, price: float, quantity: int,
                        cost: float, reason: str = "") -> Order:
        async with get_pg_session() as session:
            order = Order(
                account_id=account_id, symbol=symbol, name=name,
                action=OrderAction(action), price=price, quantity=quantity,
                cost=cost, reason=reason,
            )
            session.add(order)
            acc = await session.get(Account, account_id)
            if acc:
                if action == "buy":
                    acc.cash -= cost
                else:
                    acc.cash += cost
            await session.commit()
            await session.refresh(order)
            return order

    async def get_orders(self, account_id: int, limit: int = 50) -> list[Order]:
        async with get_pg_session() as session:
            result = await session.execute(
                select(Order)
                .where(Order.account_id == account_id)
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def available_sell_quantity(self, account_id: int, symbol: str) -> int:
        """Return T+1-aware available quantity for a position."""
        async with get_pg_session() as session:
            result = await session.execute(
                select(Position).where(
                    Position.account_id == account_id,
                    Position.symbol == symbol,
                )
            )
            pos = result.scalar_one_or_none()
            if pos is None:
                return 0
            if pos.market != "a_stock" or not settings.a_share_t1_enabled:
                return int(pos.quantity or 0)
            same_day_buy_qty = await _same_day_buy_quantity(session, account_id, symbol)
            return max(int(pos.quantity or 0) - same_day_buy_qty, 0)

    async def restore_orders_if_empty(self, account_id: int, orders: list[dict]) -> bool:
        """Restore legacy order rows without touching cash or positions."""
        if not orders:
            return False
        async with get_pg_session() as session:
            existing = await session.execute(
                select(Order).where(Order.account_id == account_id).limit(1)
            )
            if existing.scalar_one_or_none():
                return False

            restored = 0
            for item in orders:
                action = str(item.get("action") or "").lower()
                if action not in ("buy", "sell"):
                    continue
                symbol = str(item.get("symbol") or "").strip()
                quantity = int(item.get("quantity") or 0)
                price = float(item.get("price") or 0)
                if not symbol or quantity <= 0 or price <= 0:
                    continue
                session.add(Order(
                    account_id=account_id,
                    symbol=symbol,
                    name=str(item.get("name") or ""),
                    action=OrderAction(action),
                    price=price,
                    quantity=quantity,
                    cost=float(item.get("cost") or price * quantity),
                    reason=str(item.get("reason") or "历史模拟交易恢复"),
                    created_at=_parse_order_time(item.get("timestamp")),
                ))
                restored += 1
            if restored:
                await session.commit()
                return True
            return False

    async def restore_snapshot_if_empty(
        self,
        account_snapshot: dict,
        market: str = "a_stock",
    ) -> bool:
        """Restore cash and positions from a legacy simulation snapshot if DB is empty."""
        async with get_pg_session() as session:
            result = await session.execute(select(Account).order_by(Account.id.asc()).limit(1))
            account = result.scalar_one_or_none()
            if account is None:
                account = Account()
                session.add(account)
                await session.flush()

            existing_positions = await session.execute(
                select(Position).where(Position.account_id == account.id).limit(1)
            )
            existing_orders = await session.execute(
                select(Order).where(Order.account_id == account.id).limit(1)
            )
            if existing_positions.scalar_one_or_none() or existing_orders.scalar_one_or_none():
                return False

            positions = account_snapshot.get("positions") or []
            if not positions and account_snapshot.get("cash") in (None, account.initial_capital):
                return False

            account.initial_capital = float(account_snapshot.get("initial_capital") or account.initial_capital)
            account.cash = float(account_snapshot.get("cash") or account.cash)
            for item in positions:
                symbol = str(item.get("symbol", "")).strip()
                quantity = int(item.get("quantity") or 0)
                if not symbol or quantity <= 0:
                    continue
                session.add(Position(
                    account_id=account.id,
                    symbol=symbol,
                    name=str(item.get("name", "")),
                    market=str(item.get("market") or market),
                    quantity=quantity,
                    avg_cost=float(item.get("avg_cost") or 0),
                    current_price=float(item.get("current_price") or item.get("avg_cost") or 0),
                ))
            await session.commit()
            return True

    async def execute_order(
        self,
        account_id: int,
        symbol: str,
        name: str,
        market: str,
        action: str,
        price: float,
        quantity: int,
        reason: str = "",
    ) -> Order | None:
        """Atomically update cash, position, and order history."""
        async with get_pg_session() as session:
            acc = await session.get(Account, account_id)
            if acc is None:
                return None

            value = price * quantity
            if action == "buy":
                costs = compute_trade_costs(
                    action,
                    market,
                    price,
                    quantity,
                    commission_rate=settings.commission_rate,
                    min_commission=settings.min_commission,
                    transfer_fee_rate=settings.transfer_fee_rate,
                    stamp_duty_rate=settings.stamp_duty_rate,
                )
                cash_required = costs.gross_amount + costs.total_fee
                if acc.cash < cash_required:
                    return None
                acc.cash -= cash_required

                result = await session.execute(
                    select(Position).where(
                        Position.account_id == account_id,
                        Position.symbol == symbol,
                    )
                )
                pos = result.scalar_one_or_none()
                effective_cost = cash_required / quantity if quantity else price
                if pos:
                    new_qty = pos.quantity + quantity
                    pos.avg_cost = (
                        (pos.avg_cost * pos.quantity + effective_cost * quantity) / new_qty
                    )
                    pos.quantity = new_qty
                    pos.name = name or pos.name
                    pos.market = market
                    pos.current_price = price
                else:
                    pos = Position(
                        account_id=account_id,
                        symbol=symbol,
                        name=name,
                        market=market,
                        quantity=quantity,
                        avg_cost=effective_cost,
                        current_price=price,
                    )
                    session.add(pos)

            elif action == "sell":
                result = await session.execute(
                    select(Position).where(
                        Position.account_id == account_id,
                        Position.symbol == symbol,
                    )
                )
                pos = result.scalar_one_or_none()
                if pos is None:
                    return None
                available_qty = int(pos.quantity or 0)
                if pos.market == "a_stock" and settings.a_share_t1_enabled:
                    same_day_buy_qty = await _same_day_buy_quantity(session, account_id, symbol)
                    available_qty = max(available_qty - same_day_buy_qty, 0)
                quantity = min(quantity, available_qty)
                if quantity <= 0:
                    return None
                value = price * quantity
                costs = compute_trade_costs(
                    action,
                    market,
                    price,
                    quantity,
                    commission_rate=settings.commission_rate,
                    min_commission=settings.min_commission,
                    transfer_fee_rate=settings.transfer_fee_rate,
                    stamp_duty_rate=settings.stamp_duty_rate,
                )
                acc.cash += costs.gross_amount - costs.total_fee
                name = pos.name
                market = pos.market
                pos.quantity -= quantity
                pos.current_price = price
                if pos.quantity <= 0:
                    await session.delete(pos)
            else:
                return None

            order = Order(
                account_id=account_id,
                symbol=symbol,
                name=name,
                action=OrderAction(action),
                price=price,
                quantity=quantity,
                cost=value,
                reason=reason,
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)
            return order

    # ── Trading Plans ──

    async def get_pending_plans(self) -> list[TradingPlan]:
        async with get_pg_session() as session:
            result = await session.execute(
                select(TradingPlan)
                .where(TradingPlan.status == "pending")
                .order_by(TradingPlan.confidence.desc())
            )
            return list(result.scalars().all())

    async def add_plan(self, **kwargs) -> TradingPlan:
        async with get_pg_session() as session:
            plan = TradingPlan(**kwargs)
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan

    async def mark_plan_executed(self, plan_id: int):
        async with get_pg_session() as session:
            plan = await session.get(TradingPlan, plan_id)
            if plan:
                plan.status = "executed"
                await session.commit()

    async def delete_plan(self, plan_id: int):
        async with get_pg_session() as session:
            plan = await session.get(TradingPlan, plan_id)
            if plan:
                await session.delete(plan)
                await session.commit()


def _parse_order_time(value) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.utcnow()


async def _same_day_buy_quantity(session, account_id: int, symbol: str) -> int:
    result = await session.execute(
        select(Order).where(
            Order.account_id == account_id,
            Order.symbol == symbol,
            Order.action == OrderAction.buy,
        )
    )
    qty = 0
    for order in result.scalars().all():
        if is_same_china_trade_date(order.created_at):
            qty += int(order.quantity or 0)
    return qty
