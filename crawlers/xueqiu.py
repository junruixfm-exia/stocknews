"""
雪球 (xueqiu.com) - API 抓取
免费，无需 API Key（但有频率限制）
"""
import json
from typing import List
from datetime import datetime
from .base import BaseCrawler


class XueqiuCrawler(BaseCrawler):
    """雪球 - 热门文章 + 7x24 快讯"""
    
    def __init__(self):
        super().__init__("xueqiu", "雪球")
        # 雪球反爬较严，需要 Cookie
        self.client.headers.update({
            "Referer": "https://xueqiu.com",
        })
        # 先访问首页获取 Cookie
        try:
            self.client.get("https://xueqiu.com", timeout=15)
        except:
            pass
        self._enabled = False  # Render US IP 被墙，默认禁用
    
    @property
    def enabled(self):
        return self._enabled
    
    def fetch(self) -> List[dict]:
        articles = []
        
        # 热门文章
        try:
            resp = self.client.get(
                "https://xueqiu.com/statuses/hot/listV2.json",
                params={"since_id": "-1", "max_id": "-1", "size": 20},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                for item in items:
                    title = item.get("title", "") or item.get("text", "")[:60]
                    title = title.replace("\n", " ").strip()
                    if not title:
                        continue
                    pub_time = datetime.fromtimestamp(
                        item.get("created_at", 0) / 1000
                    ).isoformat()
                    articles.append(self.make_article(
                        title=title,
                        url=f"https://xueqiu.com{item.get('target', '')}",
                        content=item.get("text", ""),
                        published_at=pub_time,
                        tags=self._extract_tags(title + " " + item.get("text", "")),
                    ))
        except Exception as e:
            print(f"[雪球] 热门失败: {e}")
        
        # 7x24 快讯（直播）
        try:
            resp = self.client.get(
                "https://xueqiu.com/statuses/livenews/list.json",
                params={"since_id": "-1", "max_id": "-1", "count": 20},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    text = item.get("text", "")
                    if len(text) < 10:
                        continue
                    pub_time = datetime.fromtimestamp(
                        item.get("created_at", 0) / 1000
                    ).isoformat()
                    articles.append(self.make_article(
                        title=text[:80],
                        url=f"https://xueqiu.com/livenews/{item.get('id', '')}",
                        content=text,
                        published_at=pub_time,
                        tags=self._extract_tags(text),
                    ))
        except Exception as e:
            print(f"[雪球] 快讯失败: {e}")
        
        return articles
