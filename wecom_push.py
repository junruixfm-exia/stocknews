"""
企业微信群机器人推送模块
通过 Webhook 发送图片和 Markdown 消息到企业微信群
在个人微信中可直接查看（企业微信与微信互通）
"""
import base64
import hashlib
import os
import httpx

# Webhook URL 从环境变量读取
WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL", "")


def send_image(image_bytes: bytes, webhook_url: str = "") -> dict:
    url = webhook_url or WECOM_WEBHOOK_URL
    if not url:
        return {"errcode": -1, "errmsg": "未配置 WECOM_WEBHOOK_URL"}

    if len(image_bytes) > 2 * 1024 * 1024:
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(image_bytes))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        image_bytes = buf.getvalue()

    payload = {
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(image_bytes).decode(),
            "md5": hashlib.md5(image_bytes).hexdigest(),
        },
    }
    try:
        resp = httpx.post(url, json=payload, timeout=30)
        return resp.json()
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def send_markdown(content: str, webhook_url: str = "") -> dict:
    url = webhook_url or WECOM_WEBHOOK_URL
    if not url:
        return {"errcode": -1, "errmsg": "未配置 WECOM_WEBHOOK_URL"}
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    try:
        resp = httpx.post(url, json=payload, timeout=30)
        return resp.json()
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def push_digest(digest: dict = None, webhook_url: str = "") -> dict:
    url = webhook_url or WECOM_WEBHOOK_URL
    if not url:
        return {"errcode": -1, "errmsg": "未配置 WECOM_WEBHOOK_URL"}

    if digest is None:
        from ai_summary import summarizer
        cache = summarizer._digest_cache
        if not cache or not cache.get("result"):
            return {"errcode": -1, "errmsg": "暂无 digest 缓存，请先生成"}
        digest = cache["result"]

    topics = digest.get("topics", [])
    summary = digest.get("summary", "")
    generated_at = digest.get("generated_at", "")

    # 格式时间
    ts = ""
    if generated_at:
        ts = generated_at.replace("T", " ")[:19]

    # 构建精美的 Markdown 摘要
    md_lines = [
        "## 📊 财经热点 · 24h 要闻",
        f"> <font color=\"info\">{summary}</font>",
        "",
    ]
    if ts:
        md_lines.append(f"<font color=\"comment\">⏰ {ts}</font>")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("")

    # 热度榜
    for t in topics[:10]:
        rank = t.get("rank", 0)
        heat = t.get("heat", 0)
        count = t.get("article_count", 0)
        sentiment = t.get("sentiment", "mixed")

        # 排名图标
        rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")

        # 热度颜色
        if heat >= 80:
            heat_str = f'<font color="warning">🔥{heat}</font>'
        elif heat >= 60:
            heat_str = f'<font color="warning">{heat}</font>'
        else:
            heat_str = str(heat)

        # 情绪
        if sentiment == "positive":
            s_str = '<font color="info">📈</font>'
        elif sentiment == "negative":
            s_str = '<font color="warning">📉</font>'
        else:
            s_str = "📊"

        # 进度条（10格）
        bar_filled = min(heat // 10, 10)
        bar_empty = 10 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty

        md_lines.append(
            f"{rank_icon} **{t.get('topic', '')}** {s_str}"
        )
        md_lines.append(f"　{bar} <font color=\"comment\">{heat}分 · {count}篇报道</font>")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append('<font color="comment">📸 详情卡片见下方图片</font>')

    result_md = send_markdown("\n".join(md_lines), url)
    if result_md.get("errcode") != 0:
        return {"errcode": result_md.get("errcode"), "errmsg": f"Markdown 发送失败: {result_md.get('errmsg')}"}

    # 生成并发送图片
    try:
        from digest_image import render_digest_card
        img_bytes = render_digest_card(digest)
        result_img = send_image(img_bytes, url)
        if result_img.get("errcode") != 0:
            return {"errcode": result_img.get("errcode"), "errmsg": f"图片发送失败: {result_img.get('errmsg')}"}
    except Exception as e:
        return {"errcode": -1, "errmsg": f"图片生成失败: {e}"}

    return {"errcode": 0, "errmsg": "ok", "topics": len(topics)}
