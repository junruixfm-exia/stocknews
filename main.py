"""
股票资讯抓取网站 - FastAPI 后端（完整版）
支持 WebSocket 实时推送 + AI 摘要 + 移动端适配
"""
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from config import HOST, PORT, SOURCES, CRAWL_INTERVAL_MINUTES, DEEPSEEK_API_KEY
from models import get_articles, get_article, get_stats, init_db
from scheduler import start_scheduler, stop_scheduler, crawl_all_sources, ws_clients, set_main_loop
from scheduler import is_data_stale, last_crawl_age_seconds, is_crawling

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("stocknews")

_jinja_env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")), autoescape=True, cache_size=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio, traceback
    try:
        set_main_loop(asyncio.get_running_loop())
        init_db()
        logger.info("✅ 数据库初始化完成")
        start_scheduler()
        logger.info("✅ 调度器启动完成")
        logger.info(f"📰 服务启动: http://{HOST}:{PORT}")
    except Exception as e:
        logger.error(f"⚠️ 启动失败: {e}\n{traceback.format_exc()}")
    yield
    try:
        stop_scheduler()
    except:
        pass
    logger.info("👋 关闭")


app = FastAPI(
    title="📰 股票资讯聚合",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ===== WebSocket 实时推送 =====

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"🔗 WebSocket 连接 (+1, 共 {len(ws_clients)} 个)")
    try:
        # 发送连接确认
        await websocket.send_json({
            "type": "connected",
            "message": "实时推送已连接",
            "total_articles": get_stats()["total_articles"],
        })
        # 保持连接，等待推送
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_clients.discard(websocket)
        logger.info(f"🔌 WebSocket 断开 (剩余 {len(ws_clients)} 个)")


# ===== 页面路由 =====

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    page: int = Query(1, ge=1),
    source: str = Query(None),
    sentiment: str = Query(None),
):
    try:
        # 检测数据是否过时，后台补爬（不阻塞页面返回）
        data_stale = is_data_stale()
        if data_stale:
            logger.info(f"⚠️ 数据过时 {last_crawl_age_seconds():.0f}s，后台触发补爬")
            import threading
            threading.Thread(target=crawl_all_sources, daemon=True).start()

        data = get_articles(page=page, per_page=50, source=source, sentiment=sentiment)
        stats = get_stats()
        
        # 获取 AI Digest（缓存30分钟，避免每次请求都调 API）
        # 缓存未命中时跳过，由调度器后台预生成
        digest = None
        if DEEPSEEK_API_KEY:
            try:
                from ai_summary import summarizer
                cache = summarizer._digest_cache
                if cache and (time.time() - cache["timestamp"]) < 1800:
                    digest = cache["result"]
                else:
                    # 后台触发生成，本次请求不等待
                    import threading
                    def _gen():
                        try:
                            articles = data["articles"][:80]
                            if articles:
                                summarizer.get_digest(articles, max_age_seconds=0)
                        except Exception:
                            pass
                    threading.Thread(target=_gen, daemon=True).start()
            except Exception:
                pass
        
        tmpl = _jinja_env.get_template("index.html")
        html = tmpl.render(
            request=request,
            **data,
            stats=stats,
            sources=SOURCES,
            current_source=source,
            current_sentiment=sentiment,
            interval=CRAWL_INTERVAL_MINUTES,
            has_ai=bool(DEEPSEEK_API_KEY),
            digest=digest,
            data_stale=data_stale,
            now=datetime.now(),
        )
        return HTMLResponse(html)
    except Exception as e:
        import traceback
        return HTMLResponse(f"<h1>Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int):
    article = get_article(article_id)
    if not article:
        return HTMLResponse(_jinja_env.get_template("404.html").render(request=request), status_code=404)
    return HTMLResponse(_jinja_env.get_template("detail.html").render(
        request=request,
        article=article,
        now=datetime.now(),
    ))


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(""),
    page: int = Query(1, ge=1),
):
    if not q.strip():
        data = {"articles": [], "total": 0, "page": 1, "per_page": 20, "total_pages": 0}
    else:
        data = get_articles(page=page, search=q.strip())
    return HTMLResponse(_jinja_env.get_template("search.html").render(
        request=request,
        **data,
        query=q,
        now=datetime.now(),
    ))


