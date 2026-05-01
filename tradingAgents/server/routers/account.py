from fastapi import APIRouter

from tradingAgents.server.models.trade import AccountSummary
from tradingAgents.trader.account import VirtualAccount

router = APIRouter(prefix="/api/account", tags=["account"])
_account = VirtualAccount()


@router.get("/", response_model=AccountSummary)
def get_account():
    return _account.to_dict()


@router.get("/positions")
def get_positions():
    return _account.get_position_summary()


@router.get("/orders")
def get_orders(limit: int = 50):
    return _account.orders[-limit:]


def get_global_account() -> VirtualAccount:
    return _account
