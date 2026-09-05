"""统一认证生命周期的单元测试。"""

import http.cookiejar
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from noteforge.auth import (
    AuthManager,
    AuthPlatform,
    AuthRequiredError,
    AuthResult,
    AuthStatus,
    CookieExpiredError,
    CookieImportError,
    CookieSource,
    EncryptedCookieStore,
    JsonCookieProvider,
    PlaywrightCookieProvider,
    RawCookieProvider,
)
from noteforge.auth.providers.base import make_cookie
from noteforge.auth.validator import CookieValidator
from noteforge.exceptions import LoginRequiredError
from noteforge.media.config import ExtractorConfig
from noteforge.media.cookies import CookieService
from noteforge.media.models import SubtitleAccessStatus
from noteforge.media.service import MediaService


def _cookies(platform: AuthPlatform) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.CookieJar()
    if platform is AuthPlatform.BILIBILI:
        values = {
            "SESSDATA": "session-secret",
            "DedeUserID": "123",
            "bili_jct": "csrf-secret",
        }
        domain = "bilibili.com"
    else:
        values = {"SAPISID": "session-secret"}
        domain = "youtube.com"
    for name, value in values.items():
        jar.set_cookie(make_cookie(name, value, domain))
    return jar


class MemoryStore:
    """测试专用内存存储。"""

    def __init__(self, jar=None):
        self.jar = jar
        self.saved = 0

    def load(self, platform):
        del platform
        return self.jar

    def save(self, platform, cookies, source):
        del platform, source
        self.jar = cookies
        self.saved += 1

    def clear(self, platform):
        del platform
        self.jar = None

    def exists(self, platform):
        del platform
        return self.jar is not None


class FixedValidator:
    """按 Cookie 名称返回确定状态。"""

    def validate(self, platform, cookies):
        names = {cookie.name for cookie in cookies}
        if not names:
            status = AuthStatus.NO_COOKIE
        elif "expired" in names:
            status = AuthStatus.COOKIE_EXPIRED
        elif (
            platform is AuthPlatform.BILIBILI
            and not {
                "SESSDATA",
                "DedeUserID",
                "bili_jct",
            }
            <= names
        ):
            status = AuthStatus.MISSING_REQUIRED_FIELDS
        else:
            status = AuthStatus.AUTHENTICATED
        return AuthResult(platform, status, refreshed_at=datetime.now(UTC))


class FixedProvider:
    def __init__(self, jar=None, error=None):
        self.jar = jar
        self.error = error
        self.source = CookieSource("browser", "chrome")
        self.calls = 0

    def load(self, platform):
        del platform
        self.calls += 1
        if self.error:
            raise self.error
        return self.jar


class FakeHttpClient:
    """模拟 httpx 上下文客户端。"""

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        del args

    def get(self, url, **kwargs):
        del kwargs
        request = httpx.Request("GET", url)
        if "bilibili" in url:
            return httpx.Response(200, json=self.payload, request=request)
        return httpx.Response(200, text=str(self.payload), request=request)


def test_encrypted_cookie_store_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOTEFORGE_COOKIE_VAULT_KEY", "ab" * 32)
    store = EncryptedCookieStore(tmp_path)
    store.save(
        AuthPlatform.BILIBILI,
        _cookies(AuthPlatform.BILIBILI),
        CookieSource("browser", "chrome"),
    )

    loaded = store.load(AuthPlatform.BILIBILI)

    assert loaded is not None
    assert {cookie.name for cookie in loaded} == {
        "SESSDATA",
        "DedeUserID",
        "bili_jct",
    }
    assert store.exists(AuthPlatform.BILIBILI)
    assert "session-secret" not in (tmp_path / "bilibili/metadata.json").read_text()
    store.clear(AuthPlatform.BILIBILI)
    assert not store.exists(AuthPlatform.BILIBILI)


def test_raw_and_json_providers_filter_domains(tmp_path: Path) -> None:
    raw = RawCookieProvider("SESSDATA=value; DedeUserID=1; bili_jct=csrf")
    assert {cookie.name for cookie in raw.load(AuthPlatform.BILIBILI)} == {
        "SESSDATA",
        "DedeUserID",
        "bili_jct",
    }
    path = tmp_path / "cookies.json"
    path.write_text(
        '[{"name":"SESSDATA","value":"ok","domain":".bilibili.com"},'
        '{"name":"stolen","value":"bad","domain":".example.com"}]',
        encoding="utf-8",
    )
    imported = JsonCookieProvider(path).load(AuthPlatform.BILIBILI)
    assert [cookie.name for cookie in imported] == ["SESSDATA"]


def test_validator_distinguishes_missing_valid_and_expired() -> None:
    missing = http.cookiejar.CookieJar()
    missing.set_cookie(make_cookie("SESSDATA", "value", "bilibili.com"))
    validator = CookieValidator(lambda: FakeHttpClient({"data": {"isLogin": True}}))
    assert (
        validator.validate(AuthPlatform.BILIBILI, missing).status
        is AuthStatus.MISSING_REQUIRED_FIELDS
    )
    assert (
        validator.validate(
            AuthPlatform.BILIBILI, _cookies(AuthPlatform.BILIBILI)
        ).status
        is AuthStatus.AUTHENTICATED
    )
    expired = CookieValidator(lambda: FakeHttpClient({"data": {"isLogin": False}}))
    assert (
        expired.validate(AuthPlatform.BILIBILI, _cookies(AuthPlatform.BILIBILI)).status
        is AuthStatus.COOKIE_EXPIRED
    )


