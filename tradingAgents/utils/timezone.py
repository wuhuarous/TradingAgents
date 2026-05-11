"""Timezone helpers that work on Windows without the optional tzdata package."""
from __future__ import annotations

from datetime import timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def china_tz():
    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), name="Asia/Shanghai")


CN_TZ = china_tz()
