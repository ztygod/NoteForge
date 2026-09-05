"""平台请求签名扩展点。

Bilibili 的 WBI/CSRF 只应在具体接口明确要求时使用；YouTube 播放器签名继续
由 yt-dlp 维护。本模块刻意不提供与当前平台无关的 MTOP 签名。
"""


def csrf_token(cookie_values: dict[str, str]) -> str | None:
    """返回 Bilibili bili_jct CSRF token；不存在时返回空。"""

    return cookie_values.get("bili_jct")
