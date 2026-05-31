"""
金十数据 (jin10.com) - 快讯 API
免费，无需 API Key
"""
from typing import List
from datetime import datetime
from .base import BaseCrawler


class Jin10Crawler(BaseCrawler):
    """金十数据 - 快讯"""
    
    def __init__(self):
        super().__init__("jin10", "金十数据")
    
    def fetch(self) -> List[dict]:
        articles = []
        
        # 金十数据 Flash API - GET 方式
        try:
            resp = self.client.get(
                "https://flash-api.jin10.com/get_flash_list",
                params={
                    "channel": "-8200",
                    "vip": "1",
                },
                headers={
                    "Referer": "https://www.jin10.com/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.jin10.com",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                
                for item in items[:30]:
                    content = item.get("data", {}).get("content", "")
                    if not content:
                        continue
                    
                    # 时间可能是 "2026-05-24 14:47:50" 格式
                    raw_time = item.get("time", "")
                    try:
                        if isinstance(raw_time, str) and len(raw_time) > 10:
                            pub_time = datetime.strptime(
                                raw_time, "%Y-%m-%d %H:%M:%S"
                            ).isoformat()
                        elif isinstance(raw_time, (int, float)):
                            pub_time = datetime.fromtimestamp(int(raw_time)).isoformat()
                        else:
                            pub_time = datetime.now().isoformat()
                    except (ValueError, TypeError):
                        pub_time = datetime.now().isoformat()
                    
                    articles.append(self.make_article(
                        title=content[:80].replace('\n', ' '),
                        url=f"https://flash.jin10.com/detail/{item.get('id', '')}",
                        content=content,
                        published_at=pub_time,
                        tags=self._extract_tags(content),
                    ))
                
                if articles:
                    print(f"[金十数据] ✓ {len(articles)} 条")
                    
        except Exception as e:
            print(f"[金十数据] 失败: {e}")
        
        return articles
