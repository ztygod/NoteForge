"""使用临时 Playwright 上下文完成交互式网页登录。"""

import http.cookiejar
from collections.abc import Iterable, Mapping
from time import monotonic, sleep

from noteforge.auth.errors import InteractiveLoginError
from noteforge.auth.models import AuthPlatform
from noteforge.auth.providers.base import filter_cookies, make_cookie


class PlaywrightCookieProvider:
    """打开可见浏览器，等待用户完成 Bilibili 或 YouTube 登录。"""

    LOGIN_URLS = {
        AuthPlatform.BILIBILI: "https://passport.bilibili.com/login",
        AuthPlatform.YOUTUBE: "https://accounts.google.com/ServiceLogin?service=youtube",
    }

    def __init__(self, timeout: int = 180) -> None:
        self.timeout = timeout

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar:
        """登录成功后提取目标域 Cookie，并销毁临时浏览器上下文。"""

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise InteractiveLoginError(
                "交互登录需要安装 Playwright，并执行 playwright install chromium。"
            ) from error
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto(self.LOGIN_URLS[platform])
                deadline = monotonic() + self.timeout
                while monotonic() < deadline:
                    jar = self._from_playwright(context.cookies())
                    filtered = filter_cookies(jar, platform)
                    if self._has_session_marker(platform, filtered):
                        context.close()
                        browser.close()
                        return filtered
                    sleep(1)
                context.close()
                browser.close()
        except InteractiveLoginError:
            raise
        except Exception as error:
            raise InteractiveLoginError("交互登录窗口被关闭或启动失败。") from error
        raise InteractiveLoginError("交互登录超时，未检测到有效登录态。")

    @staticmethod
    def _from_playwright(
        items: Iterable[Mapping[str, object]],
    ) -> http.cookiejar.CookieJar:
        """把 Playwright Cookie 映射转换为标准 CookieJar。"""

        jar = http.cookiejar.CookieJar()
        for item in items:
            name, value, domain = (
                item.get("name"),
                item.get("value"),
                item.get("domain"),
            )
            # TypedDict 经过 all() 后无法可靠收窄，逐项检查可兼容 Pyright。
            if not isinstance(name, str):
                continue
            if not isinstance(value, str):
                continue
            if not isinstance(domain, str):
                continue
            raw_path = item.get("path")
            cookie_path = raw_path if isinstance(raw_path, str) else "/"
            expires = item.get("expires")
            cookie_expires = (
                int(expires)
                if isinstance(expires, (int, float))
                and not isinstance(expires, bool)
                and expires > 0
                else None
            )
            jar.set_cookie(
                make_cookie(
                    name,
                    value,
                    domain,
                    path=cookie_path,
                    expires=cookie_expires,
                    secure=bool(item.get("secure", True)),
                )
            )
        return jar

    @staticmethod
    def _has_session_marker(
        platform: AuthPlatform, jar: http.cookiejar.CookieJar
    ) -> bool:
        names = {cookie.name for cookie in jar}
        if platform is AuthPlatform.BILIBILI:
            return "SESSDATA" in names and "DedeUserID" in names
        return bool(names & {"SAPISID", "__Secure-3PAPISID", "SID"})
