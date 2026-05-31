"""
CNBC - RSS 抓取（国际财经新闻，英文→中文翻译）
免费 RSS，无需 API Key
"""
from typing import List
from datetime import datetime, timezone, timedelta
import feedparser
from .base import BaseCrawler
from translator import translate_text


class CNBCCrawler(BaseCrawler):
    """CNBC 财经新闻 - RSS"""

    FEEDS = [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "Top News"),
        ("https://www.cnbc.com/id/10001147/device/rss/rss.html", "Markets"),
    ]

    def __init__(self):
        super().__init__("cnbc", "CNBC")

    def fetch(self) -> List[dict]:
        articles = []

        for feed_url, category in self.FEEDS:
            try:
                resp = self.client.get(feed_url, timeout=15)
                if resp.status_code != 200:
                    print(f"[CNBC] {category} HTTP {resp.status_code}")
                    continue

                feed = feedparser.parse(resp.text)
                if not feed.entries:
                    print(f"[CNBC] {category} 无条目")
                    continue

                count = 0
                for entry in feed.entries[:20]:
                    title = entry.get("title", "")
                    if not title or len(title) < 10:
                        continue

                    # 翻译标题
                    cn_title = translate_text(title)
                    display_title = f"[EN] {title}"
                    summary = f"📰 {cn_title}" if cn_title else ""

                    # 发布时间
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

                    link = entry.get("link", "")

                    articles.append(
                        self.make_article(
                            title=display_title,
                            url=link,
                            summary=summary,
                            content=entry.get("summary", ""),
                            published_at=pub_time,
                            tags=["美股", "国际"] + self._extract_tags(title),
                        )
                    )
                    count += 1

                print(f"[CNBC] ✓ {category}: {count} 篇")
            except Exception as e:
                print(f"[CNBC] {category} 失败: {e}")

        return articles
