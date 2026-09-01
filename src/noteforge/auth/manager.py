"""统一编排 Cookie 获取、验证、刷新、持久化与短期租约。"""

from __future__ import annotations

import http.cookiejar
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from noteforge.auth.errors import (
    AuthRequiredError,
    CookieExpiredError,
    CookieImportError,
)
from noteforge.auth.models import AuthPlatform, AuthResult, AuthStatus, CookieSource
from noteforge.auth.providers import (
    BrowserCookieProvider,
    JsonCookieProvider,
    PlaywrightCookieProvider,
    RawCookieProvider,
)
from noteforge.auth.store import CookieStore, EncryptedCookieStore
from noteforge.auth.validator import CookieValidator

if TYPE_CHECKING:
    from noteforge.media.cookies.service import CookieLease, CookieService


class AuthManager:
    """业务层唯一允许使用的认证生命周期入口。"""

    def __init__(
        self,
        store: CookieStore | None = None,
        *,
        validator: CookieValidator | None = None,
        cookie_service: CookieService | None = None,
        browser_provider_factory: Callable[[str | None], BrowserCookieProvider]
        | None = None,
    ) -> None:
        # 延迟导入可避免 media 公共包初始化时反向加载 AuthManager。
        if cookie_service is None:
            from noteforge.media.cookies.service import CookieService

            cookie_service = CookieService()
        self.store = store or EncryptedCookieStore()
        self.validator = validator or CookieValidator()
        self.cookie_service = cookie_service
        self._browser_provider_factory = browser_provider_factory or (
            lambda browser: BrowserCookieProvider(browser)
        )
        self._locks = {platform: threading.RLock() for platform in AuthPlatform}

    def get_cookie(
        self, platform: AuthPlatform, *, browser: str | None = None
    ) -> CookieLease:
        """读取并验证 Store；无有效凭据时自动从浏览器刷新。"""

        platform = AuthPlatform(platform)
        with self._locks[platform]:
            stored = self.store.load(platform)
            if stored is not None:
                result = self.validator.validate(platform, stored)
                if result.status is AuthStatus.AUTHENTICATED:
                    return self.cookie_service.lease(platform.value, stored)
            return self.refresh(platform, browser=browser)

    def refresh(
        self, platform: AuthPlatform, *, browser: str | None = None
    ) -> CookieLease:
        """优先从本机浏览器重新导入、验证并持久化 Cookie。"""

        platform = AuthPlatform(platform)
        with self._locks[platform]:
            provider = self._browser_provider_factory(browser)
            try:
                cookies = provider.load(platform)
            except CookieImportError as error:
                if self.store.exists(platform):
                    raise CookieExpiredError(
                        f"{platform.value} Cookie 已过期，自动刷新未成功。"
                    ) from error
                raise AuthRequiredError(
                    f"未找到有效的 {platform.value} 浏览器登录态。"
                ) from error
            self._validate_required(platform, cookies)
            source = provider.source or CookieSource("browser", browser)
            self.store.save(platform, cookies, source)
            return self.cookie_service.lease(platform.value, cookies)

    def is_authenticated(self, platform: AuthPlatform) -> bool:
        """返回当前持久凭据是否通过真实登录态验证。"""

        return self.status(platform).status is AuthStatus.AUTHENTICATED

    def status(self, platform: AuthPlatform) -> AuthResult:
        """返回不包含 Cookie 明文的认证状态。"""

        platform = AuthPlatform(platform)
        cookies = self.store.load(platform)
        if cookies is None:
            return AuthResult(platform, AuthStatus.NO_COOKIE)
        result = self.validator.validate(platform, cookies)
        metadata = (
            self.store.metadata(platform)
            if isinstance(self.store, EncryptedCookieStore)
            else {}
        )
        refreshed = metadata.get("refreshed_at")
        try:
            refreshed_at = (
                datetime.fromisoformat(refreshed)
                if isinstance(refreshed, str)
                else None
            )
        except ValueError:
            refreshed_at = None
        return AuthResult(
            platform,
            result.status,
            str(metadata.get("source")) if metadata.get("source") else None,
            str(metadata.get("browser")) if metadata.get("browser") else None,
            refreshed_at,
        )

    def login_from_browser(
        self, platform: AuthPlatform, *, browser: str | None = None
    ) -> AuthResult:
        """显式从浏览器导入，不复用 Store 中的旧 Cookie。"""

        platform = AuthPlatform(platform)
        provider = self._browser_provider_factory(browser)
        cookies = provider.load(platform)
        result = self._validate_required(platform, cookies)
        source = provider.source or CookieSource("browser", browser)
        self.store.save(platform, cookies, source)
        return AuthResult(
            platform,
            result.status,
            source.kind,
            source.browser,
            result.refreshed_at,
        )

    def login_from_json(self, platform: AuthPlatform, path: Path) -> AuthResult:
        """从扩展导出的 JSON 导入并验证登录态。"""

        return self._login_provider(platform, JsonCookieProvider(path), "json")

    def login_from_raw(self, platform: AuthPlatform, raw_cookie: str) -> AuthResult:
        """从 Cookie Header 文本导入并验证登录态。"""

        return self._login_provider(platform, RawCookieProvider(raw_cookie), "raw")

    def login_interactively(
        self, platform: AuthPlatform, *, timeout: int = 180
    ) -> AuthResult:
        """启动可见浏览器并在真实验证成功后保存 Cookie。"""

        return self._login_provider(
            platform, PlaywrightCookieProvider(timeout), "playwright"
        )

    def logout(self, platform: AuthPlatform) -> None:
        """清除 NoteForge 保存的指定平台凭据。"""

        self.store.clear(AuthPlatform(platform))

    def _login_provider(self, platform, provider, source: str) -> AuthResult:
        platform = AuthPlatform(platform)
        cookies = provider.load(platform)
        result = self._validate_required(platform, cookies)
        self.store.save(platform, cookies, CookieSource(source))
        return AuthResult(
            platform, result.status, source, refreshed_at=result.refreshed_at
        )

    def _validate_required(
        self, platform: AuthPlatform, cookies: http.cookiejar.CookieJar
    ) -> AuthResult:
        result = self.validator.validate(platform, cookies)
        if result.status is AuthStatus.AUTHENTICATED:
            return result
        if result.status is AuthStatus.COOKIE_EXPIRED:
            raise CookieExpiredError(f"{platform.value} Cookie 已失效。")
        raise CookieImportError(f"导入的 {platform.value} Cookie 缺少必要登录字段。")
