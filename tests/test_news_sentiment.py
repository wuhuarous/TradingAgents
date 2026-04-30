"""Tests for news collection and sentiment analysis"""
import pytest
from tradingAgents.engine.dataflows.interface import NewsItem
from tradingAgents.data.social.sentiment import (
    analyze_sentiment,
    analyze_news_sentiment,
    aggregate_sentiment,
)


class TestSentimentAnalysis:
    def test_positive_keywords(self):
        score = analyze_sentiment("利好大涨 公司盈利突破增长")
        assert score > 0

    def test_negative_keywords(self):
        score = analyze_sentiment("利空大跌 公司亏损减持")
        assert score < 0

    def test_neutral_text(self):
        score = analyze_sentiment("今天天气不错")
        assert score == 0.0

    def test_mixed_sentiment(self):
        score = analyze_sentiment("利好大涨 但也面临监管调查")
        # 2 positive + 2 negative => 0
        assert score == 0.0

    def test_english_positive(self):
        score = analyze_sentiment("stock surge on strong growth and buy upgrade")
        assert score > 0

    def test_english_negative(self):
        score = analyze_sentiment("crash plunge on loss and downgrade sell")
        assert score < 0

    def test_score_range(self):
        for text in ["利好", "利空", "利好 大涨 突破", "nothing"]:
            score = analyze_sentiment(text)
            assert -1.0 <= score <= 1.0


class TestNewsSentimentBatch:
    def test_analyze_news_sentiment(self):
        items = [
            NewsItem(title="公司业绩大涨", content="利润创新高"),
            NewsItem(title="监管处罚公告", content="公司被调查"),
        ]
        result = analyze_news_sentiment(items)
        assert result[0].sentiment is not None
        assert result[1].sentiment is not None
        assert result[0].sentiment > 0
        assert result[1].sentiment < 0

    def test_aggregate_empty(self):
        assert aggregate_sentiment([]) == 0.0

    def test_aggregate_no_scores(self):
        items = [NewsItem(title="test", content="test")]
        # No sentiment assigned
        assert aggregate_sentiment(items) == 0.0

    def test_aggregate_mixed(self):
        items = [
            NewsItem(title="利好", content="", sentiment=1.0),
            NewsItem(title="利空", content="", sentiment=-0.5),
        ]
        assert aggregate_sentiment(items) == 0.25
