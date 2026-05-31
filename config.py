# 股票资讯抓取网站 - 配置模块
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Render 持久化磁盘路径（通过环境变量 DATA_DIR 设置）
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 尝试加载 .env 文件
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

# === 数据库 ===
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/stocknews.db")

# === API 密钥 ===
YAHOO_API_KEY = os.getenv("YAHOO_FINANCE_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# === 服务器 ===
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# === 爬取间隔 ===
CRAWL_INTERVAL_MINUTES = int(os.getenv("CRAWL_INTERVAL_MINUTES", "5"))

# === 数据源定义 ===
SOURCES = {
    "cls": {
        "name": "财联社",
        "url": "https://www.cls.cn",
        "type": "rss",  # api / rss / scrape
        "enabled": True,
    },
    "wallstreetcn": {
        "name": "华尔街见闻",
        "url": "https://wallstreetcn.com",
        "type": "api",
        "enabled": True,
    },
    "eastmoney": {
        "name": "东方财富",
        "url": "https://www.eastmoney.com",
        "type": "rss",
        "enabled": True,
    },
    "xueqiu": {
        "name": "雪球",
        "url": "https://xueqiu.com",
        "type": "api",
        "enabled": False,  # Render US IP 被墙
    },
    "sina": {
        "name": "新浪财经",
        "url": "https://finance.sina.com.cn",
        "type": "rss",
        "enabled": True,
    },
    "jin10": {
        "name": "金十数据",
        "url": "https://www.jin10.com",
        "type": "scrape",
        "enabled": False,  # 反爬严格，暂时禁用
    },
    "36kr": {
        "name": "36氪",
        "url": "https://36kr.com/newsflashes",
        "type": "scrape",
        "enabled": True,
    },
    "cnbc": {
        "name": "CNBC",
        "url": "https://www.cnbc.com",
        "type": "rss",
        "enabled": True,
    },
    "marketwatch": {
        "name": "MarketWatch",
        "url": "https://www.marketwatch.com",
        "type": "rss",
        "enabled": True,
    },
    "wsj": {
        "name": "WSJ",
        "url": "https://www.wsj.com",
        "type": "rss",
        "enabled": True,
    },
    "yahoo": {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com",
        "type": "api",
        "enabled": bool(YAHOO_API_KEY),
    },
    "finnhub": {
        "name": "Finnhub",
        "url": "https://finnhub.io",
        "type": "api",
        "enabled": bool(FINNHUB_API_KEY),
    },
}
