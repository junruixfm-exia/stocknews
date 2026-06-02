"""
热点榜图片渲染模块
用 Pillow 将 DeepSeek digest JSON 渲染成精美卡片图片
适用于微信/企业微信分享（800px 宽）
"""
import io
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CST = timezone(timedelta(hours=8))

FONT_DIR = Path(__file__).parent / "static" / "fonts"
FONT_REGULAR = str(FONT_DIR / "NotoSansSC-Regular.otf")
FONT_BOLD = str(FONT_DIR / "NotoSansSC-Bold.otf")

# 如果没有 Bold 字体，用 Regular 代替
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = FONT_REGULAR

# 卡片设计常量
CARD_W = 800
PADDING = 24
HEADER_H = 120
SUMMARY_H = 100
TOPIC_H = 130
FOOTER_H = 50

# 颜色
BG_COLOR = "#F5F6FA"
HEADER_START = "#FF6B35"
HEADER_END = "#EE3B33"
SUMMARY_START = "#3B82F6"
SUMMARY_END = "#6366F1"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#1F2937"
TEXT_GRAY = "#6B7280"
TEXT_LIGHT = "#9CA3AF"
HEAT_HIGH = "#EF4444"
HEAT_MED = "#F97316"
HEAT_LOW = "#EAB308"
POSITIVE = "#10B981"
NEGATIVE = "#EF4444"
MIXED = "#6B7280"
RANK_GRADIENT = ["#FF6B35", "#F97316", "#EAB308"]


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size)


def _heat_color(heat: int) -> str:
    if heat >= 80:
        return HEAT_HIGH
    elif heat >= 60:
        return HEAT_MED
    elif heat >= 40:
        return HEAT_LOW
    return TEXT_LIGHT


def _sentiment_emoji(s: str) -> str:
    return {"positive": "📈", "negative": "📉", "mixed": "📊"}.get(s, "📊")


def _sentiment_color(s: str) -> str:
    return {"positive": POSITIVE, "negative": NEGATIVE, "mixed": MIXED}.get(s, MIXED)


