"""
华尔街见闻 (wallstreetcn.com) - API 抓取
免费，无需 API Key
"""
from typing import List
from datetime import datetime
from .base import BaseCrawler


class WallstreetcnCrawler(BaseCrawler):
    """华尔街见闻 - 快讯 + 文章"""
    
    def __init__(self):
        super().__init__("wallstreetcn", "华尔街见闻")
    
    def fetch(self) -> List[dict]:
        articles = []
        
        # 快讯 API
        try:
            resp = self.client.get(
                "https://api-one.wallstcn.com/apiv1/content/lives",
                params={"channel": "global-channel", "limit": 30},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("items", [])
                for item in items:
                    pub_time = datetime.fromtimestamp(
                        item.get("display_time", 0)
                    ).isoformat()
                    title = item.get("title", "") or item.get("content_text", "")[:50]
                    articles.append(self.make_article(
                        title=title,
                        url=f"https://wallstreetcn.com/livenews/{item.get('id', '')}",
                        content=item.get("content_text", ""),
                        published_at=pub_time,
                        tags=self._extract_tags(title),
                    ))
        except Exception as e:
            print(f"[华尔街见闻] 快讯失败: {e}")
        
        # 文章 API
        try:
            resp = self.client.get(
                "https://api-one.wallstcn.com/apiv1/content/articles/hot",
                params={"period": "all", "limit": 20},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("day_items", [])
                for item in items:
                    pub_time = datetime.fromtimestamp(
                        item.get("display_time", 0)
                    ).isoformat()
                    articles.append(self.make_article(
                        title=item.get("title", ""),
                        url=f"https://wallstreetcn.com/articles/{item.get('id', '')}",
                        content=item.get("content_text", ""),
                        summary=item.get("content_short", ""),
                        published_at=pub_time,
                        tags=self._extract_tags(item.get("title", "")),
                    ))
        except Exception as e:
            print(f"[华尔街见闻] 文章失败: {e}")
        
        return articles
