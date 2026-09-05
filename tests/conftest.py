"""测试环境的全局安全边界。"""

import pytest

from noteforge.auth.providers.browser import BrowserCookieProvider


@pytest.fixture(autouse=True)
def forbid_real_browser_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止单元测试读取真实浏览器或触发系统 Keyring 密码框。"""

    def forbidden_load(self, platform):
        del self, platform
        raise AssertionError("测试禁止读取真实浏览器 Cookie；请注入认证替身。")

    monkeypatch.setattr(BrowserCookieProvider, "load", forbidden_load)
    # 即使测试意外创建加密 Store，也只能使用测试密钥，不访问系统 Keyring。
    monkeypatch.setenv("NOTEFORGE_COOKIE_VAULT_KEY", "00" * 32)
