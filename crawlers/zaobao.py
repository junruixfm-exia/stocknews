"""
联合早报 (zaobao.com.sg) - 财经新闻 HTML 抓取
新加坡中文媒体，只抓取财经类内容
"""
import re
from typing import List
from datetime import datetime, timezone, timedelta
from .base import BaseCrawler, CST


# 财经关键词过滤
FINANCE_KEYWORDS = [
    "财经", "经济", "股市", "股票", "金融", "投资", "贸易", "关税",
    "企业", "公司", "央行", "利率", "汇率", "金价", "油价", "PMI",
    "GDP", "通胀", "市场", "财报", "业绩", "上市", "IPO", "科技",
    "银行", "基金", "理财", "产业", "制造", "出口", "进口", "税务",
    "预算", "赤字", "债务", "美元", "人民币", "新元", "房地产",
    "能源", "半导体", "芯片", "AI", "人工智能", "数据", "零售",
    "消费", "物流", "收购", "合并", "融资", "海关", "供应链",
    "数码", "监管", "创业", "营收", "利润", "股东", "分红",
    "保险", "养老金", "公积金", "贷款", "债务", "信用",
]


class ZaobaoCrawler(BaseCrawler):
    """联合早报 - 财经新闻（含实时页关键词过滤 + 财经频道）"""

    # 财经频道直接抓取，实时页需关键词过滤
    PAGES = [
        ("https://www.zaobao.com/realtime", "实时", True),   # 需要关键词过滤
        ("https://www.zaobao.com/finance", "财经", False),   # 财经频道，全收
    ]

    def __init__(self):
        super().__init__("zaobao", "联合早报")

    def _is_finance(self, title: str) -> bool:
        """判断标题是否与财经相关"""
        return any(kw in title for kw in FINANCE_KEYWORDS)

    def fetch(self) -> List[dict]:
        articles = []
        seen_urls = set()

        for page_url, category, need_filter in self.PAGES:
            try:
                resp = self.client.get(page_url, timeout=15)
                if resp.status_code != 200:
                    print(f"[联合早报] {category} HTTP {resp.status_code}")
                    continue

                html = resp.text

                story_pattern = re.compile(
                    r'<a[^>]*href="(/realtime/[^"]+/story\d+[^"]*|/news/[^"]+/story\d+[^"]*|/finance/[^"]+/story\d+[^"]*)"[^>]*>'
                    r"(.*?)"
                    r"</a>",
                    re.DOTALL,
                )

                # 同时匹配 title 属性中的标题（财经频道用）
                title_attr_pattern = re.compile(
                    r'<a[^>]*title="([^"]+)"[^>]*href="(/finance/[^"]+/story\d+[^"]*)"',
                    re.DOTALL,
                )
                attr_matches = title_attr_pattern.findall(html)
                attr_titles = {url: title for title, url in attr_matches}

                matches = story_pattern.findall(html)
                count = 0
                skipped = 0

                for href, inner_html in matches:
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title = re.sub(r"<[^>]+>", " ", inner_html)
                    title = re.sub(r"\s+", " ", title).strip()

                    # 财经频道：inner text 可能为空（标题在 title 属性中）
                    if len(title) < 8 and href in attr_titles:
                        title = attr_titles[href]

                    if len(title) < 8:
                        continue

                    # 实时页：非财经主题跳过
                    if need_filter and not self._is_finance(title):
                        skipped += 1
                        continue

                    # 提取时间
                    time_match = re.match(r"(\d{1,2}:\d{2})\s*", title)
                    pub_time = None
                    if time_match:
                        time_str = time_match.group(1)
                        title = title[len(time_str):].strip()
                        try:
                            hour, minute = map(int, time_str.split(":"))
                            # 北京时间（新加坡与北京同属 UTC+8）
                            now = datetime.now(CST)
                            pub_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            if pub_time > now:
                                pub_time = pub_time - timedelta(days=1)
                            if (now - pub_time) > timedelta(hours=24):
                                continue
                        except (ValueError, TypeError):
                            pub_time = None
                    if not pub_time:
                        date_match = re.search(r"story(\d{8})", href)
                        if date_match:
                            try:
                                date_str = date_match.group(1)
                                pub_time = datetime.strptime(date_str, "%Y%m%d")
                                pub_time = pub_time.replace(tzinfo=CST)
                                # 只保留 7 天内的文章
                                if (datetime.now(CST) - pub_time) > timedelta(days=7):
                                    continue
                            except ValueError:
                                pub_time = datetime.now(CST)
                        else:
                            pub_time = datetime.now(CST)

                    url = f"https://www.zaobao.com{href}"

                    articles.append(
                        self.make_article(
                            title=title,
                            url=url,
                            published_at=pub_time.isoformat()
                            if isinstance(pub_time, datetime)
                            else pub_time,
                            tags=["财经"] + self._extract_tags(title),
                        )
                    )
                    count += 1

                if need_filter:
                    print(f"[联合早报] ✓ {category}（过滤后）: {count} 篇（跳过 {skipped} 非财经）")
                else:
                    print(f"[联合早报] ✓ {category}: {count} 篇")

            except Exception as e:
                print(f"[联合早报] {category} 失败: {e}")

        # 清理旧数据，仅保留本次抓取的财经文章
        if articles:
            try:
                from models import get_db
                conn = get_db()
                conn.execute("DELETE FROM articles WHERE source = 'zaobao'")
                conn.commit()
                conn.close()
            except:
                pass

        return articles
