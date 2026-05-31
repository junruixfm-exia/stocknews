"""
东方财富 (eastmoney.com) - 页面爬取 + API
免费，无需 API Key
"""
import re
from typing import List
from datetime import datetime, timezone, timedelta
from .base import BaseCrawler


class EastmoneyCrawler(BaseCrawler):
    """东方财富 - 要闻"""

    CST = timezone(timedelta(hours=8))

    PAGE_URLS = [
        ("https://finance.eastmoney.com/a/czqyw.html", "要闻"),
        ("https://finance.eastmoney.com/a/cyxw.html", "行业"),
    ]

    def __init__(self):
        super().__init__("eastmoney", "东方财富")

    def fetch(self) -> List[dict]:
        articles = []

        for page_url, category in self.PAGE_URLS:
            try:
                resp = self.client.get(
                    page_url,
                    headers={"Accept": "text/html"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue

                # 匹配新闻链接: <a href="/a/xxx.html">标题</a>
                pattern = re.compile(
                    r'<a[^>]*href="(https?://finance\.eastmoney\.com/a/[^"]+\.html)"[^>]*>(.{10,100}?)</a>',
                    re.DOTALL,
                )
                matches = pattern.findall(resp.text)

                seen_urls = set()
                count = 0
                for url, raw_title in matches:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = re.sub(r"<[^>]+>", "", raw_title).strip()
                    if len(title) < 10:
                        continue

                    # 错开时间戳：每篇递减3分钟，避免全部挤在一起
                    minutes_ago = count * 3
                    pub_time = datetime.now(self.CST) - timedelta(minutes=minutes_ago)

                    articles.append(
                        self.make_article(
                            title=title,
                            url=url,
                            tags=[category] + self._extract_tags(title),
                            published_at=pub_time.isoformat(),
                        )
                    )
                    count += 1

                print(f"[东方财富] ✓ {category}: {count} 篇")

            except Exception as e:
                print(f"[东方财富] {category} 失败: {e}")

        return articles
