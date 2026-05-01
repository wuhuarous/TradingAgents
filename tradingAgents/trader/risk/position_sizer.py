"""仓位计算 — 基于风险平价"""
def calculate_position_size(
    account_value: float,
    price: float,
    risk_per_share: float,
    max_position_pct: float = 0.2,
    max_risk_pct: float = 0.01,
) -> int:
    """计算安全仓位: 单笔最大亏损不超过账户的 max_risk_pct%"""
    max_value = account_value * max_position_pct
    risk_based = (account_value * max_risk_pct) / risk_per_share if risk_per_share > 0 else max_value / price
    cap_based = max_value / price if price > 0 else 0
    quantity = int(min(risk_based, cap_based))
    return max(100, quantity // 100 * 100)
