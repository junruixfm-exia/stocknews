"""
Finnhub - API 抓取
免费额度: 60次/分钟
注册: https://finnhub.io/
"""
from typing import List
from datetime import datetime
from .base import BaseCrawler
from config import FINNHUB_API_KEY


class FinnhubCrawler(BaseCrawler):
    """Finnhub 市场新闻"""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self):
        super().__init__("finnhub", "Finnhub")
    
    @property
    def enabled(self):
        return bool(FINNHUB_API_KEY)
    
    def fetch(self) -> List[dict]:
        if not FINNHUB_API_KEY:
            return []
        
        articles = []
        categories = ["general", "forex", "crypto", "merger"]
        
        for category in categories:
            try:
                resp = self.client.get(
                    f"{self.BASE_URL}/news",
                    params={
                        "category": category,
                        "token": FINNHUB_API_KEY,
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                
                for item in resp.json()[:15]:
                    pub_time = datetime.fromtimestamp(
                        item.get("datetime", 0)
                    ).isoformat()
                    articles.append(self.make_article(
                        title=item.get("headline", ""),
                        url=item.get("url", ""),
                        summary=item.get("summary", ""),
                        published_at=pub_time,
                        tags=[category] + self._extract_tags(
                            item.get("headline", "") + " " + item.get("summary", "")
                        ),
                        related_stocks=item.get("related", "").split(","),
                    ))
            except Exception as e:
                print(f"[Finnhub] {category} 失败: {e}")
        
        return articles
