"""A股数据源 — Sina/Tencent 直连 API（主） + AkShare（备，仅财务/K线）"""
import logging
import re
import time
import pandas as pd
import requests
from datetime import datetime
from urllib3.util.retry import Retry

from tradingAgents.data.cache import ttl_cache
from tradingAgents.data.universe import get_universe_symbols
from tradingAgents.engine.dataflows.interface import DataSourceProvider, Market, NewsItem, StockQuote

logger = logging.getLogger(__name__)

STOCK_CACHE_TTL = 45
FULL_LIST_CACHE_TTL = 120
FINANCIALS_CACHE_TTL = 1800
HISTORY_CACHE_TTL = 300

# ── HTTP Session with retry (Sina/Tencent 直连) ──
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
        _session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    return _session


def _prepend_market(symbol: str) -> str:
    """600519 → sh600519 / 000001 → sz000001"""
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


# ═══════════════════════════════════════════════════════════════
# 实时行情 — 腾讯主 + 新浪备
# ═══════════════════════════════════════════════════════════════

def _fetch_tencent_batch(symbols: list[str]) -> dict[str, dict]:
    """腾讯 qt.gtimg.cn 批量行情（单次请求）"""
    if not symbols:
        return {}
    codes = [f"sh{s}" if s.startswith(("6", "9")) else f"sz{s}" for s in symbols]
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    try:
        resp = _get_session().get(url, timeout=10)
        resp.encoding = "gbk"
        results = {}
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            try:
                # v_sh600519="..." 格式
                code_part = line.split("=")[0].strip()
                raw_code = code_part.replace('v_', '').replace('sh', '').replace('sz', '')
                raw_code = raw_code.strip('"').strip("'")
                value_str = line.split("=", 1)[1].strip().strip('"').strip(";")
                parts = value_str.split("~")
                if len(parts) < 40:
                    continue
                results[raw_code] = {
                    "name": parts[1],
                    "price": float_safe(parts[3]),
                    "close": float_safe(parts[4]),
                    "open": float_safe(parts[5]),
                    "volume": int_safe(parts[6]),
                    "high": float_safe(parts[33]),
                    "low": float_safe(parts[34]),
                    "amount": float_safe(parts[37]) * 10000 if parts[37] else 0,
                    "turnover": float_safe(parts[38]),
                    "pe": float_safe(parts[39]),
                    "market_cap": float_safe(parts[45]),
                    "pb": float_safe(parts[46]),
                }
            except Exception:
                continue
        return results
    except Exception as e:
        logger.debug("Tencent batch fetch failed: %s", e)
        return {}


def _fetch_sina_single(symbol: str) -> dict | None:
    """新浪 hq.sinajs.cn 单股行情"""
    code = _prepend_market(symbol)
    url = f"https://hq.sinajs.cn/list={code}"
    try:
        s = _get_session()
        s.headers["Referer"] = "https://finance.sina.com.cn/"
        resp = s.get(url, timeout=10)
        resp.encoding = "gbk"
        text = resp.text.strip()
        if not text or "=" not in text:
            return None
        value_str = text.split("=", 1)[1].strip().strip('"').strip(";")
        fields = value_str.split(",")
        if len(fields) < 10:
            return None
        return {
            "name": fields[0],
            "open": float_safe(fields[1]),
            "close": float_safe(fields[2]),
            "price": float_safe(fields[3]),
            "high": float_safe(fields[4]),
            "low": float_safe(fields[5]),
            "volume": int_safe(fields[8]),
            "amount": float_safe(fields[9]),
        }
    except Exception as e:
        logger.debug("Sina quote failed for %s: %s", symbol, e)
        return None


