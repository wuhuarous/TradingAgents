"""Sync full A-share daily K-line data into ClickHouse.

Example:
    python scripts/sync_a_stock_daily.py --batch-size 50 --max-workers 4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tradingAgents.data.database.market_sync import sync_a_stock_daily_full


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync full A-share daily K-line data into ClickHouse.")
    parser.add_argument("--limit", type=int, default=None, help="Limit symbol count for a partial run.")
    parser.add_argument("--batch-size", type=int, default=50, help="Symbols per batch.")
    parser.add_argument("--max-workers", type=int, default=4, help="Concurrent quote fetch workers.")
    parser.add_argument("--force", action="store_true", help="Fetch and insert even when enough rows already exist.")
    parser.add_argument("--min-rows", type=int, default=200, help="Skip symbols with at least this many daily rows.")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="Sleep between batches.")
    parser.add_argument(
        "--status-file",
        default=str(ROOT / "logs" / "a_stock_daily_sync_status.json"),
        help="JSON status file updated after every batch.",
    )
    parser.add_argument(
        "--persist-universe",
        action="store_true",
        help="Also upsert discovered A-share codes into PostgreSQL stock_universe before syncing K-lines.",
    )
    args = parser.parse_args()

    result = sync_a_stock_daily_full(
        limit=args.limit,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        force=args.force,
        min_rows=args.min_rows,
        sleep_seconds=args.sleep_seconds,
        status_path=args.status_file,
        persist_universe=args.persist_universe,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
