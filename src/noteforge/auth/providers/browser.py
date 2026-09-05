"""从本机浏览器安全导入目标平台 Cookie。"""

from __future__ import annotations

import http.cookiejar
import sys
from pathlib import Path

from noteforge.auth.errors import CookieImportError
from noteforge.auth.models import AuthPlatform, CookieSource
from noteforge.auth.providers.base import filter_cookies


class BrowserCookieProvider:
    """复用 yt-dlp 的跨平台浏览器 Cookie 解密能力。"""

    DEFAULT_BROWSERS = (
        "chrome",
        "edge",
        "brave",
        "arc",
        "chromium",
        "firefox",
        "safari",
    )

    def __init__(self, browser: str | None = None, profile: str | None = None) -> None:
        self.browser = browser.casefold() if browser else None
        self.profile = profile
        self.source: CookieSource | None = None

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar:
        """按优先级返回第一个包含目标域 Cookie 的浏览器。"""

        failures: list[str] = []
        browsers = (self.browser,) if self.browser else self.DEFAULT_BROWSERS
        for browser in browsers:
            try:
                jar = self._extract(browser)
                filtered = filter_cookies(jar, platform)
                if list(filtered):
                    self.source = CookieSource("browser", browser)
                    return filtered
            except Exception:
                # 浏览器错误可能包含系统路径或解密细节，不向上拼接原始消息。
                failures.append(browser)
        attempted = "、".join(failures or browsers)
        raise CookieImportError(f"无法从本机浏览器导入有效 Cookie：{attempted}")

    def _extract(self, browser: str) -> http.cookiejar.CookieJar:
        from yt_dlp.cookies import extract_cookies_from_browser

        if browser != "arc":
            return extract_cookies_from_browser(browser, profile=self.profile)
        profile = self.profile or str(self._arc_profile())
        # Arc 使用 Chromium Cookie 格式，显式传入其用户数据目录。
        return extract_cookies_from_browser("chrome", profile=profile)

    @staticmethod
    def _arc_profile() -> Path:
        if sys.platform == "darwin":
            return Path.home() / "Library/Application Support/Arc/User Data/Default"
        if sys.platform.startswith("win"):
            return Path.home() / "AppData/Local/Arc/User Data/Default"
        return Path.home() / ".config/Arc/User Data/Default"
