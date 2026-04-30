"""社交媒体舆情分析 — 基于关键词的情感打分"""
from tradingAgents.engine.dataflows.interface import NewsItem

SENTIMENT_KEYWORDS = {
    "positive": [
        "利好", "大涨", "突破", "增长", "盈利", "买入", "增持", "回购",
        "breakthrough", "surge", "beat", "upgrade", "buy", "growth",
    ],
    "negative": [
        "利空", "大跌", "下跌", "亏损", "减持", "卖出", "监管", "调查",
        "crash", "plunge", "downgrade", "sell", "loss", "investigation",
    ],
}


def analyze_sentiment(text: str) -> float:
    """简单关键词情感打分，范围 [-1, 1]"""
    text_lower = text.lower()
    pos = sum(1 for w in SENTIMENT_KEYWORDS["positive"] if w in text_lower)
    neg = sum(1 for w in SENTIMENT_KEYWORDS["negative"] if w in text_lower)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 2)


def analyze_news_sentiment(news_items: list[NewsItem]) -> list[NewsItem]:
    """对新闻列表批量分析情感分"""
    for item in news_items:
        item.sentiment = analyze_sentiment(f"{item.title} {item.content}")
    return news_items


def aggregate_sentiment(news_items: list[NewsItem]) -> float:
    """聚合多篇新闻的情感均值"""
    if not news_items:
        return 0.0
    scores = [n.sentiment for n in news_items if n.sentiment is not None]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)
