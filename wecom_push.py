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
    """
    发送图片到企业微信群机器人

    参数:
        image_bytes: PNG/JPEG 图片二进制数据（最大 2MB）
        webhook_url: Webhook URL（默认从环境变量读取）

    返回:
        {"errcode": 0, "errmsg": "ok"}
    """
    url = webhook_url or WECOM_WEBHOOK_URL
    if not url:
        return {"errcode": -1, "errmsg": "未配置 WECOM_WEBHOOK_URL"}

    # 确保不超过 2MB
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
    """
    发送 Markdown 消息到企业微信群机器人

    参数:
        content: Markdown 格式文本
        webhook_url: Webhook URL（默认从环境变量读取）

    返回:
        {"errcode": 0, "errmsg": "ok"}
    """
    url = webhook_url or WECOM_WEBHOOK_URL
    if not url:
        return {"errcode": -1, "errmsg": "未配置 WECOM_WEBHOOK_URL"}

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }

    try:
        resp = httpx.post(url, json=payload, timeout=30)
        return resp.json()
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def push_digest(digest: dict = None, webhook_url: str = "") -> dict:
    """
    一键推送热点榜：先发文字摘要，再发图片

    参数:
        digest: digest JSON（可选，不传则从缓存读取）
        webhook_url: Webhook URL

    返回:
        推送结果
    """
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

    # 1. 发送 Markdown 文字摘要
    md_lines = [
        "## 🔥 AI 财经热点 · 24h 要闻",
        "",
        f"> {summary}",
        "",
        "**📊 热度排行榜：**",
        "",
    ]
    for t in topics[:10]:
        emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(t.get("rank", 0), f"#{t.get('rank', '')}")
        s_emoji = {"positive": "📈", "negative": "📉"}.get(t.get("sentiment", ""), "📊")
        md_lines.append(
            f"{emoji} **{t.get('topic', '')}** {s_emoji} "
            f"热度:{t.get('heat', 0)} | {t.get('article_count', 0)}篇"
        )

    if generated_at:
        # 截取时间部分
        ts = generated_at.replace("T", " ")[:19]
        md_lines.append("")
        md_lines.append(f"⏰ 生成时间: {ts}")

    md_lines.append("")
    md_lines.append("📸 详情卡片见下方图片 ↓")

    result_md = send_markdown("\n".join(md_lines), url)
    if result_md.get("errcode") != 0:
        return {"errcode": result_md.get("errcode"), "errmsg": f"Markdown 发送失败: {result_md.get('errmsg')}"}

    # 2. 生成并发送图片
    try:
        from digest_image import render_digest_card
        img_bytes = render_digest_card(digest)
        result_img = send_image(img_bytes, url)
        if result_img.get("errcode") != 0:
            return {"errcode": result_img.get("errcode"), "errmsg": f"图片发送失败: {result_img.get('errmsg')}"}
    except Exception as e:
        return {"errcode": -1, "errmsg": f"图片生成失败: {e}"}

    return {"errcode": 0, "errmsg": "ok", "topics": len(topics)}
