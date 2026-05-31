"""
股票资讯抓取网站 - FastAPI 后端（完整版）
支持 WebSocket 实时推送 + AI 摘要 + 移动端适配
"""
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import HOST, PORT, SOURCES, CRAWL_INTERVAL_MINUTES, DEEPSEEK_API_KEY
from models import get_articles, get_article, get_stats, init_db
from scheduler import start_scheduler, stop_scheduler, crawl_all_sources, ws_clients, set_main_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("stocknews")

templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    set_main_loop(asyncio.get_running_loop())
    init_db()
    start_scheduler()
    logger.info(f"📰 服务启动: http://{HOST}:{PORT}")
    logger.info(f"📡 数据源: {' '.join(s['name'] for s in SOURCES.values() if s['enabled'])}")
    logger.info(f"🤖 AI摘要: {'已启用 (DeepSeek)' if DEEPSEEK_API_KEY else '未启用（设置 DEEPSEEK_API_KEY）'}")
    yield
    stop_scheduler()
    logger.info("👋 关闭")


app = FastAPI(
    title="📰 股票资讯聚合",
    version="2.0.0",
    lifespan=lifespan,
)


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
    data = get_articles(page=page, source=source, sentiment=sentiment)
    stats = get_stats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        **data,
        "stats": stats,
        "sources": SOURCES,
        "current_source": source,
        "current_sentiment": sentiment,
        "interval": CRAWL_INTERVAL_MINUTES,
        "has_ai": bool(DEEPSEEK_API_KEY),
        "now": datetime.now(),
    })


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(request: Request, article_id: int):
    article = get_article(article_id)
    if not article:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "article": article,
        "now": datetime.now(),
    })


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
    return templates.TemplateResponse("search.html", {
        "request": request,
        **data,
        "query": q,
        "now": datetime.now(),
    })


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    stats = get_stats()
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "sources": SOURCES,
        "has_ai": bool(DEEPSEEK_API_KEY),
        "now": datetime.now(),
    })


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
