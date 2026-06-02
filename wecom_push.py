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

    # 只发送图片卡片（不发送 Markdown 文字）
    try:
        from digest_image import render_digest_card
        img_bytes = render_digest_card(digest)
        result_img = send_image(img_bytes, url)
        if result_img.get("errcode") != 0:
            return {"errcode": result_img.get("errcode"), "errmsg": f"图片发送失败: {result_img.get('errmsg')}"}
    except Exception as e:
        return {"errcode": -1, "errmsg": f"图片生成失败: {e}"}

    return {"errcode": 0, "errmsg": "ok", "topics": len(topics)}
