import asyncio
import time

from fastapi import APIRouter, Query

from tradingAgents.server.models.trade import AccountSummary
from tradingAgents.trader.account import VirtualAccount

router = APIRouter(prefix="/api/account", tags=["account"])
_account = VirtualAccount(persist=True)
_account_lock = asyncio.Lock()
_ACCOUNT_CACHE_TTL_SECONDS = 15.0
_BACKGROUND_REFRESH_TTL_SECONDS = 15.0
_last_loaded_at = 0.0
_last_background_refresh_at = 0.0


async def _refresh_account(
    refresh_prices: bool = True,
    force: bool = False,
    force_prices: bool = False,
) -> VirtualAccount:
    async with _account_lock:
        await _refresh_account_locked(
            refresh_prices=refresh_prices,
            force=force,
            force_prices=force_prices,
        )
        return _account


async def _refresh_account_locked(
    refresh_prices: bool = True,
    force: bool = False,
    force_prices: bool = False,
) -> None:
    global _last_loaded_at
    now = time.monotonic()
    should_load = force or _account._account_id is None or (now - _last_loaded_at) >= _ACCOUNT_CACHE_TTL_SECONDS
    if should_load:
        await _account.aload(force=True)
        _last_loaded_at = now
    if should_load and not _account.positions and not _account.orders:
        try:
            from tradingAgents.trader.account_recovery import recover_empty_account_from_latest_run

            await recover_empty_account_from_latest_run(_account)
        except Exception:
            pass
    if should_load and _account.positions and not _account.orders:
        try:
            from tradingAgents.trader.account_recovery import recover_missing_orders_from_recent_runs

            await recover_missing_orders_from_recent_runs(_account)
        except Exception:
            pass
    if refresh_prices and _account.positions:
        try:
            await _account.arefresh_market_prices(force=force_prices)
        except Exception:
            pass


@router.get("/", response_model=AccountSummary)
async def get_account(force_prices: bool = Query(False)):
    async with _account_lock:
        await _refresh_account_locked(refresh_prices=True, force_prices=force_prices)
        return _account.to_dict()


@router.get("/positions")
async def get_positions(force_prices: bool = Query(False)):
    async with _account_lock:
        await _refresh_account_locked(refresh_prices=True, force_prices=force_prices)
        return _account.get_position_summary()


@router.get("/overview")
async def get_account_overview(force_prices: bool = Query(False)):
    async with _account_lock:
        await _refresh_account_locked(refresh_prices=True, force_prices=force_prices)
        return {
            "account": _account.to_dict(),
            "positions": _account.get_position_summary(),
        }


@router.get("/orders")
async def get_orders(limit: int = 50):
    async with _account_lock:
        await _refresh_account_locked(refresh_prices=False)
        return _account.orders[-limit:]


def get_global_account() -> VirtualAccount:
    return _account


async def get_loaded_account() -> VirtualAccount:
    return await _refresh_account()


async def get_account_summary_locked() -> tuple[int | None, dict]:
    async with _account_lock:
        await _refresh_account_locked(refresh_prices=True)
        return getattr(_account, "_account_id", None), _account.to_dict()


async def _background_refresh() -> None:
    """Fire-and-forget refresh that doesn't error the caller."""
    try:
        async with _account_lock:
            await _refresh_account_locked(refresh_prices=True)
    except Exception:
        pass


async def get_account_summary_fast() -> tuple[int | None, dict]:
    """Return cached account summary for read-heavy endpoints.

    Returns immediately with in-memory state when available.  Kicks off a
    non-blocking background refresh so the next request sees updated data.
    """
    global _last_background_refresh_at
    account_id = getattr(_account, "_account_id", None)
    if account_id is None:
        return await get_account_summary_locked()

    now = time.monotonic()
    should_refresh = (
        (now - _last_loaded_at) >= _ACCOUNT_CACHE_TTL_SECONDS
        and (now - _last_background_refresh_at) >= _BACKGROUND_REFRESH_TTL_SECONDS
    )
    if should_refresh and not _account_lock.locked():
        _last_background_refresh_at = now
        asyncio.create_task(_background_refresh())
    return account_id, _account.to_dict()
