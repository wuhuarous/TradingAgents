"""Trading time utilities — A-share market hours, trading day detection"""
from datetime import datetime, time, timedelta

A_MORNING_OPEN = time(9, 30)
A_MORNING_CLOSE = time(11, 30)
A_AFTERNOON_OPEN = time(13, 0)
A_AFTERNOON_CLOSE = time(15, 0)

# Chinese holidays (major ones, needs yearly update)
_CN_HOLIDAYS = {
    # 2026 major holidays (approximate, update yearly)
    "2026-01-01", "2026-01-02",  # 元旦
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # 春节
    "2026-04-06",  # 清明
    "2026-05-01", "2026-05-04", "2026-05-05",  # 劳动节
    "2026-06-22",  # 端午
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",  # 国庆+中秋
}


def is_trading_day(dt: datetime | None = None) -> bool:
    """Check if the given datetime is an A-share trading day"""
    dt = dt or datetime.now()
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    date_str = dt.strftime("%Y-%m-%d")
    if date_str in _CN_HOLIDAYS:
        return False
    return True


def is_trading_time(dt: datetime | None = None) -> bool:
    """Check if the market is currently open"""
    dt = dt or datetime.now()
    if not is_trading_day(dt):
        return False
    t = dt.time()
    return (A_MORNING_OPEN <= t <= A_MORNING_CLOSE) or (A_AFTERNOON_OPEN <= t <= A_AFTERNOON_CLOSE)


def is_morning_session(dt: datetime | None = None) -> bool:
    dt = dt or datetime.now()
    return A_MORNING_OPEN <= dt.time() <= A_MORNING_CLOSE


def is_afternoon_session(dt: datetime | None = None) -> bool:
    dt = dt or datetime.now()
    return A_AFTERNOON_OPEN <= dt.time() <= A_AFTERNOON_CLOSE


def is_lunch_break(dt: datetime | None = None) -> bool:
    dt = dt or datetime.now()
    return A_MORNING_CLOSE < dt.time() < A_AFTERNOON_OPEN


def next_trading_time(dt: datetime | None = None) -> datetime:
    """Return the next A-share trading session start time"""
    dt = dt or datetime.now()
    t = dt.time()

    if is_trading_day(dt):
        if t < A_MORNING_OPEN:
            return dt.replace(hour=9, minute=30, second=0, microsecond=0)
        if is_lunch_break(dt):
            return dt.replace(hour=13, minute=0, second=0, microsecond=0)
        if t > A_AFTERNOON_CLOSE:
            dt = dt + timedelta(days=1)
        else:
            return dt  # currently trading

    # Find next trading day
    while not is_trading_day(dt):
        dt = dt + timedelta(days=1)
    return dt.replace(hour=9, minute=30, second=0, microsecond=0)
