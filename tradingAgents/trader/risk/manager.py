"""风控管理器 — 统一止损/仓位/回撤控制"""
from tradingAgents.trader.risk.stop_loss import evaluate_stop_loss, evaluate_take_profit
from tradingAgents.trader.risk.position_sizer import calculate_position_size


class RiskManager:
    def __init__(
        self,
        daily_stop_loss_pct: float = 0.03,
        single_position_max_pct: float = 0.2,
        daily_drawdown_limit_pct: float = 0.05,
    ):
        self.daily_stop_loss_pct = daily_stop_loss_pct
        self.single_position_max_pct = single_position_max_pct
        self.daily_drawdown_limit_pct = daily_drawdown_limit_pct
        self._daily_pnl = 0.0
        self._daily_start_value = 0.0
        self._price_highs: dict = {}  # symbol → highest price

    def check_position(self, symbol: str, avg_cost: float, current_price: float, quantity: int) -> dict:
        """检查单个持仓的风控状态"""
        self._price_highs[symbol] = max(self._price_highs.get(symbol, current_price), current_price)

        stop_loss = evaluate_stop_loss(avg_cost, current_price, self.daily_stop_loss_pct)
        take_profit = evaluate_take_profit(
            avg_cost, current_price,
            highest_price=self._price_highs[symbol],
        )

        return {
            "symbol": symbol,
            "current_price": current_price,
            "avg_cost": avg_cost,
            "pnl_pct": stop_loss.current_pnl_pct,
            "stop_loss_triggered": stop_loss.triggered,
            "stop_loss_price": stop_loss.stop_price,
            "take_profit_triggered": take_profit,
            "action": "sell" if (stop_loss.triggered or take_profit) else "hold",
        }

    def calculate_position_size(self, account_value: float, price: float, risk_per_share: float = 0) -> int:
        return calculate_position_size(
            account_value, price, risk_per_share or price * self.daily_stop_loss_pct,
            max_position_pct=self.single_position_max_pct,
        )

    def record_daily_pnl(self, pnl: float, account_value: float):
        self._daily_pnl = pnl
        if self._daily_start_value == 0:
            self._daily_start_value = account_value

    def should_halt_trading(self) -> bool:
        if self._daily_start_value <= 0:
            return False
        drawdown = abs(self._daily_pnl) / self._daily_start_value
        return self._daily_pnl < 0 and drawdown >= self.daily_drawdown_limit_pct

    def get_dynamic_params(self, volatility: float) -> dict:
        """AI动态风控: 根据波动率调整参数"""
        adjusted_stop = min(self.daily_stop_loss_pct * (1 + volatility), 0.10)
        adjusted_position = self.single_position_max_pct / (1 + volatility)
        return {
            "stop_loss_pct": round(adjusted_stop, 3),
            "position_max_pct": round(adjusted_position, 3),
        }
