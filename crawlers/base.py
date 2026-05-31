# 爬虫基类 & 工具函数
import re
import hashlib
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List

import httpx
from bs4 import BeautifulSoup


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, source: str, source_name: str):
        self.source = source
        self.source_name = source_name
        self.client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )
    
    @abstractmethod
    def fetch(self) -> List[dict]:
        """抓取文章列表，返回标准化 dict 列表"""
        ...
    
    def make_article(self, title: str, url: str, summary="", content="",
                     tags=None, related_stocks=None, published_at=None) -> dict:
        """构建标准化的文章 dict"""
        return {
            "title": self._clean_title(title),
            "url": url,
            "source": self.source,
            "source_name": self.source_name,
            "summary": self._clean_text(summary or content)[:300],
            "content": self._clean_text(content),
            "tags": self._extract_tags(title + " " + (summary or "")),
            "related_stocks": related_stocks or [],
            "sentiment": "neutral",
            "published_at": published_at,
        }
    
    def _clean_title(self, title: str) -> str:
        """清理标题"""
        return re.sub(r'\s+', ' ', title).strip()
    
    def _clean_text(self, text: str) -> str:
        """清理正文 HTML 标签"""
        if not text:
            return ""
        soup = BeautifulSoup(text, "lxml")
        text = soup.get_text(separator="\n")
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
    
    def _extract_tags(self, text: str) -> list:
        """从文本中提取关键标签"""
        keyword_map = {
            "涨停": "涨停", "跌停": "跌停", "利好": "利好", "利空": "利空",
            "财报": "财报", "业绩": "业绩", "分红": "分红", "回购": "回购",
            "新能源": "新能源", "AI": "AI", "人工智能": "AI",
            "芯片": "芯片", "半导体": "半导体", "医药": "医药",
            "消费": "消费", "地产": "地产", "银行": "银行",
            "证券": "证券", "保险": "保险", "汽车": "汽车",
            "光伏": "光伏", "锂电": "锂电", "储能": "储能",
            "美股": "美股", "港股": "港股", "A股": "A股",
            "降息": "降息", "加息": "加息", "通胀": "通胀",
            "央行": "央行", "政策": "政策", "监管": "监管",
            "IPO": "IPO", "并购": "并购", "重组": "重组",
        }
        tags = []
        for keyword, tag in keyword_map.items():
            if keyword in text:
                tags.append(tag)
        return list(set(tags))
    
    def _extract_stocks(self, text: str) -> list:
        """提取文中提到的股票代码"""
        # 匹配 600xxx, 000xxx, 300xxx 等 A 股代码
        a_stock = re.findall(r'[63]0[0123]\d{3}', text)
        return list(set(a_stock))
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
