"""
36氪 (36kr.com) - 快讯数据提取
从 HTML 页面中的 window.initialState JSON 提取 newsflash 数据
"""
import re
import json
from typing import List
from .base import BaseCrawler


class News36krCrawler(BaseCrawler):
    """36氪快讯"""

    def __init__(self):
        super().__init__("36kr", "36氪")

    def fetch(self) -> List[dict]:
        articles = []

        try:
            resp = self.client.get("https://36kr.com/newsflashes", timeout=15)
            if resp.status_code != 200:
                print(f"[36氪] HTTP {resp.status_code}")
                return articles

            html = resp.text

            # 提取 window.initialState JSON
            start = html.find("window.initialState={")
            if start == -1:
                print("[36氪] 未找到 initialState")
                return articles

            json_start = start + len("window.initialState=")
            brace_count = 0
            json_end = json_start
            for i in range(json_start, min(json_start + 500000, len(html))):
                if html[i] == "{":
                    brace_count += 1
                elif html[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            json_str = html[json_start:json_end]
            data = json.loads(json_str)

            items = (
                data.get("newsflashCatalogData", {})
                .get("data", {})
                .get("newsflashList", {})
                .get("data", {})
                .get("itemList", [])
            )

            for item in items:
                tm = item.get("templateMaterial", {})
                title = tm.get("widgetTitle", "")
                content = tm.get("widgetContent", "")

                if not title or len(title) < 5:
                    continue

                # publishTime 是毫秒时间戳 → 北京时间
                pub_ms = tm.get("publishTime", 0)
                if pub_ms:
                    pub_time = self.ts_to_cst(pub_ms)
                else:
                    pub_time = self.now_cst()

                item_id = item.get("itemId", "")
                url = f"https://36kr.com/newsflashes/{item_id}" if item_id else "https://36kr.com/newsflashes"

                # 提取源链接
                source_url = tm.get("sourceUrlRoute", "")
                if source_url and "url=" in source_url:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(source_url.split("?")[-1])
                    if "url" in parsed:
                        url = parsed["url"][0]

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
                print(f"[36氪] ✓ 抓取 {len(articles)} 条")
            else:
                print(f"[36氪] 无数据")

        except Exception as e:
            print(f"[36氪] 失败: {e}")

        return articles
