"""Recovery helpers for legacy simulation account snapshots."""
from __future__ import annotations

import logging

from tradingAgents.data.database.account_repo import AccountRepository
from tradingAgents.trader.account import VirtualAccount
from tradingAgents.trader.auto_strategy import QualityMomentumStrategy

logger = logging.getLogger(__name__)


async def recover_empty_account_from_latest_run(account: VirtualAccount) -> bool:
    """Restore DB account state from the latest JSONL simulation run when DB is empty."""
    await account.aload(force=True)
    if account.positions or account.orders:
        return False

    runs = QualityMomentumStrategy().recent_runs(limit=1)
    if not runs:
        return False

    latest = runs[0]
    snapshot = latest.get("account") or {}
    if not snapshot:
        return False

    restored = await AccountRepository().restore_snapshot_if_empty(
        snapshot,
        market=latest.get("market", "a_stock"),
    )
    if restored:
        await account.aload(force=True)
        await recover_missing_orders_from_recent_runs(account)
        logger.info("Recovered account state from simulation run %s", latest.get("run_id"))
    return restored


async def recover_missing_orders_from_recent_runs(account: VirtualAccount) -> bool:
    """Restore legacy order rows when positions were recovered without orders."""
    await account.aload(force=True)
    if not account.positions or account.orders or account._account_id is None:
        return False

    position_symbols = set(account.positions.keys())
    for run in QualityMomentumStrategy().recent_runs(limit=100):
        orders = run.get("orders") or []
        if not orders:
            continue
        order_symbols = {str(item.get("symbol") or "") for item in orders}
        if not position_symbols.intersection(order_symbols):
            continue
        restored = await AccountRepository().restore_orders_if_empty(account._account_id, orders)
        if restored:
            await account.aload(force=True)
            logger.info("Recovered %d order(s) from simulation run %s", len(orders), run.get("run_id"))
            return True
    return False
