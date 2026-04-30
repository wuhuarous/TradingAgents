"""订单管理 — 订单状态跟踪"""
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderManager:
    def __init__(self):
        self.orders: list[dict] = []

    def add(self, order: dict):
        order["id"] = len(self.orders) + 1
        order["status"] = OrderStatus.FILLED
        self.orders.append(order)

    def history(self, limit: int = 50) -> list[dict]:
        return self.orders[-limit:]
