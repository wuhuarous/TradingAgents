from fastapi import APIRouter

from tradingAgents.server.models.trade import AccountSummary
from tradingAgents.trader.account import VirtualAccount

router = APIRouter(prefix="/api/account", tags=["account"])
_account = VirtualAccount(persist=True)


async def _refresh_account() -> VirtualAccount:
    await _account.aload(force=True)
    if not _account.positions and not _account.orders:
        try:
            from tradingAgents.trader.account_recovery import recover_empty_account_from_latest_run

            await recover_empty_account_from_latest_run(_account)
        except Exception:
            pass
    if _account.positions and not _account.orders:
        try:
            from tradingAgents.trader.account_recovery import recover_missing_orders_from_recent_runs

            await recover_missing_orders_from_recent_runs(_account)
        except Exception:
            pass
    if _account.positions:
        try:
            await _account.arefresh_market_prices()
        except Exception:
            pass
    return _account


@router.get("/", response_model=AccountSummary)
async def get_account():
    return (await _refresh_account()).to_dict()


@router.get("/positions")
async def get_positions():
    return (await _refresh_account()).get_position_summary()


@router.get("/orders")
async def get_orders(limit: int = 50):
    return (await _refresh_account()).orders[-limit:]


def get_global_account() -> VirtualAccount:
    return _account


async def get_loaded_account() -> VirtualAccount:
    return await _refresh_account()