@app.get("/topic", response_class=HTMLResponse)
async def topic_page(
    request: Request,
    q: str = Query(""),
):
    """话题聚合页 - 从 AI 热度分析缓存中加载该话题的全部文章"""
    if not q.strip():
        return HTMLResponse(_jinja_env.get_template("topic.html").render(
            request=request, query="", articles=[], now=datetime.now(),
        ))
    return HTMLResponse(_jinja_env.get_template("topic.html").render(
        request=request, query=q, articles=[], now=datetime.now(),
    ))


@app.get("/api/topic/articles")
async def api_topic_articles(q: str = Query("")):
    """获取某话题关联的文章列表（来自 Digest 缓存）"""
    from ai_summary import summarizer
    
    cache = summarizer._digest_cache
    if not cache or not cache.get("result"):
        # 缓存为空，回退到关键词搜索
        data = get_articles(page=1, per_page=50, search=q, max_age_hours=24)
        return {"articles": data["articles"], "total": data["total"], "source": "search"}
    
    topics = cache["result"].get("topics", [])
    for topic in topics:
        if topic.get("topic") == q:
            return {
                "articles": topic.get("_articles", []),
                "total": len(topic.get("_articles", [])),
                "source": "digest",
                "topic_info": {
                    "rank": topic.get("rank"),
                    "heat": topic.get("heat"),
                    "summary": topic.get("summary"),
                }
            }
    
    # 未找到精确匹配，回退到关键词搜索
    data = get_articles(page=1, per_page=50, search=q, max_age_hours=24)
    return {"articles": data["articles"], "total": data["total"], "source": "search"}


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    stats = get_stats()
    return HTMLResponse(_jinja_env.get_template("stats.html").render(
        request=request,
        stats=stats,
        sources=SOURCES,
        has_ai=bool(DEEPSEEK_API_KEY),
        now=datetime.now(),
    ))


# ===== API 路由 =====

@app.get("/api/articles")
async def api_articles(
    page: int = Query(1, ge=1),
    source: str = Query(None),
    sentiment: str = Query(None),
    search: str = Query(None),
):
    return get_articles(page=page, source=source, sentiment=sentiment, search=search)


@app.get("/api/article/{article_id}")
async def api_article(article_id: int):
    article = get_article(article_id)
    if not article:
        return {"error": "Not found"}
    return article


@app.get("/api/stats")
async def api_stats():
    return get_stats()


@app.post("/api/crawl")
async def api_crawl():
    """触发后台爬取，立即返回。通过 WebSocket 推送结果。"""
    import threading
    thread = threading.Thread(target=crawl_all_sources, daemon=True)
    thread.start()
    return {"status": "ok", "message": "爬取已在后台启动"}


@app.get("/api/crawl/status")
async def api_crawl_status():
    """查询爬取状态"""
    return {
        "last_crawl_age_seconds": last_crawl_age_seconds(),
        "is_data_stale": is_data_stale(),
        "is_crawling": is_crawling(),
        "crawl_interval_minutes": CRAWL_INTERVAL_MINUTES,
    }


# AI 摘要后台处理状态
_ai_summary_running = False
_ai_summary_progress = {"processed": 0, "total": 0, "done": False}


