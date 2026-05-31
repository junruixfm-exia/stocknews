"""
Yahoo Finance - API 抓取
需要免费 API Key: https://www.yahoofinanceapi.com/
"""
from typing import List
from datetime import datetime
from .base import BaseCrawler
from config import YAHOO_API_KEY


class YahooCrawler(BaseCrawler):
    """Yahoo Finance 新闻"""
    
    BASE_URL = "https://yahoofinanceapi.com/v8/finance/news"
    
    def __init__(self):
        super().__init__("yahoo", "Yahoo Finance")
        if not YAHOO_API_KEY:
            self._enabled = False
        else:
            self._enabled = True
    
    @property
    def enabled(self):
        return bool(YAHOO_API_KEY) and self._enabled
    
    def fetch(self) -> List[dict]:
        if not YAHOO_API_KEY:
            return []
        
        articles = []
        try:
            resp = self.client.get(
                self.BASE_URL,
                headers={"X-API-KEY": YAHOO_API_KEY},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[Yahoo] API 错误: {resp.status_code}")
                return []
            
            data = resp.json()
            for item in data.get("news", [])[:20]:
                pub_time = datetime.fromtimestamp(
                    item.get("providerPublishTime", 0)
                ).isoformat()
                articles.append(self.make_article(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    summary=item.get("summary", ""),
                    published_at=pub_time,
                    tags=["美股"] + self._extract_tags(item.get("title", "")),
                    related_stocks=item.get("relatedTickers", []),
                ))
        except Exception as e:
            print(f"[Yahoo] 失败: {e}")
        
        return articles