def _rank_emoji(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")


def _draw_gradient_header(draw: ImageDraw.Draw, img: Image.Image, w: int) -> None:
    """绘制渐变头部"""
    for y in range(HEADER_H):
        ratio = y / HEADER_H
        r = int(0xFF - ratio * (0xFF - 0xEE))
        g = int(0x6B - ratio * (0x6B - 0x3B))
        b = int(0x35 - ratio * (0x35 - 0x33))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    font_title = _get_font(32, bold=True)
    font_sub = _get_font(16)
    draw.text((PADDING, 20), "🔥 AI 财经热点", fill="white", font=font_title)
    draw.text((PADDING, 62), "DeepSeek 智能分析 24h 新闻 · 按热度排名", fill=(255, 255, 255), font=font_sub)

    # 右侧时间（北京时间）
    now_str = datetime.now(CST).strftime("%m/%d %H:%M")
    bbox = draw.textbbox((0, 0), now_str, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text((w - PADDING - tw, 62), now_str, fill=(255, 255, 255), font=font_sub)


def _draw_summary(draw: ImageDraw.Draw, y: int, w: int, summary: str) -> int:
    """绘制总结栏"""
    box_y = y + 12
    box_h = SUMMARY_H

    # 纯色圆角背景（蓝色渐变用两个纯色模拟）
    draw.rounded_rectangle(
        [PADDING, box_y, w - PADDING, box_y + box_h],
        radius=12, fill="#4F7DF3"
    )
    font_label = _get_font(14)
    font_text = _get_font(18, bold=True)
    draw.text((PADDING + 20, box_y + 16), "📋 AI 今日要闻", fill=(255, 255, 255), font=font_label)

    # 多行文本换行
    max_text_w = w - PADDING * 2 - 40
    lines = _wrap_text(summary, font_text, max_text_w)
    for i, line in enumerate(lines[:2]):
        draw.text((PADDING + 20, box_y + 42 + i * 26), line, fill="white", font=font_text)

    return box_y + box_h + 16


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """简单文本换行"""
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_topic_card(draw: ImageDraw.Draw, y: int, w: int, topic: dict, rank: int) -> int:
    """绘制单个话题卡片，返回下一个 y"""
    card_x = PADDING
    card_w = w - PADDING * 2
    card_h = TOPIC_H

    # 卡片背景 + 阴影
    draw.rounded_rectangle(
        [card_x + 2, y + 2, card_x + card_w + 2, y + card_h + 2],
        radius=12, fill="#E5E7EB"
    )
    draw.rounded_rectangle(
        [card_x, y, card_x + card_w, y + card_h],
        radius=12, fill=CARD_BG
    )

    # 排名徽章
    badge_x = card_x + 16
    badge_y = y + 20
    badge_r = 28
    color = RANK_GRADIENT[min(rank - 1, 2)]
    draw.ellipse(
        [badge_x, badge_y, badge_x + badge_r * 2, badge_y + badge_r * 2],
        fill=color
    )
    emoji = _rank_emoji(rank)
    font_rank = _get_font(22 if rank <= 3 else 18, bold=True)
    bbox = draw.textbbox((0, 0), emoji, font=font_rank)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (badge_x + badge_r - tw // 2, badge_y + badge_r - th // 2 - 2),
        emoji, fill="white", font=font_rank
    )

    # 话题标题
    text_x = badge_x + badge_r * 2 + 14
    font_topic = _get_font(18, bold=True)
    topic_name = topic.get("topic", "")
    draw.text((text_x, y + 18), topic_name, fill=TEXT_DARK, font=font_topic)

    # 情绪标签
    sentiment = topic.get("sentiment", "mixed")
    font_s = _get_font(13)
    s_emoji = _sentiment_emoji(sentiment)
    s_color = _sentiment_color(sentiment)
    bbox_t = draw.textbbox((0, 0), topic_name, font=font_topic)
    sx = text_x + (bbox_t[2] - bbox_t[0]) + 10
    draw.text((sx, y + 21), s_emoji, fill=s_color, font=font_s)

    # 摘要
    summary = topic.get("summary", "")
    if summary:
        font_summary = _get_font(14)
        draw.text((text_x, y + 44), summary, fill=TEXT_GRAY, font=font_summary)

    # 要点
    key_point = topic.get("key_point", "")
    if key_point:
        font_kp = _get_font(13)
        kp_text = f"💡 {key_point}"
        draw.text((text_x, y + 66), kp_text, fill="#F97316", font=font_kp)

    # 底部信息
    font_info = _get_font(12)
    article_count = topic.get("article_count", 0)
    sources = topic.get("sources", [])
    sources_str = " · ".join(sources[:4])
    if len(sources) > 4:
        sources_str += f" +{len(sources) - 4}"

    info_y = y + card_h - 24
    draw.text((text_x, info_y), f"📰 {article_count}篇报道", fill=TEXT_LIGHT, font=font_info)
    if sources_str:
        bbox_i = draw.textbbox((0, 0), f"📰 {article_count}篇报道", font=font_info)
        draw.text((text_x + (bbox_i[2] - bbox_i[0]) + 16, info_y), f"🏷️ {sources_str}", fill=TEXT_LIGHT, font=font_info)

    # 热度条（右侧）
    heat = topic.get("heat", 0)
    heat_x = card_x + card_w - 80
    font_heat = _get_font(28, bold=True)
    heat_color = _heat_color(heat)
    h_text = str(heat)
    bbox_h = draw.textbbox((0, 0), h_text, font=font_heat)
    draw.text((heat_x + 40 - (bbox_h[2] - bbox_h[0]) // 2, y + 18), h_text, fill=heat_color, font=font_heat)
    font_hl = _get_font(11)
    draw.text((heat_x + 30, y + 52), "热度", fill=TEXT_LIGHT, font=font_hl)

    # 热度条
    bar_x = heat_x + 23
    bar_y = y + 68
    bar_w = 6
    bar_h = card_h - 90
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=3, fill="#F3F4F6")
    fill_h = int(bar_h * heat / 100)
    if fill_h > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y + bar_h - fill_h, bar_x + bar_w, bar_y + bar_h],
            radius=3, fill=heat_color
        )

    return y + card_h + 12


def _draw_footer(draw: ImageDraw.Draw, y: int, w: int) -> None:
    font = _get_font(12)
    text = "📰 股票资讯聚合平台 · DeepSeek AI 生成"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, y + 10), text, fill=TEXT_LIGHT, font=font)


def render_digest_card(digest: dict) -> bytes:
    """
    将 digest JSON 渲染成 PNG 图片

    参数:
        digest: generate_digest() 返回的结果 dict
        格式: {"summary": "...", "topics": [...], "generated_at": "..."}

    返回:
        PNG 图片 bytes
    """
    topics = digest.get("topics", [])
    summary = digest.get("summary", "")

    # 计算高度
    n = len(topics)
    H = HEADER_H + SUMMARY_H + 30 + n * (TOPIC_H + 12) + FOOTER_H + PADDING

    img = Image.new("RGB", (CARD_W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 头部
    _draw_gradient_header(draw, img, CARD_W)

    # 总结
    next_y = HEADER_H + 8
    if summary:
        next_y = _draw_summary(draw, next_y, CARD_W, summary)

    # 话题卡片
    for i, topic in enumerate(topics):
        next_y = _draw_topic_card(draw, next_y, CARD_W, topic, i + 1)

    # 底部
    _draw_footer(draw, next_y, CARD_W)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_digest_card_from_cache() -> bytes | None:
    """从 digest 缓存渲染图片（避免重复调用 API）"""
    from ai_summary import summarizer
    cache = summarizer._digest_cache
    if not cache or not cache.get("result"):
        return None
    return render_digest_card(cache["result"])
