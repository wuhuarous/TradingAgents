"""AI trading strategy engine: convert decisions into executable plans."""


class StrategyEngine:
    """Generate executable trading plans from a TraderAgent decision."""

    @staticmethod
    def generate_plan(trader_decision: dict, account_cash: float) -> dict:
        action = trader_decision.get("action", "hold")
        quantity_pct = trader_decision.get("quantity_pct", 0)
        price_lower = trader_decision.get("price_lower", 0)
        price_upper = trader_decision.get("price_upper", 0)
        budget = account_cash * quantity_pct

        plan = {
            "action": action,
            "budget": budget,
            "price_range": [price_lower, price_upper],
            "stop_loss": trader_decision.get("stop_loss", 0),
            "take_profit": trader_decision.get("take_profit", 0),
            "confidence": trader_decision.get("confidence", 0),
        }

        if action == "buy" and price_lower > 0:
            quantity = int(budget / price_lower / 100) * 100
            plan["quantity"] = max(100, quantity)
        else:
            plan["quantity"] = 0

        return plan