@app.post("/api/ai/summarize")
async def api_ai_summarize():
    """手动触发 AI 批量摘要（后台处理，立即返回）"""
    global _ai_summary_running, _ai_summary_progress
    
    import traceback
    import threading
    try:
        import sqlite3
        from models import DB_PATH
        
        # 检查 API Key
        if not DEEPSEEK_API_KEY:
            return {"status": "error", "message": "未配置 DEEPSEEK_API_KEY"}
        
        if _ai_summary_running:
            return {"status": "running", "progress": _ai_summary_progress}
        
        # 查询待处理数量
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        pending = conn.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE summary = '' OR summary IS NULL"
        ).fetchone()["cnt"]
        conn.close()
        
        if pending == 0:
            return {"status": "ok", "processed": 0, "message": "没有需要处理的文章"}
        
        # 后台处理
        _ai_summary_running = True
        _ai_summary_progress = {"processed": 0, "total": pending, "done": False}
        
        def _run():
            global _ai_summary_running, _ai_summary_progress
            try:
                from ai_summary import summarizer
                # 1. 文章摘要
                count = summarizer.batch_summarize(max_count=50)
                _ai_summary_progress = {"processed": count, "total": pending, "done": False}
                # 2. 生成热度分析 digest
                try:
                    from models import get_articles
                    articles = get_articles(page=1, per_page=80, max_age_hours=24)["articles"]
                    if articles:
                        summarizer.get_digest(articles, max_age_seconds=0)  # 强制刷新
                except Exception:
                    pass
                _ai_summary_progress = {"processed": count, "total": pending, "done": True}
            except Exception as e:
                _ai_summary_progress = {"processed": 0, "total": pending, "done": True, "error": str(e)}
            finally:
                _ai_summary_running = False
        
        threading.Thread(target=_run, daemon=True).start()
        return {
            "status": "started",
            "message": f"后台处理中 ({pending} 篇待摘要)",
            "pending": pending,
        }
    except Exception as e:
        _ai_summary_running = False
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()[-300:]}


@app.get("/api/ai/summarize/status")
async def api_ai_summarize_status():
    """查询 AI 摘要处理进度"""
    global _ai_summary_running, _ai_summary_progress
    return {
        "running": _ai_summary_running,
        "progress": _ai_summary_progress,
    }


@app.get("/api/ai/pending")
async def api_ai_pending():
    """查询待 AI 摘要的文章数量"""
    import sqlite3
    from models import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    pending = conn.execute(
        "SELECT COUNT(*) as cnt FROM articles WHERE summary = '' OR summary IS NULL"
    ).fetchone()["cnt"]
    total = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()["cnt"]
    summarized = conn.execute(
        "SELECT COUNT(*) as cnt FROM articles WHERE summary != '' AND summary IS NOT NULL"
    ).fetchone()["cnt"]
    conn.close()
    return {
        "pending": pending,
        "summarized": summarized,
        "total": total,
    }


@app.get("/digest", response_class=HTMLResponse)
async def digest_page(request: Request):
    """AI 新闻纪要 + 热度排名页面"""
    return HTMLResponse(_jinja_env.get_template("digest.html").render(
        request=request,
        has_ai=bool(DEEPSEEK_API_KEY),
        now=datetime.now(),
    ))


@app.get("/api/digest")
async def api_digest():
    """生成 AI 新闻纪要并返回（自动推送已内置于 generate_digest）"""
    import traceback
    try:
        from ai_summary import summarizer
        
        if not DEEPSEEK_API_KEY:
            return {"error": "未配置 DEEPSEEK_API_KEY", "topics": [], "summary": ""}
        
        # 获取 24h 内所有文章
        data = get_articles(page=1, per_page=300, max_age_hours=24)
        articles = data["articles"]
        if not articles:
            return {"error": "暂无 24h 内文章", "topics": [], "summary": ""}
        result = summarizer.generate_digest(articles)
        # 移除 _articles 内部字段（仅用于话题页面后端查询）
        for t in result.get("topics", []):
            t.pop("_articles", None)
        return result
    except Exception as e:
        return {"error": f"{e}\n{traceback.format_exc()[-300:]}", "topics": [], "summary": ""}


@app.get("/api/digest/image")
async def api_digest_image():
    """将 AI 热点榜渲染为 PNG 图片返回（使用缓存，不重复调 API）"""
    from fastapi.responses import Response
    import traceback
    try:
        if not DEEPSEEK_API_KEY:
            return {"error": "未配置 DEEPSEEK_API_KEY"}

        from digest_image import render_digest_card_from_cache
        img_bytes = render_digest_card_from_cache()
        if img_bytes is None:
            return {"error": "暂无 digest 缓存，请先点击「生成纪要」"}

        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"{e}\n{traceback.format_exc()[-300:]}"}


@app.post("/api/digest/push")
async def api_digest_push():
    """推送热点榜到企业微信（先 Markdown 摘要 + 后图片卡片）"""
    import traceback
    try:
        from wecom_push import push_digest
        result = push_digest()
        return result
    except Exception as e:
        return {"errcode": -1, "errmsg": f"{e}\n{traceback.format_exc()[-300:]}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
