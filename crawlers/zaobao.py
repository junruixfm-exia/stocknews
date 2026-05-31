"""
联合早报 (zaobao.com.sg) - 实时新闻 HTML 抓取
新加坡中文媒体，无需 API Key
"""
import re
from typing import List
from datetime import datetime, timedelta
from .base import BaseCrawler


class ZaobaoCrawler(BaseCrawler):
    """联合早报 - 实时新闻"""

    PAGES = [
        ("https://www.zaobao.com/realtime", "实时"),
        ("https://www.zaobao.com/finance", "财经"),
    ]

    def __init__(self):
        super().__init__("zaobao", "联合早报")

    def fetch(self) -> List[dict]:
        articles = []
        seen_urls = set()

        for page_url, category in self.PAGES:
            try:
                resp = self.client.get(page_url, timeout=15)
                if resp.status_code != 200:
                    print(f"[联合早报] {category} HTTP {resp.status_code}")
                    continue

                html = resp.text

                # 提取标题时间 + 标题 + 链接
                # 格式: <a href="/realtime/.../story..."><span class="time">HH:MM</span> 标题</a>
                # 或: <a href="/realtime/.../story...">标题</a> 前面有时间标记

                # 模式1: 链接中包含 story 路径的文章
                story_pattern = re.compile(
                    r'<a[^>]*href="(/realtime/[^"]+/story\d+[^"]*|/news/[^"]+/story\d+[^"]*|/finance/[^"]+/story\d+[^"]*)"[^>]*>'
                    r'(.*?)'
                    r'</a>',
                    re.DOTALL,
                )

                matches = story_pattern.findall(html)
                count = 0

                for href, inner_html in matches:
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # 清理 inner_html 获取纯文本标题
                    title = re.sub(r"<[^>]+>", " ", inner_html)
                    title = re.sub(r"\s+", " ", title).strip()

                    if len(title) < 8:
                        continue

                    # 尝试提取时间（格式：HH:MM 在标题开头或 span 中）
                    time_match = re.match(r"(\d{1,2}:\d{2})\s*", title)
                    pub_time = None
                    if time_match:
                        time_str = time_match.group(1)
                        title = title[len(time_str) :].strip()
                        try:
                            hour, minute = map(int, time_str.split(":"))
                            now = datetime.now()
                            pub_time = now.replace(
                                hour=hour, minute=minute, second=0, microsecond=0
                            )
                            # 如果时间看起来在未来（比如现在是10:00，文章是23:00），可能是昨天的
                            if pub_time > now:
                                pub_time = pub_time - timedelta(days=1)
                            
                            # 如果文章时间超过24小时前
                            if (now - pub_time) > timedelta(hours=24):
                                continue
                        except (ValueError, TypeError):
                            pub_time = None

                    if not pub_time:
                        # 从 URL 提取日期 story20260531
                        date_match = re.search(r"story(\d{8})", href)
                        if date_match:
                            try:
                                date_str = date_match.group(1)
                                pub_time = datetime.strptime(date_str, "%Y%m%d")
                            except ValueError:
                                pub_time = datetime.now()
                        else:
                            pub_time = datetime.now()

                    url = f"https://www.zaobao.com{href}"

                    articles.append(
                        self.make_article(
                            title=title,
                            url=url,
                            published_at=pub_time.isoformat()
                            if isinstance(pub_time, datetime)
                            else pub_time,
                            tags=["国际", "财经"] + self._extract_tags(title),
                        )
                    )
                    count += 1

                print(f"[联合早报] ✓ {category}: {count} 篇")

            except Exception as e:
                print(f"[联合早报] {category} 失败: {e}")

        return articles
