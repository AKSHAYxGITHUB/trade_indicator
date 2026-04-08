"""News fetching and sentiment tagging utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from xml.etree import ElementTree

import requests
from newsapi import NewsApiClient

from config import NEWS_API_KEY
from logger import LOGGER

POSITIVE = ["surge", "gain", "rise", "profit", "record", "growth", "rally", "buy", "upgrade", "strong", "beat", "high"]
NEGATIVE = ["fall", "drop", "loss", "crash", "decline", "sell", "downgrade", "weak", "miss", "low", "cut", "risk"]


def _detect_sentiment(text: str) -> str:
    """Detect sentiment from headline text.

    Args:
        text: Headline/content snippet.

    Returns:
        POSITIVE, NEGATIVE, or NEUTRAL sentiment label.
    """
    lower = (text or "").lower()
    pos = sum(word in lower for word in POSITIVE)
    neg = sum(word in lower for word in NEGATIVE)
    if pos > neg:
        return "POSITIVE"
    if neg > pos:
        return "NEGATIVE"
    return "NEUTRAL"


def _fetch_google_news(query: str) -> list[dict[str, Any]]:
    """Fetch fallback stock news from Google News RSS.

    Args:
        query: Search query for stock-specific news.

    Returns:
        List of normalized article dictionaries.
    """
    try:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        articles = []
        for item in root.findall("./channel/item")[:5]:
            title = item.findtext("title", default="No title")
            link = item.findtext("link", default="")
            source = item.findtext("source", default="Google News")
            pub_date = item.findtext("pubDate", default=datetime.utcnow().isoformat())
            articles.append(
                {
                    "title": title,
                    "source": source,
                    "published_at": pub_date,
                    "url": link,
                    "sentiment": _detect_sentiment(title),
                }
            )
        return articles
    except Exception:
        LOGGER.exception("Google RSS fallback failed.")
        return []


def get_stock_news(company_name: str, symbol: str) -> list[dict[str, Any]]:
    """Fetch top stock news from NewsAPI with RSS fallback.

    Args:
        company_name: Company long name.
        symbol: Stock symbol.

    Returns:
        List of top 5 article dictionaries.
    """
    query = f"{company_name} OR {symbol} stock NSE BSE India"
    if not NEWS_API_KEY:
        return _fetch_google_news(query)

    try:
        client = NewsApiClient(api_key=NEWS_API_KEY)
        payload = client.get_everything(
            q=query,
            language="en",
            sort_by="publishedAt",
            page_size=5,
        )
        articles = []
        for article in payload.get("articles", []):
            title = article.get("title") or "No title"
            articles.append(
                {
                    "title": title,
                    "source": (article.get("source") or {}).get("name", "Unknown"),
                    "published_at": article.get("publishedAt", ""),
                    "url": article.get("url", ""),
                    "sentiment": _detect_sentiment(title),
                }
            )
        return articles[:5] if articles else _fetch_google_news(query)
    except Exception:
        LOGGER.exception("NewsAPI fetch failed, switching to RSS fallback.")
        return _fetch_google_news(query)
