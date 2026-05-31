"""
财联社 (cls.cn) - HTML 页面爬取
免费，无需 API Key
"""
import re
from typing import List
from datetime import datetime
from .base import BaseCrawler


class CLSCrawler(BaseCrawler):
    """财联社电报 - 从 HTML 页面抓取"""
    
    def __init__(self):
        super().__init__("cls", "财联社")
    
    def fetch(self) -> List[dict]:
        articles = []
        
        try:
            resp = self.client.get(
                "https://www.cls.cn/telegraph",
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[财联社] HTTP {resp.status_code}")
                return articles
            
            html = resp.text
            
            # 从 JavaScript 数据中提取电报内容
            # 模式: "content":"xxx","ctime":1234567890
            pattern = re.compile(
                r'"content":"(.*?)"[^}]*"ctime":(\d+)',
                re.DOTALL,
            )
            matches = pattern.findall(html)
            
            for content, ctime in matches:
                content = content.replace('\\"', '"').replace('\\n', '\n').replace('\\/', '/')
                content = re.sub(r'<[^>]+>', '', content)  # 去 HTML 标签
                content = content.strip()
                
                if len(content) < 10:
                    continue
                
                try:
                    pub_time = datetime.fromtimestamp(int(ctime)).isoformat()
                except (ValueError, TypeError):
                    pub_time = datetime.now().isoformat()
                
                title = content[:80].replace('\n', ' ')
                
                articles.append(self.make_article(
                    title=title,
                    url=f"https://www.cls.cn/telegraph",
                    content=content,
                    published_at=pub_time,
                    tags=self._extract_tags(content),
                ))
            
            if articles:
                print(f"[财联社] ✓ 抓取 {len(articles)} 条电报")
            else:
                # 尝试备选模式
                pattern2 = re.compile(
                    r'"title":"(.*?)"[^}]*"brief":"(.*?)"[^}]*"ctime":(\d+)',
                    re.DOTALL,
                )
                matches2 = pattern2.findall(html)
                for title, brief, ctime in matches2:
                    title = title.replace('\\"', '"').strip()
                    brief = brief.replace('\\"', '"').strip()
                    try:
                        pub_time = datetime.fromtimestamp(int(ctime)).isoformat()
                    except:
                        pub_time = datetime.now().isoformat()
                    
                    if len(title) >= 5:
                        articles.append(self.make_article(
                            title=title,
                            url="https://www.cls.cn/telegraph",
                            content=brief,
                            published_at=pub_time,
                            tags=self._extract_tags(title + " " + brief),
                        ))
                
                if articles:
                    print(f"[财联社] ✓ 备选模式抓取 {len(articles)} 条")
                    
        except Exception as e:
            print(f"[财联社] 失败: {e}")
        
        return articles
