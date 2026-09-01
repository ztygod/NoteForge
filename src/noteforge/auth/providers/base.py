"""Cookie Provider 的公共协议与安全过滤工具。"""

import http.cookiejar
from typing import Protocol

from noteforge.auth.models import AuthPlatform


class CookieProvider(Protocol):
    """从单一来源加载 Cookie 的扩展协议。"""

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar: ...


PLATFORM_DOMAINS = {
    AuthPlatform.BILIBILI: ("bilibili.com",),
    AuthPlatform.YOUTUBE: (
        "youtube.com",
        "google.com",
        "googlevideo.com",
        "youtu.be",
    ),
}


def filter_cookies(
    source: http.cookiejar.CookieJar, platform: AuthPlatform
) -> http.cookiejar.MozillaCookieJar:
    """仅复制目标平台根域及其子域 Cookie。"""

    result = http.cookiejar.MozillaCookieJar()
    for cookie in source:
        domain = cookie.domain.lstrip(".").casefold()
        if any(
            domain == allowed or domain.endswith("." + allowed)
            for allowed in PLATFORM_DOMAINS[platform]
        ):
            result.set_cookie(cookie)
    return result


def make_cookie(
    name: str,
    value: str,
    domain: str,
    *,
    path: str = "/",
    expires: int | None = None,
    secure: bool = True,
) -> http.cookiejar.Cookie:
    """把受控输入转换成标准 CookieJar 条目。"""

    normalized_domain = domain if domain.startswith(".") else "." + domain
    return http.cookiejar.Cookie(
        0,
        name,
        value,
        None,
        False,
        normalized_domain,
        True,
        normalized_domain.startswith("."),
        path or "/",
        True,
        secure,
        expires,
        False,
        None,
        None,
        {},
        False,
    )
