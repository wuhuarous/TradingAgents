from fastapi import APIRouter, HTTPException

from tradingAgents.server.models.trade import TradeRequest, TradeResponse
from tradingAgents.server.routers.account import get_loaded_account

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post("/execute", response_model=TradeResponse)
async def execute_trade(req: TradeRequest):
    acc = await get_loaded_account()
    if req.action == "buy":
        order = await acc.abuy(req.symbol, "", req.price, req.quantity, market=req.market, reason="手动交易")
    elif req.action == "sell":
        order = await acc.asell(req.symbol, req.price, req.quantity, reason="手动交易")
    else:
        raise HTTPException(400, "action must be buy or sell")

    if order is None:
        return TradeResponse(success=False, order_id=0, message="余额不足或持仓不足")
    return TradeResponse(success=True, order_id=order.get("order_id", len(acc.orders)), message="成交")
