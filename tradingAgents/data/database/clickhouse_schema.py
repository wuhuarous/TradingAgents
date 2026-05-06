"""ClickHouse schema — time-series tables for market data"""
from tradingAgents.data.database.connection import get_ch_client


def init_clickhouse():
    ch = get_ch_client()

    ch.command("""
        CREATE TABLE IF NOT EXISTS market_quotes (
            symbol String,
            name String,
            market String,
            price Float64,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64,
            amount Float64,
            change_pct Float64,
            pe Float64,
            pb Float64,
            market_cap Float64,
            turnover Float64,
            timestamp DateTime DEFAULT now(),
            date Date DEFAULT toDate(timestamp)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, timestamp)
    """)

    ch.command("""
        CREATE TABLE IF NOT EXISTS kline_daily (
            symbol String,
            date Date,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume UInt64,
            ma5 Float64,
            ma10 Float64,
            ma20 Float64,
            ma60 Float64,
            macd Float64,
            macd_signal Float64,
            macd_hist Float64,
            rsi14 Float64,
            k Float64,
            d Float64,
            j Float64,
            boll_upper Float64,
            boll_mid Float64,
            boll_lower Float64
        ) ENGINE = ReplacingMergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, date)
    """)
