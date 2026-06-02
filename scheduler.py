"""
定时调度器（增强版）- 包含 AI 摘要
使用 asyncio 循环替代 APScheduler（避免 Render 休眠后不恢复）
"""
import asyncio
import logging
import time
from datetime import datetime

from config import CRAWL_INTERVAL_MINUTES
from models import init_db, save_article, log_crawl, get_db


logger = logging.getLogger("stocknews.scheduler")

# 导入所有爬虫
from crawlers.cls import CLSCrawler
from crawlers.wallstreetcn import WallstreetcnCrawler
from crawlers.eastmoney import EastmoneyCrawler
from crawlers.xueqiu import XueqiuCrawler
from crawlers.sina import SinaCrawler
from crawlers.jin10 import Jin10Crawler
from crawlers.news_36kr import News36krCrawler
from crawlers.cnbc import CNBCCrawler
from crawlers.zaobao import ZaobaoCrawler
from crawlers.yahoo import YahooCrawler
from crawlers.finnhub import FinnhubCrawler

# WebSocket 客户端列表（用于实时推送）
ws_clients = set()

# 主事件循环引用（用于后台线程跨线程推送）
_main_loop = None

# 上次爬取完成时间（用于判断数据是否过时）
_last_crawl_time: float = 0.0
_crawl_lock = asyncio.Lock()
_crawl_task: asyncio.Task | None = None
_crawling: bool = False  # 防止并发爬取


def set_main_loop(loop):
    """设置主事件循环引用（由 main.py 在启动时调用）"""
    global _main_loop
    _main_loop = loop


def last_crawl_age_seconds() -> float:
    """距离上次爬取完成过去了多少秒"""
    if _last_crawl_time == 0:
        return float("inf")
    return time.time() - _last_crawl_time


def is_data_stale() -> bool:
    """判断数据是否过时（超过爬取间隔的 2 倍）"""
    return last_crawl_age_seconds() > CRAWL_INTERVAL_MINUTES * 60 * 2


def is_crawling() -> bool:
    """是否正在爬取中"""
    return _crawling


def crawl_all_sources():
    """抓取所有数据源（带防并发锁）"""
    global _crawling
    if _crawling:
        logger.info("⏭️ 爬取已在运行中，跳过")
        print("⏭️ 爬取已在运行中，跳过")
        return
    _crawling = True
    try:
        _crawl_all_sources_impl()
    finally:
        _crawling = False


def _crawl_all_sources_impl():
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
        ("36氪", News36krCrawler()),
        ("CNBC", CNBCCrawler()),
        ("联合早报", ZaobaoCrawler()),
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

    # 更新最后爬取时间
    global _last_crawl_time
    _last_crawl_time = time.time()

    # AI 摘要和 Digest 均改为手动触发，不再自动运行

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


async def _crawl_loop(interval_seconds: int):
    """asyncio 爬取循环（比 APScheduler 更抗休眠）"""
    # 首次等待 10 秒让服务先启动
    await asyncio.sleep(10)
    logger.info(f"🔄 爬取循环启动（每 {interval_seconds}s）")

    while True:
        try:
            start = time.time()
            logger.info(f"⏰ 定时爬取触发 {datetime.now().strftime('%H:%M:%S')}")
            crawl_all_sources()
            elapsed = time.time() - start
            logger.info(f"✅ 定时爬取完成 (耗时 {elapsed:.0f}s)")
        except Exception as e:
            logger.error(f"❌ 定时爬取异常: {e}")

        # asyncio.sleep 在 Render 休眠恢复后会自动续跑
        await asyncio.sleep(interval_seconds)


async def _auto_crawl_if_stale():
    """页面请求时自动检测并补爬（数据过时时触发）"""
    if not is_data_stale():
        return

    global _crawl_lock
    if _crawl_lock.locked():
        logger.info("🔄 补爬已在运行中，跳过")
        return

    async with _crawl_lock:
        # 双重检查
        if not is_data_stale():
            return
        logger.info(f"⚠️ 数据过时（{last_crawl_age_seconds():.0f}s），自动补爬...")
        try:
            import threading
            thread = threading.Thread(target=crawl_all_sources, daemon=True)
            thread.start()
            thread.join(timeout=60)
        except Exception as e:
            logger.error(f"补爬失败: {e}")


def start_scheduler():
    """启动定时调度器（使用 asyncio 循环）"""
    init_db()

    # 后台执行首次爬取（不阻塞服务启动）
    import threading
    def initial_crawl():
        try:
            print("🚀 首次爬取（后台）...")
            crawl_all_sources()
        except Exception as e:
            print(f"⚠️ 首次爬取失败: {e}")
    threading.Thread(target=initial_crawl, daemon=True).start()

    # 启动 asyncio 循环
    global _crawl_task
    loop = _main_loop
    if loop:
        _crawl_task = loop.create_task(
            _crawl_loop(CRAWL_INTERVAL_MINUTES * 60)
        )
        print(f"⏰ 定时任务已启动（每 {CRAWL_INTERVAL_MINUTES} 分钟）")
    else:
        print("⚠️ 无事件循环，调度器未启动")


def stop_scheduler():
    """停止调度器"""
    global _crawl_task
    if _crawl_task:
        _crawl_task.cancel()
