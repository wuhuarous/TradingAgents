"""Stock symbol utilities — normalization, market detection, code conversion"""
import re


def normalize_symbol(symbol: str) -> str:
    """Strip sh/sz/bj prefix, ensure 6 digits.  'sh600519' → '600519'"""
    s = symbol.strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.zfill(6)


def to_sina_code(symbol: str) -> str:
    """600519 → sh600519, 000001 → sz000001"""
    s = normalize_symbol(symbol)
    if s.startswith(("6", "9")):
        return f"sh{s}"
    return f"sz{s}"


def to_tencent_code(symbol: str) -> str:
    """Alias for to_sina_code — same format"""
    return to_sina_code(symbol)


def detect_market(symbol: str) -> str:
    """Detect market from symbol prefix. Returns a_stock / hk_stock / us_stock"""
    s = normalize_symbol(symbol)
    if s.startswith(("6", "0", "3", "9", "8", "4")):
        return "a_stock"
    if len(s) <= 5 and s.isdigit():
        return "hk_stock"
    return "us_stock"


def is_a_stock(symbol: str) -> bool:
    return detect_market(symbol) == "a_stock"


def is_hk_stock(symbol: str) -> bool:
    return detect_market(symbol) == "hk_stock"
