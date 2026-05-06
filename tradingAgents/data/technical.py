"""技术指标计算 — MA/MACD/KDJ/RSI/BOLL，纯 numpy/pandas 实现"""
import pandas as pd
import numpy as np


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """对包含 收盘/最高/最低/开盘/成交量 列的 DataFrame 计算全部技术指标"""
    if df.empty:
        return df
    close = df.get("收盘", df.get("Close"))
    high = df.get("最高", df.get("High"))
    low = df.get("最低", df.get("Low"))
    volume = df.get("成交量", df.get("Volume"))
    if close is None:
        return df

    result = df.copy()
    result["ma5"] = sma(close, 5)
    result["ma10"] = sma(close, 10)
    result["ma20"] = sma(close, 20)
    result["ma60"] = sma(close, 60)
    result["ema12"] = ema(close, 12)
    result["ema26"] = ema(close, 26)
    result["macd"], result["macd_signal"], result["macd_hist"] = macd(close)
    result["rsi14"] = rsi(close, 14)
    result["k"], result["d"], result["j"] = kdj(high, low, close)
    result["boll_upper"], result["boll_mid"], result["boll_lower"] = bollinger(close)
    result["ma_vol5"] = sma(volume, 5) if volume is not None else np.nan
    result["ma_vol10"] = sma(volume, 10) if volume is not None else np.nan
    return result


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m1: int = 3, m2: int = 3):
    low_n = low.rolling(window=n, min_periods=n).min()
    high_n = high.rolling(window=n, min_periods=n).max()
    rsv = ((close - low_n) / (high_n - low_n).replace(0, np.nan)) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def bollinger(close: pd.Series, period: int = 20, std_factor: int = 2):
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()
    upper = mid + std_factor * std
    lower = mid - std_factor * std
    return upper, mid, lower


def signal_summary(df: pd.DataFrame) -> dict:
    """从指标 DataFrame 提取交易信号摘要"""
    if df.empty or len(df) < 2:
        return {}
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signals = {}

    # MACD 金叉/死叉
    if "macd" in df.columns and "macd_signal" in df.columns:
        if latest.get("macd", 0) > latest.get("macd_signal", 0) and prev.get("macd", 0) <= prev.get("macd_signal", 0):
            signals["macd"] = "golden_cross"
        elif latest.get("macd", 0) < latest.get("macd_signal", 0) and prev.get("macd", 0) >= prev.get("macd_signal", 0):
            signals["macd"] = "dead_cross"

    # RSI 超买超卖
    rsi_val = latest.get("rsi14")
    if rsi_val is not None and not pd.isna(rsi_val):
        if rsi_val > 80:
            signals["rsi"] = "overbought"
        elif rsi_val < 20:
            signals["rsi"] = "oversold"

    # KDJ
    k_val, d_val, j_val = latest.get("k"), latest.get("d"), latest.get("j")
    if all(v is not None and not pd.isna(v) for v in [k_val, d_val, j_val]):
        if k_val > 80 and d_val > 80:
            signals["kdj"] = "overbought"
        elif k_val < 20 and d_val < 20:
            signals["kdj"] = "oversold"
        if k_val > d_val and prev.get("k", 0) <= prev.get("d", 0):
            signals["kdj"] = signals.get("kdj", "") + "_golden_cross"

    # 均线排列
    ma5, ma10, ma20 = latest.get("ma5"), latest.get("ma10"), latest.get("ma20")
    if all(v is not None and not pd.isna(v) for v in [ma5, ma10, ma20]):
        if ma5 > ma10 > ma20:
            signals["ma"] = "bullish_alignment"
        elif ma5 < ma10 < ma20:
            signals["ma"] = "bearish_alignment"

    # 布林带位置
    close_val = latest.get("收盘", latest.get("Close"))
    upper, lower = latest.get("boll_upper"), latest.get("boll_lower")
    if all(v is not None and not pd.isna(v) for v in [close_val, upper, lower]):
        if close_val >= upper:
            signals["boll"] = "upper_break"
        elif close_val <= lower:
            signals["boll"] = "lower_break"

    return signals
