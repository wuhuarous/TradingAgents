from fastapi import APIRouter, HTTPException

from tradingAgents.server.models.trade import TradeRequest, TradeResponse
from tradingAgents.server.routers.account import get_global_account

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post("/execute", response_model=TradeResponse)
def execute_trade(req: TradeRequest):
    acc = get_global_account()
    if req.action == "buy":
        order = acc.buy(req.symbol, "", req.price, req.quantity, "手动交易")
    elif req.action == "sell":
        order = acc.sell(req.symbol, req.price, req.quantity, "手动交易")
    else:
        raise HTTPException(400, "action must be buy or sell")

    if order is None:
        return TradeResponse(success=False, order_id=0, message="余额不足或持仓不足")
    return TradeResponse(success=True, order_id=len(acc.orders), message="成交")
