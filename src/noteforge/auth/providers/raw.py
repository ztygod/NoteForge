"""解析用户显式提供的 Cookie Header 文本。"""

import http.cookiejar
from http.cookies import SimpleCookie

from noteforge.auth.errors import CookieImportError
from noteforge.auth.models import AuthPlatform
from noteforge.auth.providers.base import PLATFORM_DOMAINS, make_cookie


class RawCookieProvider:
    """把 name=value 列表转换成平台限定 CookieJar。"""

    def __init__(self, raw_cookie: str) -> None:
        self.raw_cookie = raw_cookie

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar:
        """解析 Cookie Header；错误消息绝不回显原文。"""

        parsed = SimpleCookie()
        try:
            parsed.load(self.raw_cookie)
        except Exception as error:
            raise CookieImportError("无法解析粘贴的 Cookie。") from error
        if not parsed:
            raise CookieImportError("粘贴的 Cookie 为空或格式无效。")
        jar = http.cookiejar.CookieJar()
        domain = PLATFORM_DOMAINS[platform][0]
        for name, morsel in parsed.items():
            jar.set_cookie(make_cookie(name, morsel.value, domain))
        return jar
