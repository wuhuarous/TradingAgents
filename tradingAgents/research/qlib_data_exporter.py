"""Export project-owned market data into Qlib's file format."""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tradingAgents.data.database.connection import get_ch_client


@dataclass
class QlibExportConfig:
    market: str = "a_stock"
    target_dir: str = "memory/qlib_data/a_stock_custom"
    start_date: str | None = None
    end_date: str | None = None
    limit: int = 500
    min_rows: int = 30
    overwrite: bool = False


class QlibDataExporter:
    source = "clickhouse_kline_daily"

    def status(self, target_dir: str = "memory/qlib_data/a_stock_custom") -> dict[str, Any]:
        root = Path(target_dir).expanduser()
        calendar = root / "calendars" / "day.txt"
        instruments = root / "instruments" / "all.txt"
        features = root / "features"
        feature_dirs = list(features.iterdir()) if features.exists() else []
        return {
            "target_dir": str(root.resolve()),
            "available": calendar.exists() and instruments.exists() and bool(feature_dirs),
            "calendar": calendar.exists(),
            "instruments": instruments.exists(),
            "features": features.exists(),
            "symbol_count": len([p for p in feature_dirs if p.is_dir()]),
        }

    def source_status(self, market: str = "a_stock") -> dict[str, Any]:
        try:
            ch = get_ch_client()
            df = ch.query_df(
                """
                SELECT
                    count() AS row_count,
                    uniqExact(symbol) AS symbol_count,
                    min(date) AS start_date,
                    max(date) AS end_date
                FROM kline_daily
                """
            )
            row = df.iloc[0].to_dict() if not df.empty else {}
            return {
                "market": market,
                "source": self.source,
                "available": int(row.get("row_count") or 0) > 0,
                "row_count": int(row.get("row_count") or 0),
                "symbol_count": int(row.get("symbol_count") or 0),
                "start_date": str(row.get("start_date") or ""),
                "end_date": str(row.get("end_date") or ""),
            }
        except Exception as exc:
            return {
                "market": market,
                "source": self.source,
                "available": False,
                "row_count": 0,
                "symbol_count": 0,
                "start_date": "",
                "end_date": "",
                "error": str(exc)[:300],
            }

    def export_from_clickhouse(self, config: QlibExportConfig) -> dict[str, Any]:
        started_at = datetime.utcnow()
        export_id = f"qexp{started_at.strftime('%Y%m%d%H%M%S%f')}"
        try:
            df = self._load_kline(config)
            if df.empty:
                return self._result(
                    export_id,
                    config,
                    started_at,
                    status="failed",
                    message="ClickHouse kline_daily 没有可导出的日线数据，请先同步历史 K 线。",
                )
            prepared = self._prepare_frame(df, config)
            if prepared.empty:
                return self._result(
                    export_id,
                    config,
                    started_at,
                    status="failed",
                    message=f"过滤后没有满足 min_rows={config.min_rows} 的标的。",
                )
            target = Path(config.target_dir).expanduser()
            if target.exists() and config.overwrite:
                shutil.rmtree(target)
            self._write_qlib_files(prepared, target)
            symbols = sorted(prepared["instrument"].unique())
            calendars = sorted(prepared["date"].unique())
            return self._result(
                export_id,
                config,
                started_at,
                status="success",
                message="已从 ClickHouse kline_daily 导出 Qlib 自定义日线数据。",
                symbol_count=len(symbols),
                row_count=len(prepared),
                calendar_count=len(calendars),
                start_date=str(pd.Timestamp(min(calendars)).date()) if calendars else "",
                end_date=str(pd.Timestamp(max(calendars)).date()) if calendars else "",
                metadata={
                    "fields": ["open", "high", "low", "close", "volume", "factor", "change"],
                    "target_status": self.status(str(target)),
                },
            )
        except Exception as exc:
            return self._result(
                export_id,
                config,
                started_at,
                status="failed",
                message=f"Qlib 数据导出失败: {type(exc).__name__}: {str(exc)[:500]}",
            )

    def _load_kline(self, config: QlibExportConfig) -> pd.DataFrame:
        ch = get_ch_client()
        conditions = []
        params: dict[str, Any] = {}
        if config.start_date:
            conditions.append("date >= {start_date:Date}")
            params["start_date"] = config.start_date
        if config.end_date:
            conditions.append("date <= {end_date:Date}")
            params["end_date"] = config.end_date
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        symbol_filter = ""
        if config.limit > 0:
            symbol_filter = """
            symbol IN (
                SELECT symbol
                FROM kline_daily
                GROUP BY symbol
                ORDER BY symbol
                LIMIT {limit:Int32}
            )
            """
            conditions.append(symbol_filter)
            params["limit"] = config.limit
            where = f"WHERE {' AND '.join(conditions)}"
        return ch.query_df(
            f"""
            SELECT
                symbol,
                toDate(date) AS date,
                anyLast(open) AS open,
                anyLast(high) AS high,
                anyLast(low) AS low,
                anyLast(close) AS close,
                anyLast(volume) AS volume
            FROM kline_daily
            {where}
            GROUP BY symbol, date
            ORDER BY symbol, date
            """,
            parameters=params,
        )

    def _prepare_frame(self, df: pd.DataFrame, config: QlibExportConfig) -> pd.DataFrame:
        data = df.copy()
        data["date"] = pd.to_datetime(data["date"])
        data["instrument"] = data["symbol"].map(_to_qlib_instrument)
        for column in ("open", "high", "low", "close", "volume"):
            data[column] = pd.to_numeric(data[column], errors="coerce")
        data = data.dropna(subset=["instrument", "date", "close"])
        data = data[data["close"] > 0].sort_values(["instrument", "date"])
        data["factor"] = 1.0
        data["change"] = data.groupby("instrument")["close"].pct_change().fillna(0)
        counts = data.groupby("instrument")["date"].transform("count")
        data = data[counts >= config.min_rows]
        return data[["instrument", "date", "open", "high", "low", "close", "volume", "factor", "change"]]

    def _write_qlib_files(self, df: pd.DataFrame, target: Path) -> None:
        calendars = sorted(pd.Timestamp(x) for x in df["date"].unique())
        calendar_index = {day: idx for idx, day in enumerate(calendars)}
        (target / "calendars").mkdir(parents=True, exist_ok=True)
        (target / "instruments").mkdir(parents=True, exist_ok=True)
        (target / "features").mkdir(parents=True, exist_ok=True)
        np.savetxt(target / "calendars" / "day.txt", [x.strftime("%Y-%m-%d") for x in calendars], fmt="%s", encoding="utf-8")

        instruments: list[str] = []
        for instrument, group in df.groupby("instrument"):
            group = group.sort_values("date").drop_duplicates("date")
            instruments.append(
                f"{instrument}\t{group['date'].min().strftime('%Y-%m-%d')}\t{group['date'].max().strftime('%Y-%m-%d')}"
            )
            feature_dir = target / "features" / instrument.lower()
            feature_dir.mkdir(parents=True, exist_ok=True)
            begin = pd.Timestamp(group["date"].min())
            end = pd.Timestamp(group["date"].max())
            active_calendar = [day for day in calendars if begin <= day <= end]
            aligned = pd.DataFrame({"date": active_calendar}).merge(group, on="date", how="left")
            date_index = calendar_index[begin]
            for field in ("open", "high", "low", "close", "volume", "factor", "change"):
                values = aligned[field].astype("float32").replace([math.inf, -math.inf], np.nan)
                np.hstack([date_index, values]).astype("<f").tofile(feature_dir / f"{field}.day.bin")

        np.savetxt(target / "instruments" / "all.txt", instruments, fmt="%s", encoding="utf-8")

    def _result(
        self,
        export_id: str,
        config: QlibExportConfig,
        started_at: datetime,
        status: str,
        message: str,
        symbol_count: int = 0,
        row_count: int = 0,
        calendar_count: int = 0,
        start_date: str = "",
        end_date: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "export_id": export_id,
            "market": config.market,
            "source": self.source,
            "target_dir": str(Path(config.target_dir).expanduser().resolve()),
            "status": status,
            "symbol_count": symbol_count,
            "row_count": row_count,
            "calendar_count": calendar_count,
            "start_date": start_date,
            "end_date": end_date,
            "message": message,
            "metadata": metadata or {},
            "started_at": started_at,
            "finished_at": datetime.utcnow(),
        }


def _to_qlib_instrument(symbol: Any) -> str | None:
    raw = str(symbol or "").strip().upper().replace(".SH", "").replace(".SZ", "")
    if not raw:
        return None
    if raw.startswith(("SH", "SZ")):
        return raw
    if raw.startswith(("6", "9")) or raw.startswith("688"):
        return f"SH{raw}"
    if raw.startswith(("0", "2", "3")):
        return f"SZ{raw}"
    return raw
