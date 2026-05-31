"""
翻译模块 - Google Translate (免费) + DeepSeek fallback
Render 美国 IP 可直接访问 Google Translate
"""
import re
import httpx
from config import DEEPSEEK_API_KEY


def translate_text(text: str, target: str = "zh-cn") -> str:
    """
    翻译文本为中文
    优先使用 Google Translate（免费），失败则用 DeepSeek
    """
    if not text or not text.strip():
        return ""

    # 检测是否已经是中文（简单判断）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars > len(text) * 0.3:
        return text  # 已经是中文，不翻译

    # 方法1：Google Translate（免费，Render US IP 可用）
    result = _google_translate(text, target)
    if result:
        return result

    # 方法2：DeepSeek API（付费但稳定，中国 IP 也可用）
    if DEEPSEEK_API_KEY:
        result = _deepseek_translate(text, target)
        if result:
            return result

    return ""


def _google_translate(text: str, target: str = "zh-cn") -> str:
    """Google Translate 免费 API"""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target,
            "dt": "t",
            "q": text[:500],  # Google 限制长度
        }
        resp = httpx.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return ""

        data = resp.json()
        # 拼接所有句子的翻译结果
        parts = []
        for sentence in data[0]:
            if sentence[0]:
                parts.append(sentence[0])
        result = "".join(parts)
        return result.strip() if result else ""
    except Exception:
        return ""


def _deepseek_translate(text: str, target: str = "zh-cn") -> str:
    """DeepSeek API 翻译"""
    try:
        resp = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": f"将以下英文翻译成中文，只返回翻译结果，不要解释：\n\n{text[:1000]}",
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return ""

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception:
        return ""
