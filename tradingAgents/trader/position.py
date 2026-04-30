"""持仓管理"""
class PositionManager:
    def __init__(self):
        self.positions: dict = {}

    def update(self, symbol: str, name: str, quantity: int, price: float):
        if quantity <= 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = {
                "name": name, "quantity": quantity, "current_price": price,
            }

    def get(self, symbol: str) -> dict | None:
        return self.positions.get(symbol)

    def all(self) -> dict:
        import copy
        return copy.deepcopy(self.positions)
