from pydantic import BaseModel


class TradeRequest(BaseModel):
    symbol: str
    action: str  # buy / sell
    price: float
    quantity: int


class TradeResponse(BaseModel):
    success: bool
    order_id: int
    message: str


class AccountSummary(BaseModel):
    initial_capital: float
    cash: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    positions: list[dict]
