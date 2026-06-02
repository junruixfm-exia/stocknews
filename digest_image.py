"""
热点榜图片渲染模块 v2
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

CARD_W = 800
PADDING = 20
HEADER_H = 110
SUMMARY_H = 90
RADIUS = 16
MIN_TOPIC_H = 140
LINE_H = 22
FOOTER_H = 40

BG = "#F0F2F5"
CARD_BG = "#FFFFFF"
ACCENT = "#E94560"
TEXT_DARK = "#1F2937"
TEXT_BODY = "#4B5563"
TEXT_MUTED = "#9CA3AF"
HEAT_RED = "#EF4444"
HEAT_ORANGE = "#F97316"
HEAT_YELLOW = "#EAB308"
POSITIVE = "#059669"
NEGATIVE = "#DC2626"
MIXED = "#6B7280"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_REGULAR, size)


def _heat_color(heat: int) -> str:
    if heat >= 80: return HEAT_RED
    if heat >= 60: return HEAT_ORANGE
    if heat >= 40: return HEAT_YELLOW
    return TEXT_MUTED


def _sentiment_icon(s: str) -> str:
    return {"positive": "📈", "negative": "📉"}.get(s, "📊")


def _sentiment_color(s: str) -> str:
    return {"positive": POSITIVE, "negative": NEGATIVE}.get(s, MIXED)


def _rank_badge(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list:
    lines, cur = [], ""
    for ch in text:
        if font.getbbox(cur + ch)[2] > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines or [" "]


def _calc_topic_h(topic: dict) -> int:
    """预计算话题卡片高度"""
    max_w = CARD_W - PADDING * 2 - (14 + 26*2 + 12) - 80
    title_lines = _wrap(topic.get("topic", ""), _font(17), max_w)
    tag_base = 19 + len(title_lines) * LINE_H
    sum_lines = _wrap(topic.get("summary", ""), _font(14), max_w)
    sum_h = len(sum_lines) * 20
    kp_h = 20 if topic.get("key_point") else 0
    content_h = tag_base + 28 + sum_h + kp_h + 18 + 24
    return max(MIN_TOPIC_H, content_h)


def _draw_header(draw: ImageDraw.Draw, w: int, timestamp: str = ""):
    for y in range(HEADER_H):
        r = y / HEADER_H
        draw.line([(0, y), (w, y)],
                  fill=(int(26*(1-r)+22*r), int(26*(1-r)+33*r), int(46*(1-r)+62*r)))
    draw.ellipse([-40, -30, 80, 90], fill=(233, 69, 96, 40))
    f1 = _font(34)
    draw.text((PADDING + 4, 18), "🔥 财经热点", fill="white", font=f1)
    f2 = _font(14)
    draw.text((PADDING + 4, 62), "DeepSeek · 24h 要闻智能分析", fill=(180, 190, 210), font=f2)
    if not timestamp:
        timestamp = datetime.now(CST).strftime("%m/%d %H:%M")
    f3 = _font(13)
    tw = f3.getbbox(timestamp)[2]
    draw.text((w - PADDING - tw - 4, 64), timestamp, fill=(140, 150, 170), font=f3)


def _draw_summary(draw: ImageDraw.Draw, y: int, w: int, summary: str) -> int:
    box_x, box_w = PADDING, w - PADDING * 2
    box_h = SUMMARY_H
    box_y = y + 10
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h],
                           radius=10, fill="#F8FAFC")
    draw.rounded_rectangle([box_x, box_y + 8, box_x + 4, box_y + box_h - 8],
                           radius=2, fill=ACCENT)
    f_label = _font(12)
    draw.text((box_x + 16, box_y + 12), "📋 今日要闻", fill=TEXT_MUTED, font=f_label)
    f_text = _font(17)
    lines = _wrap(summary, f_text, box_w - 40)
    for i, line in enumerate(lines[:2]):
        draw.text((box_x + 16, box_y + 34 + i * 24), line, fill=TEXT_DARK, font=f_text)
    return box_y + box_h + 10


def _draw_topic_card(draw: ImageDraw.Draw, y: int, w: int, topic: dict, rank: int, card_h: int) -> int:
    """绘制话题卡片"""
    cx, cw = PADDING, w - PADDING * 2
    badge_r = 26
    tx = cx + 14 + badge_r * 2 + 12
    max_text_w = cw - (14 + badge_r * 2 + 12) - 80
    ch = card_h

    f_topic = _font(17)
    title_lines = _wrap(topic.get("topic", ""), f_topic, max_text_w)
    title_h = len(title_lines)
    tag_base_y = 19 + title_h * LINE_H

    f_sum = _font(14)
    summary = topic.get("summary", "")
    sum_lines = _wrap(summary, f_sum, max_text_w)
    sum_y = tag_base_y + 28
    sum_h = len(sum_lines) * 20

    kp = topic.get("key_point", "")

    # 阴影 + 卡片
    draw.rounded_rectangle([cx + 3, y + 3, cx + cw + 3, y + ch + 3],
                           radius=RADIUS, fill="#D1D5DB")
    draw.rounded_rectangle([cx, y, cx + cw, y + ch], radius=RADIUS, fill=CARD_BG)

    # 排名徽章
    badge_x, badge_y = cx + 14, y + 16
    if rank <= 3:
        colors = [(255, 107, 53), (249, 115, 22), (234, 179, 8)]
        draw.ellipse([badge_x, badge_y, badge_x + badge_r*2, badge_y + badge_r*2],
                     fill=colors[rank-1])
    else:
        draw.ellipse([badge_x, badge_y, badge_x + badge_r*2, badge_y + badge_r*2],
                     fill="#E5E7EB")
    f_badge = _font(20)
    rank_text = _rank_badge(rank)
    bb = f_badge.getbbox(rank_text)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((badge_x + badge_r - bw//2, badge_y + badge_r - bh//2 - 2),
              rank_text, fill="white" if rank <= 3 else TEXT_MUTED, font=f_badge)

    # 标题
    draw.text((tx, y + 14), title_lines[0], fill=TEXT_DARK, font=f_topic)
    if title_h > 1:
        draw.text((tx, y + 14 + LINE_H), title_lines[1], fill=TEXT_DARK, font=f_topic)

    # 情感图标
    sentiment = topic.get("sentiment", "mixed")
    f_s = _font(14)
    icon_x = tx + f_topic.getbbox(title_lines[-1])[2] + 8
    draw.text((icon_x, y + 16 + (title_h - 1) * LINE_H),
              _sentiment_icon(sentiment), fill=_sentiment_color(sentiment), font=f_s)

    # 来源标签
    sources = topic.get("sources", [])
    f_tag = _font(11)
    tag_x = tx
    tag_limit_x = cx + cw - 70
    for src in sources[:5]:
        tag_w = f_tag.getbbox(src)[2] + 12
        if tag_x + tag_w > tag_limit_x:
            break
        draw.rounded_rectangle([tag_x, y + tag_base_y, tag_x + tag_w, y + tag_base_y + 18],
                               radius=6, fill="#F3F4F6")
        draw.text((tag_x + 6, y + tag_base_y + 2), src, fill=TEXT_BODY, font=f_tag)
        tag_x += tag_w + 6

    # 摘要（多行）
    if summary:
        for li, line in enumerate(sum_lines[:2]):
            draw.text((tx, y + sum_y + li * 20), line, fill=TEXT_BODY, font=f_sum)

    # 要点
    if kp:
        f_kp = _font(13)
        kp_text = f"💡 {kp}"
        if f_kp.getbbox(kp_text)[2] > max_text_w:
            while f_kp.getbbox(kp_text + "…")[2] > max_text_w and len(kp) > 3:
                kp = kp[:-1]
            kp_text = f"💡 {kp}…"
        draw.text((tx, y + sum_y + sum_h + 4), kp_text, fill=ACCENT, font=f_kp)

    # 底部篇数
    f_info = _font(12)
    count = topic.get("article_count", 0)
    info_y = y + sum_y + sum_h + (20 if kp else 0) + 8
    draw.text((tx, info_y), f"📰 {count}篇报道", fill=TEXT_MUTED, font=f_info)

    # 右侧热度
    heat = topic.get("heat", 0)
    hx = cx + cw - 70
    f_heat = _font(26)
    hc = _heat_color(heat)
    h_text = str(heat)
    hw2 = f_heat.getbbox(h_text)[2]
    draw.text((hx + 35 - hw2//2, y + 12), h_text, fill=hc, font=f_heat)
    f_hl = _font(10)
    draw.text((hx + 24, y + 44), "HEAT", fill=TEXT_MUTED, font=f_hl)

    # 热度条
    bar_y_top = y + 62
    bar_y_bot = y + ch - 24
    bar_h = max(20, bar_y_bot - bar_y_top)
    bx = hx + 22
    draw.rounded_rectangle([bx, bar_y_top, bx + 6, bar_y_bot], radius=3, fill="#F3F4F6")
    fh = int(bar_h * heat / 100)
    if fh > 0:
        draw.rounded_rectangle([bx, bar_y_bot - fh, bx + 6, bar_y_bot],
                               radius=3, fill=hc)

    return y + ch + 12


def _draw_footer(draw: ImageDraw.Draw, y: int, w: int):
    f = _font(11)
    text = "📰 股票资讯聚合 · DeepSeek AI 生成"
    tw = f.getbbox(text)[2]
    draw.text(((w - tw)//2, y + 8), text, fill=TEXT_MUTED, font=f)


def render_digest_card(digest: dict) -> bytes:
    topics = digest.get("topics", [])[:8]
    summary = digest.get("summary", "")
    generated_at = digest.get("generated_at", "")
    ts = generated_at.replace("T", " ")[:16] if generated_at else ""

    n = len(topics)
    if n == 0:
        return None

    # 预计算高度
    topic_heights = [_calc_topic_h(t) for t in topics]
    total_topic_h = sum(topic_heights) + (n - 1) * 12

    H = HEADER_H + 30 + (SUMMARY_H + 20 if summary else 10) + total_topic_h + FOOTER_H + PADDING

    img = Image.new("RGB", (CARD_W, H), BG)
    draw = ImageDraw.Draw(img)

    _draw_header(draw, CARD_W, ts)

    next_y = HEADER_H + 12
    if summary:
        next_y = _draw_summary(draw, next_y, CARD_W, summary)
    else:
        next_y += 10

    for i, (topic, h) in enumerate(zip(topics, topic_heights)):
        next_y = _draw_topic_card(draw, next_y, CARD_W, topic, i + 1, h)

    _draw_footer(draw, next_y, CARD_W)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_digest_card_from_cache() -> bytes | None:
    from ai_summary import summarizer
    cache = summarizer._digest_cache
    if not cache or not cache.get("result"):
        return None
    return render_digest_card(cache["result"])
