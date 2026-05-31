"""
定时调度器（增强版）- 包含 AI 摘要
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from config import CRAWL_INTERVAL_MINUTES
from models import init_db, save_article, log_crawl, get_db
from ai_summary import summarizer

logger = logging.getLogger("stocknews.scheduler")

# 导入所有爬虫
from crawlers.cls import CLSCrawler
from crawlers.wallstreetcn import WallstreetcnCrawler
from crawlers.eastmoney import EastmoneyCrawler
from crawlers.xueqiu import XueqiuCrawler
from crawlers.sina import SinaCrawler
from crawlers.jin10 import Jin10Crawler
from crawlers.yahoo import YahooCrawler
from crawlers.finnhub import FinnhubCrawler

scheduler = BackgroundScheduler()

# WebSocket 客户端列表（用于实时推送）
ws_clients = set()

# 主事件循环引用（用于后台线程跨线程推送）
_main_loop = None


def set_main_loop(loop):
    """设置主事件循环引用（由 main.py 在启动时调用）"""
    global _main_loop
    _main_loop = loop


def crawl_all_sources():
    """抓取所有数据源"""
    logger.info(f"⏰ 开始爬取 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'='*50}")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')} 开始爬取")
    print(f"{'='*50}")
    
    crawlers = [
        ("财联社", CLSCrawler()),
        ("华尔街见闻", WallstreetcnCrawler()),
        ("东方财富", EastmoneyCrawler()),
        ("雪球", XueqiuCrawler()),
        ("新浪财经", SinaCrawler()),
        ("金十数据", Jin10Crawler()),
        ("Yahoo Finance", YahooCrawler()),
        ("Finnhub", FinnhubCrawler()),
    ]
    
    total_found = 0
    total_new = 0
    new_article_ids = []
    
    for name, crawler in crawlers:
        try:
            if hasattr(crawler, 'enabled') and not crawler.enabled:
                continue
            
            articles = crawler.fetch()
            found = len(articles)
            new_count = 0
            
            for article in articles:
                if save_article(article):
                    new_count += 1
            
            log_crawl(crawler.source, "success", found, new_count)
            
            if found > 0:
                print(f"  ✅ {name}: {found}篇 (新增{new_count})")
            else:
                print(f"  ⚠️ {name}: 无数据")
            
            total_found += found
            total_new += new_count
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            log_crawl(crawler.source, "error", 0, 0, str(e))
    
    print(f"  📊 本轮: {total_found}篇, 新增{total_new}篇")
    
    # AI 摘要（如果有 API Key）
    if total_new > 0:
        try:
            ai_count = summarizer.batch_summarize(max_count=20)
        except Exception as e:
            print(f"  🤖 AI: {e}")
    
    # WebSocket 推送新文章
    if total_new > 0 and ws_clients:
        _push_to_clients(total_new)


def _push_to_clients(count: int):
    """向 WebSocket 客户端推送通知（线程安全）"""
    import asyncio
    import json
    if not _main_loop or not ws_clients:
        return
    
    async def _send():
        dead = []
        for ws in list(ws_clients):
            try:
                await ws.send_text(json.dumps({
                    "type": "new_articles",
                    "count": count,
                    "time": datetime.now().isoformat(),
                }))
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_clients.discard(ws)
    
    asyncio.run_coroutine_threadsafe(_send(), _main_loop)


def start_scheduler():
    """启动定时调度器"""
    init_db()
    
    # 立即执行一次
    print("🚀 首次爬取...")
    crawl_all_sources()
    
    # 每隔 N 分钟执行
    scheduler.add_job(
        crawl_all_sources,
        'interval',
        minutes=CRAWL_INTERVAL_MINUTES,
        id='crawl_job',
        next_run_time=None,
    )
    
    scheduler.start()
    print(f"⏰ 定时任务已启动（每 {CRAWL_INTERVAL_MINUTES} 分钟）")


def stop_scheduler():
    """停止调度器"""
    scheduler.shutdown(wait=False)
