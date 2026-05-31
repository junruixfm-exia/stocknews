"""
新浪财经 (sina.com.cn) - RSS + API 抓取
免费，无需 API Key
"""
import re
from typing import List
import feedparser
from .base import BaseCrawler


class SinaCrawler(BaseCrawler):
    """新浪财经"""
    
    def __init__(self):
        super().__init__("sina", "新浪财经")
    
    def fetch(self) -> List[dict]:
        articles = []
        
        # 新浪财经 RSS
        rss_urls = [
            "https://feed.mix.sina.com.cn/api/roll/get",
            "https://finance.sina.com.cn/roll/index.d.html",
        ]
        
        # 方法1：API
        try:
            resp = self.client.get(
                "https://feed.mix.sina.com.cn/api/roll/get",
                params={
                    "pageid": 153,
                    "lid": "2509",
                    "num": 30,
                    "versionNumber": "1.2.4",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("result", {}).get("data", []):
                    title = item.get("title", "")
                    if not title:
                        continue
                    # 转换 Unix 时间戳为北京时间
                    pub_time = None
                    ctime = item.get("ctime", "")
                    if ctime and str(ctime).isdigit():
                        try:
                            pub_time = self.ts_to_cst(int(ctime))
                        except Exception:
                            pass
                    articles.append(self.make_article(
                        title=title,
                        url=item.get("url", ""),
                        summary=item.get("intro", ""),
                        published_at=pub_time,
                        tags=self._extract_tags(title),
                    ))
        except Exception as e:
            print(f"[新浪财经] API 失败: {e}")
        
        # 方法2：爬取滚动新闻页
        try:
            resp = self.client.get(
                "https://finance.sina.com.cn/roll/index.d.html",
                timeout=15,
            )
            if resp.status_code == 200:
                # 匹配 <a href="链接" target="_blank">标题<span>时间</span></a>
                pattern = re.compile(
                    r'<a[^>]*href="(https?://finance\.sina\.com\.cn/[^"]+)"[^>]*>(.*?)</a>',
                    re.DOTALL,
                )
                matches = pattern.findall(resp.text)
                for url, html_title in matches[:20]:
                    title = re.sub(r'<[^>]+>', '', html_title).strip()
                    if len(title) > 5:
                        articles.append(self.make_article(
                            title=title,
                            url=url,
                            tags=self._extract_tags(title),
                        ))
        except Exception as e:
            print(f"[新浪财经] 爬取失败: {e}")
        
        return articles
