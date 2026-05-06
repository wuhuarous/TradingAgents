"""Database connections — PostgreSQL async + ClickHouse sync"""
import logging
from urllib.parse import urlparse

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from tradingAgents.config.settings import settings

logger = logging.getLogger(__name__)

_pg_engine = None
_pg_sessionmaker = None
_ch_client = None


def get_pg_engine():
    global _pg_engine
    if _pg_engine is None:
        _pg_engine = create_async_engine(
            settings.postgresql_url,
            poolclass=NullPool,
            echo=False,
        )
    return _pg_engine


def get_pg_session() -> AsyncSession:
    global _pg_sessionmaker
    if _pg_sessionmaker is None:
        _pg_sessionmaker = async_sessionmaker(get_pg_engine(), expire_on_commit=False)
    return _pg_sessionmaker()


async def init_pg():
    """Create all tables if not exist"""
    from tradingAgents.data.database.models import Base
    engine = get_pg_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables initialized")


def get_ch_client():
    global _ch_client
    if _ch_client is None:
        import clickhouse_connect
        parsed = urlparse(settings.clickhouse_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8123
        bootstrap = clickhouse_connect.get_client(
            host=host,
            port=port,
            database="default",
            username="default",
            password="",
        )
        bootstrap.command(f"CREATE DATABASE IF NOT EXISTS {settings.clickhouse_database}")
        _ch_client = clickhouse_connect.get_client(
            host=host,
            port=port,
            database=settings.clickhouse_database,
            username="default",
            password="",
        )
    return _ch_client
