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


@app.post("/api/ai/summarize")
async def api_ai_summarize():
    """手动触发 AI 批量摘要"""
    from ai_summary import summarizer
    count = summarizer.batch_summarize(max_count=50)
    return {"status": "ok", "processed": count}


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
    """生成 AI 新闻纪要并返回"""
    from ai_summary import summarizer
    # 获取 24h 内所有文章
    data = get_articles(page=1, per_page=100, max_age_hours=24)
    articles = data["articles"]
    if not articles:
        return {"error": "暂无 24h 内文章", "topics": [], "summary": ""}
    result = summarizer.generate_digest(articles)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
