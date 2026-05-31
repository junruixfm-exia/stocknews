# 数据库模型
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, DATA_DIR

DB_PATH = DATA_DIR / "stocknews.db"


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            source_name TEXT NOT NULL,
            summary TEXT DEFAULT '',
            content TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            related_stocks TEXT DEFAULT '[]',
            sentiment TEXT DEFAULT 'neutral',
            published_at TIMESTAMP,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT UNIQUE NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles(fetched_at DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment);

        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            articles_found INTEGER DEFAULT 0,
            articles_new INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def make_hash(title: str, url: str) -> str:
    """生成文章唯一哈希"""
    return hashlib.md5(f"{title}|{url}".encode()).hexdigest()


def save_article(article: dict) -> bool:
    """保存文章，返回 True 表示新增，False 表示已存在"""
    conn = get_db()
    content_hash = make_hash(article["title"], article["url"])
    
    try:
        conn.execute("""
            INSERT INTO articles (title, url, source, source_name, summary, content,
                                  tags, related_stocks, sentiment, published_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article["title"],
            article["url"],
            article["source"],
            article["source_name"],
            article.get("summary", ""),
            article.get("content", ""),
            json.dumps(article.get("tags", []), ensure_ascii=False),
            json.dumps(article.get("related_stocks", []), ensure_ascii=False),
            article.get("sentiment", "neutral"),
            article.get("published_at"),
            content_hash,
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 已存在（content_hash 冲突）
        return False
    finally:
        conn.close()


def get_articles(page=1, per_page=20, source=None, sentiment=None, search=None):
    """分页获取文章列表"""
    try:
        conn = get_db()
    except Exception:
        return {"articles": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}
    conditions = []
    params = []
    
    if source:
        conditions.append("source = ?")
        params.append(source)
    if sentiment:
        conditions.append("sentiment = ?")
        params.append(sentiment)
    if search:
        conditions.append("(title LIKE ? OR content LIKE ? OR summary LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 总数
    total = conn.execute(f"SELECT COUNT(*) FROM articles {where}", params).fetchone()[0]
    
    # 分页
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM articles {where} ORDER BY fetched_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    
    conn.close()
    
    articles = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        d["related_stocks"] = json.loads(d["related_stocks"])
        articles.append(d)
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


def get_article(article_id: int):
    """获取单篇文章"""
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        d["related_stocks"] = json.loads(d["related_stocks"])
        return d
    return None


def get_stats():
    """获取统计信息"""
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE date(fetched_at) = date('now')"
        ).fetchone()[0]
        sources = conn.execute(
            "SELECT source_name, COUNT(*) as cnt FROM articles GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        sentiment = conn.execute(
            "SELECT sentiment, COUNT(*) as cnt FROM articles GROUP BY sentiment"
        ).fetchall()
        conn.close()
        return {
            "total_articles": total,
            "today_articles": today,
            "sources": [dict(r) for r in sources],
            "sentiment": [dict(r) for r in sentiment],
        }
    except Exception:
        return {"total_articles": 0, "today_articles": 0, "sources": [], "sentiment": []}


def log_crawl(source: str, status: str, found: int, new: int, error=""):
    """记录爬取日志"""
    conn = get_db()
    conn.execute(
        "INSERT INTO crawl_log (source, status, articles_found, articles_new, error_message) VALUES (?, ?, ?, ?, ?)",
        (source, status, found, new, error)
    )
    conn.commit()
    conn.close()
