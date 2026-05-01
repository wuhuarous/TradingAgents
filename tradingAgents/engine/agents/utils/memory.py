"""经验记忆系统 — 记录每笔交易，复盘时检索类似场景"""
import json
import os
from datetime import datetime


class TradingMemory:
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        self.log_path = os.path.join(memory_dir, "trading_memory.jsonl")

    def record_decision(self, entry: dict):
        """记录每次分析+交易决策"""
        entry["timestamp"] = datetime.now().isoformat()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_recent(self, limit: int = 30) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries[-limit:]

    def find_similar(self, symbol: str, action: str = "buy") -> list[dict]:
        """查找相同股票的类似决策"""
        entries = self.load_recent(100)
        return [
            e for e in entries
            if e.get("symbol") == symbol and e.get("action") == action
        ][-5:]

    def daily_review(self, account_summary: dict, trades: list[dict]) -> str:
        """每日复盘: 总结得失，输出优化建议"""
        winning = sum(1 for t in trades if t.get("pnl", 0) > 0)
        losing = len(trades) - winning
        total_pnl = sum(t.get("pnl", 0) for t in trades)

        summary = f"""## 复盘 {datetime.now().strftime('%Y-%m-%d')}

- 今日交易: {len(trades)} 笔
- 盈利: {winning} 笔  |  亏损: {losing} 笔
- 总盈亏: ¥{total_pnl:,.2f}
- 账户总值: ¥{account_summary.get('total_value', 0):,.2f}
- 收益率: {account_summary.get('total_pnl_pct', 0):.2%}

### 经验教训
"""
        review_path = os.path.join(self.memory_dir, f"review_{datetime.now().strftime('%Y%m%d')}.md")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(summary)
        return summary
