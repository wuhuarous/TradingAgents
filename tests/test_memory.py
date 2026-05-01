"""Tests for trading experience memory and review system"""
import json
import os
import tempfile

from tradingAgents.engine.agents.utils.memory import TradingMemory


class TestTradingMemory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.memory = TradingMemory(memory_dir=self.tmpdir)

    def test_record_decision_writes_file(self):
        self.memory.record_decision({"symbol": "AAPL", "action": "buy", "score": 7})
        assert os.path.exists(self.memory.log_path)

    def test_record_adds_timestamp(self):
        self.memory.record_decision({"symbol": "AAPL", "action": "buy"})
        entries = self.memory.load_recent()
        assert len(entries) == 1
        assert "timestamp" in entries[0]

    def test_load_recent_empty_when_no_file(self):
        memory = TradingMemory(memory_dir="/nonexistent/path/12345")
        assert memory.load_recent() == []

    def test_load_recent_respects_limit(self):
        for i in range(10):
            self.memory.record_decision({"symbol": f"S{i}", "action": "buy"})
        assert len(self.memory.load_recent(limit=5)) == 5

    def test_find_similar_by_symbol(self):
        self.memory.record_decision({"symbol": "AAPL", "action": "buy"})
        self.memory.record_decision({"symbol": "GOOGL", "action": "sell"})
        self.memory.record_decision({"symbol": "AAPL", "action": "buy"})
        results = self.memory.find_similar("AAPL", "buy")
        assert len(results) == 2
        assert all(r["symbol"] == "AAPL" for r in results)

    def test_find_similar_returns_empty_if_none(self):
        results = self.memory.find_similar("UNKNOWN")
        assert results == []

    def test_daily_review_generates_summary(self):
        summary = self.memory.daily_review(
            account_summary={"total_value": 105000, "total_pnl_pct": 0.05},
            trades=[
                {"symbol": "AAPL", "pnl": 500},
                {"symbol": "GOOGL", "pnl": -200},
            ],
        )
        assert "复盘" in summary
        assert "盈利: 1 笔" in summary
        assert "亏损: 1 笔" in summary

    def test_daily_review_writes_review_file(self):
        self.memory.daily_review(
            account_summary={"total_value": 100000, "total_pnl_pct": 0.0},
            trades=[],
        )
        import glob
        reviews = glob.glob(os.path.join(self.tmpdir, "review_*.md"))
        assert len(reviews) >= 1
