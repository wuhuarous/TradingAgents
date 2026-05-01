"""Tests for FastAPI endpoints"""
import pytest
from fastapi.testclient import TestClient

from tradingAgents.server.main import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAccountAPI:
    def test_get_account_returns_summary(self):
        resp = client.get("/api/account/")
        assert resp.status_code == 200
        data = resp.json()
        assert "initial_capital" in data
        assert "cash" in data
        assert "total_value" in data

    def test_get_positions_returns_list(self):
        resp = client.get("/api/account/positions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_orders_returns_list(self):
        resp = client.get("/api/account/orders")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestTradingAPI:
    def test_buy_insufficient_cash(self):
        resp = client.post("/api/trading/execute", json={
            "symbol": "000001", "action": "buy",
            "price": 99999.0, "quantity": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_buy_valid(self):
        resp = client.post("/api/trading/execute", json={
            "symbol": "000001", "action": "buy",
            "price": 10.0, "quantity": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["order_id"] > 0

    def test_invalid_action(self):
        resp = client.post("/api/trading/execute", json={
            "symbol": "000001", "action": "invalid",
            "price": 10.0, "quantity": 100,
        })
        assert resp.status_code == 400

    def test_sell_no_position(self):
        resp = client.post("/api/trading/execute", json={
            "symbol": "UNKNOWN", "action": "sell",
            "price": 10.0, "quantity": 100,
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is False


class TestStocksAPI:
    def test_search_returns_list(self):
        resp = client.get("/api/stocks/search?keyword=平安&market=a_stock")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAnalysisAPI:
    def test_analysis_validation(self):
        resp = client.post("/api/analysis/run", json={
            "symbol": "", "market": "us_stock",
        })
        assert resp.status_code == 422