def _fetch_sina_kline(symbol: str, days: int = 252) -> pd.DataFrame:
    """新浪日K线直连 — 比 AkShare 更快更稳定"""
    code = _prepend_market(symbol)
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale=240&ma=no&datalen={days}"
    try:
        resp = _get_session().get(url, timeout=15)
        data = resp.json()
        if not data:
            return pd.DataFrame()
        rows = []
        for d in data:
            rows.append({
                "日期": d.get("day", ""),
                "开盘": float_safe(d.get("open")),
                "最高": float_safe(d.get("high")),
                "最低": float_safe(d.get("low")),
                "收盘": float_safe(d.get("close")),
                "成交量": int_safe(d.get("volume")),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["日期"] = pd.to_datetime(df["日期"])
            df.set_index("日期", inplace=True)
        return df
    except Exception as e:
        logger.debug("Sina kline failed for %s: %s", symbol, e)
        return pd.DataFrame()


def _fetch_sina_indices(codes: list[str]) -> dict[str, dict]:
    """新浪指数行情 — hq.sinajs.cn（代码: s_sh000001, s_sz399001, s_sz399006）"""
    if not codes:
        return {}
    url = "https://hq.sinajs.cn/list=" + ",".join(codes)
    try:
        s = _get_session()
        s.headers["Referer"] = "https://finance.sina.com.cn/"
        resp = s.get(url, timeout=10)
        resp.encoding = "gbk"
        results = {}
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            raw_code = line.split("=")[0].strip().replace("var hq_str_", "").strip('"').strip("'")
            value_str = line.split("=", 1)[1].strip().strip('"').strip(";")
            fields = value_str.split(",")
            if len(fields) < 4:
                continue
            results[raw_code] = {
                "name": fields[0],
                "price": float_safe(fields[1]),
                "change_amount": float_safe(fields[2]),
                "change_pct": float_safe(fields[3]) / 100,
                "volume": int_safe(fields[4]) if len(fields) > 4 else 0,
                "amount": float_safe(fields[5]) if len(fields) > 5 else 0,
            }
        return results
    except Exception as e:
        logger.debug("Sina indices fetch failed: %s", e)
        return {}


# ═══════════════════════════════════════════════════════════════
# AStockProvider
# ═══════════════════════════════════════════════════════════════

class AStockProvider(DataSourceProvider):

    @ttl_cache(ttl=FULL_LIST_CACHE_TTL, skip_first_arg=True)
    def _get_full_list(self) -> dict[str, dict]:
        """获取 A 股全量行情快照 — 腾讯批量接口，缓存 2 分钟"""
        # 常见 A 股列表（用热门股票覆盖主要标的）
        symbols = _get_all_a_symbols()
        # 分批发请求（腾讯单次可带多只）
        results = {}
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            results.update(_fetch_tencent_batch(batch))
            time.sleep(0.05)  # 避免触发限流
        return results

    def get_realtime_quote(self, symbol: str, market: Market) -> StockQuote:
        # 1. 先查缓存全量列表
        full = self._get_full_list()
        if symbol in full:
            d = full[symbol]
            price = d.get("price", 0)
            prev = d.get("close", 0)
            return StockQuote(
                symbol=symbol,
                name=str(d.get("name", "")),
                price=price,
                open=d.get("open", 0),
                high=d.get("high", 0),
                low=d.get("low", 0),
                close=prev,
                volume=d.get("volume", 0),
                change_pct=(price - prev) / prev if prev else 0,
                market=Market.A,
            )

        # 2. 腾讯单股请求
        single = _fetch_tencent_batch([symbol])
        if symbol in single:
            d = single[symbol]
            price = d.get("price", 0)
            prev = d.get("close", 0)
            return StockQuote(
                symbol=symbol, name=str(d.get("name", "")),
                price=price, open=d.get("open", 0), high=d.get("high", 0),
                low=d.get("low", 0), close=prev, volume=d.get("volume", 0),
                change_pct=(price - prev) / prev if prev else 0,
                market=Market.A,
            )

        # 3. 新浪单股回退
        return self._get_quote_sina(symbol)

    def _get_quote_sina(self, symbol: str) -> StockQuote:
        d = _fetch_sina_single(symbol)
        if d:
            price = d.get("price", 0)
            prev = d.get("close", 0)
            return StockQuote(
                symbol=symbol, name=str(d.get("name", "")),
                price=price, open=d.get("open", 0), high=d.get("high", 0),
                low=d.get("low", 0), close=prev, volume=d.get("volume", 0),
                change_pct=(price - prev) / prev if prev else 0,
                market=Market.A,
            )

        # 4. AkShare 历史接口回退
        return self._get_quote_akshare_hist(symbol)

    def _get_quote_akshare_hist(self, symbol: str) -> StockQuote:
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                price = float_safe(latest.get("收盘"))
                prev_close = float_safe(prev.get("收盘")) if len(df) > 1 else price
                return StockQuote(
                    symbol=symbol, name=symbol, price=price,
                    open=float_safe(latest.get("开盘")), high=float_safe(latest.get("最高")),
                    low=float_safe(latest.get("最低")), close=prev_close,
                    volume=int_safe(latest.get("成交量")),
                    change_pct=(price - prev_close) / prev_close if prev_close else 0,
                    market=Market.A,
                )
        except Exception as e:
            logger.debug("AkShare history fallback failed for %s: %s", symbol, e)
        return StockQuote(symbol=symbol, name=symbol, market=Market.A)

    @ttl_cache(ttl=HISTORY_CACHE_TTL, skip_first_arg=True)
    def get_historical(self, symbol: str, market: Market, period: str = "1mo") -> pd.DataFrame:
        days_map = {"5d": 5, "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}
        days = days_map.get(period, 22)

        # 1. 新浪 K 线直连
        df = _fetch_sina_kline(symbol, days)
        if not df.empty:
            return df

        # 2. AkShare K 线回退
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if df is not None and not df.empty:
                if "日期" in df.columns:
                    df["日期"] = pd.to_datetime(df["日期"])
                    df.set_index("日期", inplace=True)
                return df.tail(days)
        except Exception as e:
            logger.warning("AkShare history failed for %s: %s", symbol, e)

        return pd.DataFrame()

    @ttl_cache(ttl=FINANCIALS_CACHE_TTL, skip_first_arg=True)
    def get_financials(self, symbol: str, market: Market) -> dict:
        # Valuation data from Tencent batch (PE / PB / market cap)
        valuation = {}
        full = self._get_full_list()
        if symbol in full:
            d = full[symbol]
            if d.get("pe"):
                valuation["pe_ratio"] = d["pe"]
            if d.get("pb"):
                valuation["pb_ratio"] = d["pb"]
            if d.get("market_cap"):
                valuation["market_cap"] = d["market_cap"]

        # Income statement from THS
        income = {}
        try:
            import akshare as ak
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                income = {
                    "revenue": float_safe(str(latest.get("营业总收入", "")).replace("亿", "")) * 1e8,
                    "net_income": float_safe(str(latest.get("净利润", "")).replace("亿", "")) * 1e8,
                    "roe": float_safe(str(latest.get("净资产收益率", "")).replace("%", "")) / 100,
                    "revenue_growth": float_safe(str(latest.get("营业总收入同比增长率", "")).replace("%", "")) / 100,
                    "net_profit_growth": float_safe(str(latest.get("净利润同比增长率", "")).replace("%", "")) / 100,
                    "gross_margin": float_safe(str(latest.get("销售毛利率", "")).replace("%", "")) / 100,
                    "net_margin": float_safe(str(latest.get("销售净利率", "")).replace("%", "")) / 100,
                }
        except Exception as e:
            logger.debug("AkShare THS financials failed: %s", e)

        # Merge valuation + income, fallback to Baidu for missing PE/PB
        result = {**income, **valuation}
        if not result.get("pe_ratio") or not result.get("pb_ratio"):
            try:
                import akshare as ak
                pe_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)")
                pb_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市净率")
                if pe_df is not None and not pe_df.empty and not result.get("pe_ratio"):
                    result["pe_ratio"] = float_safe(pe_df.iloc[-1].get("value"))
                if pb_df is not None and not pb_df.empty and not result.get("pb_ratio"):
                    result["pb_ratio"] = float_safe(pb_df.iloc[-1].get("value"))
            except Exception as e:
                logger.debug("Baidu valuation failed: %s", e)

        return result

    @ttl_cache(ttl=300, skip_first_arg=True)
    def get_news(self, symbol: str, market: Market, limit: int = 10) -> list[NewsItem]:
        items = []
        # 1. 东方财富个股新闻
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=symbol)
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    items.append(NewsItem(
                        title=str(row.get("标题", "")),
                        content=str(row.get("内容", "")),
                        source="东方财富",
                        url=str(row.get("链接", "")),
                    ))
        except Exception:
            pass

        # 2. 新浪个股新闻
        if len(items) < limit:
            try:
                code = _prepend_market(symbol)
                url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{code}.phtml"
                resp = _get_session().get(url, timeout=10)
                resp.encoding = "gbk"
                # 简单解析 <a> 标签中的新闻标题
                from html.parser import HTMLParser
                class NewsParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.titles = []
                        self.in_item = False
                    def handle_starttag(self, tag, attrs):
                        attrs_d = dict(attrs)
                        href = attrs_d.get("href", "")
                        cls = attrs_d.get("class", "")
                        if tag == "a" and ("news" in href or "detail" in href):
                            self.in_item = True
                    def handle_data(self, data):
                        if self.in_item and len(data.strip()) > 5:
                            self.titles.append(data.strip())
                        self.in_item = False
                parser = NewsParser()
                parser.feed(resp.text)
                for t in parser.titles[:limit - len(items)]:
                    items.append(NewsItem(title=t, source="新浪财经"))
            except Exception:
                pass

        return items[:limit]

    @ttl_cache(ttl=FULL_LIST_CACHE_TTL, skip_first_arg=True)
    def search_symbols(self, keyword: str, market: Market) -> list[dict]:
        full = self._get_full_list()
        if not full:
            return []
        matches = []
        for code, d in full.items():
            name = str(d.get("name", ""))
            if keyword in code or keyword in name:
                matches.append({"symbol": code, "name": name})
        return matches[:20]


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _get_all_a_symbols() -> list[str]:
    """Return the configured/dynamic A-share universe used by batch quotes."""
    return get_universe_symbols("a_stock", role="all")


def float_safe(val) -> float:
    try:
        if val is None or val == "" or val == "-":
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def int_safe(val) -> int:
    try:
        if val is None or val == "" or val == "-":
            return 0
        return int(float(val))
    except (TypeError, ValueError):
        return 0