def test_playwright_cookie_mapping_is_type_safe() -> None:
    jar = PlaywrightCookieProvider._from_playwright(
        [
            {
                "name": "SESSDATA",
                "value": "secret",
                "domain": ".bilibili.com",
                "path": "/",
                "expires": -1.0,
                "secure": True,
            },
            {"name": "invalid", "value": 123, "domain": ".bilibili.com"},
        ]
    )

    cookies = list(jar)
    assert len(cookies) == 1
    assert cookies[0].name == "SESSDATA"
    assert cookies[0].expires is None


def test_manager_uses_valid_store_without_browser(tmp_path: Path) -> None:
    provider = FixedProvider(error=AssertionError("不应读取浏览器"))
    manager = AuthManager(
        MemoryStore(_cookies(AuthPlatform.BILIBILI)),
        validator=FixedValidator(),
        cookie_service=CookieService(runtime_root=tmp_path),
        browser_provider_factory=lambda browser: provider,
    )

    with manager.get_cookie(AuthPlatform.BILIBILI) as lease:
        assert lease.backend_path().exists()
    assert provider.calls == 0


def test_manager_refreshes_missing_store_and_saves(tmp_path: Path) -> None:
    store = MemoryStore()
    provider = FixedProvider(_cookies(AuthPlatform.BILIBILI))
    manager = AuthManager(
        store,
        validator=FixedValidator(),
        cookie_service=CookieService(runtime_root=tmp_path),
        browser_provider_factory=lambda browser: provider,
    )

    with manager.get_cookie(AuthPlatform.BILIBILI):
        pass

    assert provider.calls == 1
    assert store.saved == 1


def test_manager_reports_import_failure_without_store(tmp_path: Path) -> None:
    provider = FixedProvider(error=CookieImportError("browser unavailable"))
    manager = AuthManager(
        MemoryStore(),
        validator=FixedValidator(),
        cookie_service=CookieService(runtime_root=tmp_path),
        browser_provider_factory=lambda browser: provider,
    )

    with pytest.raises(AuthRequiredError):
        manager.get_cookie(AuthPlatform.BILIBILI)


def test_manager_reports_expired_when_refresh_fails(tmp_path: Path) -> None:
    expired = http.cookiejar.CookieJar()
    expired.set_cookie(make_cookie("expired", "secret", "bilibili.com"))
    provider = FixedProvider(error=CookieImportError("browser unavailable"))
    manager = AuthManager(
        MemoryStore(expired),
        validator=FixedValidator(),
        cookie_service=CookieService(runtime_root=tmp_path),
        browser_provider_factory=lambda browser: provider,
    )

    with pytest.raises(CookieExpiredError):
        manager.get_cookie(AuthPlatform.BILIBILI)


class FakeAuthManager:
    """为 MediaService 提供可计数的认证租约。"""

    def __init__(self, service, *, unavailable=False):
        self.service = service
        self.unavailable = unavailable
        self.refresh_calls = 0

    def get_cookie(self, platform):
        if self.unavailable:
            raise AuthRequiredError("没有 Cookie")
        return self.service.lease(platform.value, _cookies(platform))

    def refresh_from_browser(self, platform, *, browser=None):
        del browser
        self.refresh_calls += 1
        return self.service.lease(platform.value, _cookies(platform))


class SubtitleWorker:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = 0

    def execute(self, payload):
        self.calls += 1
        if self.calls <= self.failures:
            raise LoginRequiredError("需要登录")
        return {
            "id": "BV1CkArz1E4o",
            "title": "Demo",
            "webpage_url": payload["source"],
            "subtitles": {},
        }

    def close(self):
        pass


def _media(tmp_path, worker, *, unavailable=False):
    cookie_service = CookieService(runtime_root=tmp_path / "leases")
    auth = FakeAuthManager(cookie_service, unavailable=unavailable)
    service = MediaService(
        ExtractorConfig(cache_path=tmp_path / "cache"),
        cookie_service=cookie_service,
        auth_manager=auth,
        worker=worker,
    )
    return service, auth


def test_media_refreshes_and_retries_once(tmp_path: Path) -> None:
    worker = SubtitleWorker(failures=1)
    service, auth = _media(tmp_path, worker)

    resource = service.discover("https://www.bilibili.com/video/BV1CkArz1E4o")

    assert worker.calls == 2
    assert auth.refresh_calls == 1
    assert resource.subtitle_status is SubtitleAccessStatus.NO_SUBTITLE


def test_media_does_not_retry_more_than_once(tmp_path: Path) -> None:
    worker = SubtitleWorker(failures=2)
    service, auth = _media(tmp_path, worker)

    with pytest.raises(AuthRequiredError):
        service.discover("https://www.bilibili.com/video/BV1CkArz1E4o")

    assert worker.calls == 2
    assert auth.refresh_calls == 1


def test_anonymous_empty_subtitles_are_login_required(tmp_path: Path) -> None:
    service, _ = _media(tmp_path, SubtitleWorker(), unavailable=True)

    resource = service.discover("https://www.bilibili.com/video/BV1CkArz1E4o")

    assert resource.subtitle_status is SubtitleAccessStatus.LOGIN_REQUIRED
