#!/usr/bin/env python3
"""
🏗️ 股票资讯抓取网站 - 启动入口
"""
import sys
import os
import argparse

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="📰 股票资讯聚合平台 v2.0")
    parser.add_argument("--crawl", action="store_true", help="仅手动爬取一次")
    parser.add_argument("--reset", action="store_true", help="重置数据库")
    parser.add_argument("--ai", action="store_true", help="手动触发 AI 批量摘要")
    parser.add_argument("--port", type=int, default=8000, help="端口 (默认: 8000)")
    args = parser.parse_args()

    if args.reset:
        for f in ["stocknews.db", "ai_cache.db"]:
            if os.path.exists(f):
                os.remove(f)
                print(f"🗑️  已删除: {f}")

    if args.crawl:
        from models import init_db
        from scheduler import crawl_all_sources
        init_db()
        crawl_all_sources()
        print("✅ 爬取完成!")
        sys.exit(0)

    if args.ai:
        from models import init_db
        from ai_summary import summarizer
        init_db()
        count = summarizer.batch_summarize(max_count=50)
        print(f"✅ AI 处理了 {count} 篇文章")
        sys.exit(0)

    import uvicorn
    print(f"""
    ╔══════════════════════════════════════════╗
    ║     📰 股票资讯聚合平台 v2.0            ║
    ║                                         ║
    ║  📡 数据源: 财联社 华尔街见闻 东方财富  ║
    ║             雪球 新浪 金十 Yahoo Finnhub ║
    ║  🤖 AI摘要: {'DeepSeek' if __import__('config').DEEPSEEK_API_KEY else '未启用'}                       ║
    ║  🔗 实时推送: WebSocket                 ║
    ║                                         ║
    ║  🌐 http://localhost:{args.port:<5}               ║
    ║  📡 ws://localhost:{args.port:<5}/ws            ║
    ╚══════════════════════════════════════════╝
    """)
    
    uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=False, log_level="warning")
