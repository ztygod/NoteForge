"""通过关键字段和低成本远程请求验证平台登录态。"""

from __future__ import annotations

import http.cookiejar
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from noteforge.auth.errors import CookieValidationError
from noteforge.auth.models import AuthPlatform, AuthResult, AuthStatus


class CookieValidator:
    """验证 Cookie 完整性以及远程平台确认的真实登录态。"""

    BILIBILI_REQUIRED = {"SESSDATA", "DedeUserID", "bili_jct"}
    YOUTUBE_MARKERS = {"SID", "SAPISID", "__Secure-3PAPISID"}
    BROWSER_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
    }

    def __init__(
        self,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._client_factory = client_factory or (
            lambda: httpx.Client(timeout=10, follow_redirects=True)
        )

    def validate(
        self,
        platform: AuthPlatform,
        cookies: http.cookiejar.CookieJar,
    ) -> AuthResult:
        """返回稳定状态；网络错误不会被误判为 Cookie 过期。"""

        items = list(cookies)
        if not items:
            return AuthResult(platform, AuthStatus.NO_COOKIE)
        names = {cookie.name for cookie in items}
        if platform is AuthPlatform.BILIBILI:
            complete = self.BILIBILI_REQUIRED <= names
        else:
            complete = bool(self.YOUTUBE_MARKERS & names)
        if not complete:
            return AuthResult(platform, AuthStatus.MISSING_REQUIRED_FIELDS)
        try:
            with self._client_factory() as client:
                if platform is AuthPlatform.BILIBILI:
                    response = client.get(
                        "https://api.bilibili.com/x/web-interface/nav",
                        cookies=self._cookie_dict(cookies),
                        # Bilibili 会拒绝缺少常规浏览器指纹的 API 请求并返回 412。
                        headers=self.BROWSER_HEADERS
                        | {
                            "Referer": "https://www.bilibili.com/",
                            "Origin": "https://www.bilibili.com",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    valid = bool(
                        isinstance(payload, dict)
                        and isinstance(payload.get("data"), dict)
                        and payload["data"].get("isLogin") is True
                    )
                else:
                    response = client.get(
                        "https://www.youtube.com/feed/subscriptions",
                        cookies=self._cookie_dict(cookies),
                        headers=self.BROWSER_HEADERS,
                    )
                    response.raise_for_status()
                    # YouTube 登录页面会包含稳定的登录标志；不记录响应正文。
                    valid = '"LOGGED_IN":true' in response.text.replace(" ", "")
        except (httpx.HTTPError, ValueError) as error:
            raise CookieValidationError("认证状态验证请求失败。") from error
        return AuthResult(
            platform,
            AuthStatus.AUTHENTICATED if valid else AuthStatus.COOKIE_EXPIRED,
            refreshed_at=datetime.now(UTC) if valid else None,
        )

    @staticmethod
    def _cookie_dict(cookies: http.cookiejar.CookieJar) -> dict[str, str]:
        return {cookie.name: cookie.value for cookie in cookies}
