"""
模組一：抓取台灣財經新聞（RSS）
來源：工商時報、經濟日報、MoneyDJ、鉅亨網
"""

import feedparser
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEEDS = {
    "工商時報":  "https://ctee.com.tw/feed",
    "經濟日報":  "https://money.udn.com/rssfeed/news/1001/5591?ch=money",
    "MoneyDJ":  "https://www.moneydj.com/rss/rssnews.aspx",
    "鉅亨網":    "https://news.cnyes.com/rss/tw_stock",
    "Anue 基金": "https://news.cnyes.com/rss/fund",
}

def fetch_news(max_per_source: int = 6) -> list[dict]:
    """
    回傳格式：[{"source", "title", "link", "published"}]
    """
    all_news = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= max_per_source:
                    break
                all_news.append({
                    "source":    source,
                    "title":     entry.get("title", "").strip(),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
                count += 1
            logger.info(f"✅ {source}：{count} 則")
        except Exception as e:
            logger.error(f"❌ {source} 失敗：{e}")

    return all_news


if __name__ == "__main__":
    news = fetch_news()
    for n in news:
        print(f"[{n['source']}] {n['title']}")
