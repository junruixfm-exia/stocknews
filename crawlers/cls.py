"""
财联社 (cls.cn) - 移动端 Next.js 页面数据提取
CLS 反爬升级后需要签名，改用移动站 m.cls.cn 的内嵌 JSON
"""
import re
import json
from typing import List
from .base import BaseCrawler


class CLSCrawler(BaseCrawler):
    """财联社 - 从移动端页面提取 __NEXT_DATA__"""

    def __init__(self):
        super().__init__("cls", "财联社")
        # 使用移动端 User-Agent
        self.client.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        })

    def fetch(self) -> List[dict]:
        articles = []

        try:
            resp = self.client.get("https://m.cls.cn/telegraph", timeout=15)
            if resp.status_code != 200:
                print(f"[财联社] HTTP {resp.status_code}")
                return articles

            html = resp.text

            # 提取 __NEXT_DATA__ JSON
            start = html.find("__NEXT_DATA__ = ")
            if start == -1:
                print("[财联社] 未找到 __NEXT_DATA__")
                return articles

            json_start = html.find("{", start)
            brace_count = 0
            json_end = json_start
            for i in range(json_start, len(html)):
                if html[i] == "{":
                    brace_count += 1
                elif html[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            json_str = html[json_start:json_end]
            data = json.loads(json_str)

            roll_data = (
                data.get("props", {})
                .get("initialState", {})
                .get("roll_data", [])
            )

            for item in roll_data:
                title = item.get("title", "") or item.get("brief", "")
                content = item.get("content", "") or item.get("brief", "")
                if not title or len(title) < 5:
                    continue

                # 时间戳（秒）→ 北京时间
                ctime = item.get("ctime", item.get("modified_time", 0))
                if ctime:
                    pub_time = self.ts_to_cst(ctime)
                else:
                    pub_time = self.now_cst()

                article_id = item.get("id", "")
                url = f"https://www.cls.cn/detail/{article_id}" if article_id else "https://www.cls.cn/telegraph"

                articles.append(
                    self.make_article(
                        title=title,
                        url=url,
                        content=content,
                        published_at=pub_time,
                        tags=self._extract_tags(title + " " + content),
                    )
                )

            if articles:
                print(f"[财联社] ✓ 抓取 {len(articles)} 条")
            else:
                print(f"[财联社] 无数据")

        except Exception as e:
            print(f"[财联社] 失败: {e}")

        return articles
