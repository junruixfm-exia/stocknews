"""
Wall Street Journal - RSS 抓取（国际财经新闻，英文→中文翻译）
"""
from typing import List
from datetime import datetime, timezone
import feedparser
from .base import BaseCrawler
from translator import translate_text


class WSJCrawler(BaseCrawler):
    """WSJ Markets - RSS"""

    FEED_URL = "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"

    def __init__(self):
        super().__init__("wsj", "WSJ")

    def fetch(self) -> List[dict]:
        articles = []

        try:
            resp = self.client.get(self.FEED_URL, timeout=15)
            if resp.status_code != 200:
                print(f"[WSJ] HTTP {resp.status_code}")
                return articles

            feed = feedparser.parse(resp.text)
            if not feed.entries:
                print("[WSJ] 无条目")
                return articles

            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                if not title or len(title) < 10:
                    continue

                cn_title = translate_text(title)
                display_title = f"[EN] {title}"
                summary = f"📰 {cn_title}" if cn_title else ""

                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        from time import mktime
                        pub_time = datetime.fromtimestamp(
                            mktime(entry.published_parsed)
                        ).isoformat()
                    except Exception:
                        pass
                if not pub_time:
                    pub_time = datetime.now(timezone.utc).isoformat()

                articles.append(
                    self.make_article(
                        title=display_title,
                        url=entry.get("link", ""),
                        summary=summary,
                        content=entry.get("summary", ""),
                        published_at=pub_time,
                        tags=["美股", "国际"] + self._extract_tags(title),
                    )
                )

            print(f"[WSJ] ✓ {len(articles)} 篇")

        except Exception as e:
            print(f"[WSJ] 失败: {e}")

        return articles
