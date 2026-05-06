"""Append-only JSONL storage for trading data events.

This is intentionally lightweight: it gives the simulator a durable audit
trail before a full database pipeline is introduced.
"""
from __future__ import annotations

import hashlib
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg

from tradingAgents.config.settings import settings

STORE_DIR = Path(settings.memory_dir) / "events"
logger = logging.getLogger(__name__)
_DB_DISABLED = False


def event_id(kind: str, payload: dict[str, Any]) -> str:
    basis = {
        "kind": kind,
        "market": payload.get("market"),
        "symbol": payload.get("symbol"),
        "source": payload.get("source"),
        "url": payload.get("url"),
        "title": payload.get("title"),
        "run_id": payload.get("run_id"),
        "horizon": payload.get("horizon"),
        "action": payload.get("action"),
        "created_at": payload.get("created_at") or payload.get("published_at"),
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def append_event(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_id": payload.get("event_id") or event_id(kind, payload),
        "kind": kind,
        "stored_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    if _write_event_db(event):
        return event
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    path = STORE_DIR / f"{kind}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return event


def append_events(kind: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [append_event(kind, payload) for payload in payloads]


def read_events(kind: str, limit: int = 100) -> list[dict[str, Any]]:
    db_rows = _read_events_db(kind, limit)
    if db_rows is not None:
        return db_rows
    path = STORE_DIR / f"{kind}.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:][::-1]


def database_status() -> dict[str, Any]:
    ok = _ping_db()
    return {
        "enabled": not _DB_DISABLED,
        "connected": ok,
        "target": _safe_dsn(settings.postgresql_url),
        "fallback": str(STORE_DIR),
    }


async def database_status_async() -> dict[str, Any]:
    global _DB_DISABLED
    try:
        ok = await _ping_db_async()
        if ok:
            _DB_DISABLED = False
    except Exception:
        ok = False
    return {
        "enabled": not _DB_DISABLED,
        "connected": ok,
        "target": _safe_dsn(settings.postgresql_url),
        "fallback": str(STORE_DIR),
    }


def _write_event_db(event: dict[str, Any]) -> bool:
    if _DB_DISABLED:
        return False
    if _has_running_loop():
        return False
    try:
        return _run_db(_write_event_db_async(event))
    except Exception as exc:
        _disable_db_once(exc)
        return False


async def _write_event_db_async(event: dict[str, Any]) -> bool:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        await _ensure_table(conn)
        await conn.execute(
            """
            INSERT INTO data_events (
                event_id, kind, market, symbol, source, quality_score, payload, stored_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7::json, $8)
            ON CONFLICT (event_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                quality_score = EXCLUDED.quality_score,
                stored_at = EXCLUDED.stored_at
            """,
            str(event.get("event_id", "")),
            str(event.get("kind", "")),
            str(event.get("market", "")),
            str(event.get("symbol", "")),
            str(event.get("source", ""))[:120],
            float(event.get("quality_score") or 0),
            json.dumps(event, ensure_ascii=False, default=str),
            _parse_dt(event.get("stored_at")),
        )
        return True
    finally:
        await conn.close()


def _read_events_db(kind: str, limit: int) -> list[dict[str, Any]] | None:
    if _DB_DISABLED:
        return None
    if _has_running_loop():
        return None
    try:
        return _run_db(_read_events_db_async(kind, limit))
    except Exception as exc:
        _disable_db_once(exc)
        return None


async def _read_events_db_async(kind: str, limit: int) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        await _ensure_table(conn)
        rows = await conn.fetch(
            """
            SELECT payload
            FROM data_events
            WHERE kind = $1
            ORDER BY stored_at DESC
            LIMIT $2
            """,
            kind,
            limit,
        )
        results = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                results.append(json.loads(payload))
            else:
                results.append(dict(payload))
        return results
    finally:
        await conn.close()


def _ping_db() -> bool:
    global _DB_DISABLED
    if _has_running_loop():
        return False
    try:
        ok = bool(_run_db(_ping_db_async()))
        if ok:
            _DB_DISABLED = False
        return ok
    except Exception:
        return False


async def _ping_db_async() -> bool:
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        await _ensure_table(conn)
        value = await conn.fetchval("SELECT 1")
        return value == 1
    finally:
        await conn.close()


async def _ensure_table(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_events (
            event_id VARCHAR(40) PRIMARY KEY,
            kind VARCHAR(40) NOT NULL,
            market VARCHAR(20) DEFAULT '',
            symbol VARCHAR(40) DEFAULT '',
            source VARCHAR(120) DEFAULT '',
            quality_score DOUBLE PRECISION DEFAULT 0,
            payload JSON NOT NULL,
            stored_at TIMESTAMP DEFAULT now()
        )
        """
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS ix_data_events_kind ON data_events(kind)")
    await conn.execute("CREATE INDEX IF NOT EXISTS ix_data_events_market ON data_events(market)")
    await conn.execute("CREATE INDEX IF NOT EXISTS ix_data_events_symbol ON data_events(symbol)")
    await conn.execute("CREATE INDEX IF NOT EXISTS ix_data_events_stored_at ON data_events(stored_at)")


def _run_db(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("event_store sync database calls cannot run inside an active event loop")


def _has_running_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _asyncpg_dsn() -> str:
    return settings.postgresql_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            pass
    return datetime.now()


def _safe_dsn(dsn: str) -> str:
    if "@" not in dsn:
        return dsn
    prefix, suffix = dsn.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0]
    return f"{scheme}://***@{suffix}"


def _disable_db_once(exc: Exception) -> None:
    global _DB_DISABLED
    if not _DB_DISABLED:
        logger.warning("Data event database write disabled, falling back to JSONL: %s", exc)
    _DB_DISABLED = True
