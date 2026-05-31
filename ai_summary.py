"""
DeepSeek AI 摘要模块
用于对抓取到的文章进行智能摘要和情感分析

费用: DeepSeek API ¥1/百万token，处理千篇文章约 ¥0.5-2
注册: https://platform.deepseek.com/
"""
import json
import hashlib
import sqlite3
from typing import Optional

import httpx

from config import DEEPSEEK_API_KEY, DATA_DIR


class AISummarizer:
    """AI 文章摘要器"""
    
    API_URL = "https://api.deepseek.com/chat/completions"
    MODEL = "deepseek-chat"
    
    def __init__(self):
        self.client = httpx.Client(timeout=60)
        self.cache_db = str(DATA_DIR / "ai_cache.db")
        self._init_cache()
    
    def _init_cache(self):
        """初始化缓存数据库"""
        conn = sqlite3.connect(self.cache_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                content_hash TEXT PRIMARY KEY,
                summary TEXT,
                sentiment TEXT,
                tags TEXT,
                stocks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def _make_hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()
    
    def _check_cache(self, text: str) -> Optional[dict]:
        """检查缓存"""
        h = self._make_hash(text)
        conn = sqlite3.connect(self.cache_db)
        row = conn.execute(
            "SELECT summary, sentiment, tags, stocks FROM ai_cache WHERE content_hash = ?",
            (h,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "summary": row[0],
                "sentiment": row[1],
                "tags": json.loads(row[2]) if row[2] else [],
                "related_stocks": json.loads(row[3]) if row[3] else [],
            }
        return None
    
    def _save_cache(self, text: str, result: dict):
        """保存缓存"""
        h = self._make_hash(text)
        conn = sqlite3.connect(self.cache_db)
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (content_hash, summary, sentiment, tags, stocks) VALUES (?, ?, ?, ?, ?)",
            (h, result.get("summary", ""), result.get("sentiment", "neutral"),
             json.dumps(result.get("tags", []), ensure_ascii=False),
             json.dumps(result.get("related_stocks", []), ensure_ascii=False))
        )
        conn.commit()
        conn.close()
    
    def summarize(self, title: str, content: str = "") -> dict:
        """
        AI 分析文章
        返回: {summary, sentiment, tags, related_stocks}
        """
        if not DEEPSEEK_API_KEY:
            return {"summary": "", "sentiment": "neutral", "tags": [], "related_stocks": []}
        
        # 合并标题和内容
        full_text = f"{title}\n\n{content}" if content else title
        if len(full_text) < 20:
            return {"summary": "", "sentiment": "neutral", "tags": [], "related_stocks": []}
        
        # 检查缓存
        cached = self._check_cache(full_text)
        if cached:
            return cached
        
        # 调用 DeepSeek
        prompt = f"""分析以下财经资讯，返回 JSON 格式（只返回 JSON，不要其他内容）：

{{
  "summary": "一句话中文摘要（30字以内）",
  "sentiment": "positive/negative/neutral",
  "tags": ["标签1", "标签2"],
  "related_stocks": ["股票代码"]
}}

资讯内容：
{full_text[:1000]}
"""
        
        try:
            resp = self.client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                    "response_format": {"type": "json_object"},
                },
            )
            
            if resp.status_code != 200:
                print(f"[AI] 错误 {resp.status_code}: {resp.text[:100]}")
                return {"summary": "", "sentiment": "neutral", "tags": [], "related_stocks": []}
            
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            
            # 保存缓存
            self._save_cache(full_text, result)
            
            return result
            
        except Exception as e:
            print(f"[AI] 异常: {e}")
            return {"summary": "", "sentiment": "neutral", "tags": [], "related_stocks": []}
    
    def batch_summarize(self, articles: list, max_count: int = 20) -> int:
        """
        批量 AI 分析文章（仅处理没有摘要的）
        返回处理数量
        """
        if not DEEPSEEK_API_KEY:
            return 0
        
        import sqlite3 as sq
        from models import DB_PATH
        
        conn = sq.connect(str(DB_PATH))
        conn.row_factory = sq.Row
        
        # 获取没有 AI 摘要的文章
        rows = conn.execute(
            "SELECT id, title, content FROM articles WHERE summary = '' OR summary IS NULL LIMIT ?",
            (max_count,)
        ).fetchall()
        
        processed = 0
        for row in rows:
            result = self.summarize(row["title"], row.get("content", ""))
            if result.get("summary") or result.get("sentiment") != "neutral":
                conn.execute(
                    "UPDATE articles SET summary = ?, sentiment = ?, tags = ?, related_stocks = ? WHERE id = ?",
                    (
                        result.get("summary", ""),
                        result.get("sentiment", "neutral"),
                        json.dumps(result.get("tags", []), ensure_ascii=False),
                        json.dumps(result.get("related_stocks", []), ensure_ascii=False),
                        row["id"],
                    )
                )
                processed += 1
        
        conn.commit()
        conn.close()
        
        if processed > 0:
            print(f"[AI] ✓ DeepSeek 处理了 {processed} 篇文章")
        
        return processed


    def generate_digest(self, articles: list) -> dict:
        """
        生成 24h 新闻纪要并按热度排名
        
        参数:
            articles: 文章列表，每篇需包含 title, source_name, published_at, sentiment
        
        返回:
            {
                "generated_at": "ISO时间",
                "total_topics": N,
                "summary": "今日要闻一句话总结",
                "topics": [
                    {
                        "rank": 1,
                        "topic": "话题名称",
                        "heat": 95,
                        "summary": "一句话摘要",
                        "article_count": 8,
                        "sources": ["财联社", "华尔街见闻", ...],
                        "sentiment": "positive/negative/mixed",
                        "key_point": "核心要点（一句话）"
                    },
                    ...
                ]
            }
        """
        if not DEEPSEEK_API_KEY or not articles:
            return {"error": "无 API Key 或无文章数据", "topics": [], "summary": ""}
        
        # 构建标题列表
        title_list = []
        for i, a in enumerate(articles[:100]):  # 最多 100 篇
            title_list.append(f"[{i+1}] [{a.get('source_name', '?')}] {a.get('title', '')}")
        
        titles_text = "\n".join(title_list)
        
        prompt = f"""你是一位资深财经主编。以下是过去24小时内抓取到的财经资讯标题列表（共{len(title_list)}条），来自多个不同来源。

请完成以下任务：
1. 将这些新闻按话题归类（相同/相似话题合并），识别出最重要的 5-10 个话题
2. 按「热度」排序——热度综合考虑：覆盖该话题的来源数量、报道数量、时效性、对市场的影响程度
3. 为每个话题打分（1-100）并写一句话摘要
4. 最后写一句「今日要闻」整体总结

返回严格的 JSON 格式（不要任何其他文字）：

{{
  "summary": "今日要闻一句话总结（50字以内）",
  "topics": [
    {{
      "rank": 1,
      "topic": "话题名称（简洁，如"美联储降息预期升温"）",
      "heat": 95,
      "summary": "一句话描述该话题核心内容（40字以内）",
      "article_count": 8,
      "sources": ["来源1", "来源2"],
      "sentiment": "positive/negative/mixed",
      "key_point": "最值得关注的一个要点（30字以内）"
    }}
  ]
}}

资讯列表：
{titles_text}
"""
        
        try:
            resp = self.client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"},
                },
            )
            
            if resp.status_code != 200:
                print(f"[Digest] API 错误 {resp.status_code}: {resp.text[:200]}")
                return {"error": f"API 错误 {resp.status_code}", "topics": [], "summary": ""}
            
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["generated_at"] = __import__("datetime").datetime.now().isoformat()
            result["total_topics"] = len(result.get("topics", []))
            
            return result
            
        except Exception as e:
            print(f"[Digest] 异常: {e}")
            return {"error": str(e), "topics": [], "summary": ""}


# 全局实例
summarizer = AISummarizer()
