"""Cookie 获取、过滤、租约、保留、更新与删除服务。"""

from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import shutil
import tempfile
import threading
import uuid
import weakref
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from noteforge.media.cookies.policy import CookiePolicy, policy_for
from noteforge.media.models import AuthRequest, CookiePersistence, VideoPlatform


class CookieSecurityError(RuntimeError):
    """Cookie 生命周期或加密约束被破坏。"""


@dataclass(frozen=True, slots=True)
class CredentialInfo:
    """持久凭据的非敏感索引信息，不包含 Cookie 值。"""

    id: str  # 随机凭据 ID，也是 Vault 子目录名。
    platform: VideoPlatform
    browser: str
    profile: str | None
    created_at: datetime
    refreshed_at: datetime
    expires_at: datetime | None  # 平台未提供整体过期时间时为空。
    cookie_count: int
    domains: tuple[str, ...]  # 经过平台白名单过滤后的域名。
    version: int = 1  # Vault 数据格式版本。


class CookieLease:
    """仅供媒体后端消费的一次性凭据；关闭后明文文件立即删除。"""

    def __init__(
        self,
        lease_id: str,
        path: Path | None,
        root: Path,
        *,
        credential: CredentialInfo | None = None,
        on_close: object | None = None,
    ) -> None:
        self.id = lease_id
        self.credential = credential
        self._path = path  # 权限为 0600 的短期 Netscape Cookie 文件。
        self._root = root  # 权限为 0700 的独占租约目录。
        self._on_close = on_close
        self._closed = False
        self._finalizer = weakref.finalize(self, shutil.rmtree, root, True)

    def _materialize_for_backend(self) -> Path | None:
        """内部后端专用；公共 API 不暴露 Cookie 路径。"""

        if self._closed:
            raise CookieSecurityError("Cookie 租约已经释放。")
        return self._path

    def close(self) -> None:
        """可选回写更新后的加密凭据，再无条件删除明文租约。"""

        if not self._closed:
            self._closed = True
            try:
                if callable(self._on_close):
                    self._on_close(self._path)
            finally:
                self._finalizer()

    def __enter__(self) -> CookieLease:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class CookieService:
    """管理平台凭据；Cookie 明文只存在于权限受限的租约目录。"""

    def __init__(
        self,
        runtime_root: Path | None = None,
        vault_root: Path | None = None,
        *,
        lease_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self.runtime_root = (
            runtime_root or Path(tempfile.gettempdir()) / "noteforge-credentials"
        )
        self.vault_root = vault_root or Path.home() / ".noteforge" / "credentials"
        self.lease_ttl = lease_ttl  # 仅用于回收异常退出后的残留租约。
        self._lock = threading.RLock()

    def anonymous(self) -> CookieLease:
        """创建不含 Cookie 的租约，统一匿名与认证执行路径。"""

        root = self._new_lease_root()
        return CookieLease(root.name, None, root)

    def acquire(
        self,
        platform: VideoPlatform | str,
        request: AuthRequest | None,
    ) -> CookieLease:
        """获取目标平台 Cookie，并按请求决定用后删除或加密保留。"""

        if request is None:
            return self.anonymous()
        platform_value = VideoPlatform(platform)
        if request.credential_id:
            jar = self._load_retained(request.credential_id, platform_value)
        else:
            jar = self._extract_browser_cookie_jar(request)
        filtered = self._filter(jar, policy_for(platform_value))
        root = self._new_lease_root()
        path = root / "cookies.txt"
        filtered.filename = str(path)
        filtered.save(ignore_discard=True, ignore_expires=True)
        os.chmod(path, 0o600)
        credential: CredentialInfo | None = None
        retained_request = request
        if request.persistence is CookiePersistence.RETAIN:
            retained_request = AuthRequest(
                request.browser,
                request.profile,
                request.persistence,
                request.credential_id or uuid.uuid4().hex,
            )
            credential = self.retain(platform_value, retained_request, filtered)

        def update(updated_path: Path | None) -> None:
            if credential is None or updated_path is None or not updated_path.exists():
                return
            updated = http.cookiejar.MozillaCookieJar(str(updated_path))
            updated.load(ignore_discard=True, ignore_expires=True)
            self.retain(
                platform_value,
                retained_request,
                self._filter(updated, policy_for(platform_value)),
            )

        return CookieLease(
            root.name,
            path,
            root,
            credential=credential,
            on_close=update if credential else None,
        )

    def retain(
        self,
        platform: VideoPlatform,
        request: AuthRequest,
        jar: http.cookiejar.MozillaCookieJar,
    ) -> CredentialInfo:
        """加密保留目标域 Cookie。需要安装 cryptography。"""

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as error:
            raise CookieSecurityError(
                "保留 Cookie 需要 cryptography；安全原因禁止降级为明文存储。"
            ) from error
        credential_id = request.credential_id or uuid.uuid4().hex
        root = self.vault_root / credential_id
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        plain = self._jar_bytes(jar)
        key = self._vault_key()
        nonce = secrets.token_bytes(12)
        aad = f"noteforge:{credential_id}:{platform.value}:v1".encode()
        encrypted = nonce + AESGCM(key).encrypt(nonce, plain, aad)
        blob = root / "cookies.enc"
        blob.write_bytes(encrypted)
        os.chmod(blob, 0o600)
        now = datetime.now(UTC)
        domains = tuple(sorted({cookie.domain for cookie in jar}))
        info = CredentialInfo(
            credential_id,
            platform,
            str(request.browser),
            request.profile,
            now,
            now,
            None,
            len(list(jar)),
            domains,
        )
        metadata = asdict(info)
        metadata["platform"] = info.platform.value
        metadata["created_at"] = info.created_at.isoformat()
        metadata["refreshed_at"] = info.refreshed_at.isoformat()
        (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        os.chmod(root / "metadata.json", 0o600)
        return info

    def revoke(self, credential_id: str) -> None:
        """删除指定加密凭据及其非敏感索引。"""

        if not credential_id or any(c not in "0123456789abcdef" for c in credential_id):
            raise ValueError("无效的 credential_id。")
        shutil.rmtree(self.vault_root / credential_id, ignore_errors=True)

    def list_credentials(self) -> tuple[CredentialInfo, ...]:
        """列出可用凭据元数据，跳过损坏条目。"""

        result: list[CredentialInfo] = []
        if not self.vault_root.exists():
            return ()
        for path in self.vault_root.glob("*/metadata.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                result.append(
                    CredentialInfo(
                        value["id"],
                        VideoPlatform(value["platform"]),
                        value["browser"],
                        value.get("profile"),
                        datetime.fromisoformat(value["created_at"]),
                        datetime.fromisoformat(value["refreshed_at"]),
                        datetime.fromisoformat(value["expires_at"])
                        if value.get("expires_at")
                        else None,
                        int(value["cookie_count"]),
                        tuple(value["domains"]),
                        int(value.get("version", 1)),
                    )
                )
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(sorted(result, key=lambda item: item.created_at))

    def refresh(
        self,
        credential_id: str,
        platform: VideoPlatform | str,
        request: AuthRequest,
    ) -> CredentialInfo:
        """从浏览器重新获取并原子替换一个保留凭据。"""

        jar = self._filter(
            self._extract_browser_cookie_jar(request),
            policy_for(platform),
        )
        retained_request = AuthRequest(
            request.browser,
            request.profile,
            CookiePersistence.RETAIN,
            credential_id,
        )
        return self.retain(VideoPlatform(platform), retained_request, jar)

    def cleanup_expired(self) -> int:
        """删除超过 TTL 的崩溃残留明文租约。"""

        removed = 0
        cutoff = datetime.now(UTC) - self.lease_ttl
        if not self.runtime_root.exists():
            return removed
        for path in self.runtime_root.iterdir():
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            except OSError:
                continue
            if modified < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        return removed

    def _new_lease_root(self) -> Path:
        """创建只有当前用户可访问的随机租约目录。"""

        self.runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_root, 0o700)
        return Path(tempfile.mkdtemp(prefix="lease-", dir=self.runtime_root))

    @staticmethod
    def _extract_browser_cookie_jar(request: AuthRequest) -> http.cookiejar.CookieJar:
        """在隔离凭据服务中读取浏览器，再在暴露前执行域过滤。

        yt-dlp 当前浏览器适配层会解密 Cookie；其返回值绝不离开本方法。
        对必须保证读取阶段也按域隔离的部署，应替换为浏览器扩展 Provider。
        """

        from yt_dlp.cookies import extract_cookies_from_browser

        profile = request.profile
        return extract_cookies_from_browser(str(request.browser), profile=profile)

    @staticmethod
    def _filter(
        source: http.cookiejar.CookieJar, policy: CookiePolicy
    ) -> http.cookiejar.MozillaCookieJar:
        """仅复制白名单域 Cookie，源 CookieJar 不会向后端暴露。"""

        target = http.cookiejar.MozillaCookieJar()
        for cookie in source:
            if policy.allows(cookie.domain):
                target.set_cookie(cookie)
        return target

    @staticmethod
    def _jar_bytes(jar: http.cookiejar.MozillaCookieJar) -> bytes:
        with tempfile.NamedTemporaryFile() as output:
            jar.filename = output.name
            jar.save(ignore_discard=True, ignore_expires=True)
            return Path(output.name).read_bytes()

    def _vault_key(self) -> bytes:
        """从显式环境变量或系统 Keyring 获取 256 位主密钥。"""

        supplied = os.environ.get("NOTEFORGE_COOKIE_VAULT_KEY")
        if supplied:
            try:
                return bytes.fromhex(supplied)
            except ValueError as error:
                raise CookieSecurityError(
                    "NOTEFORGE_COOKIE_VAULT_KEY 必须是 64 位十六进制密钥。"
                ) from error
        try:
            import keyring
        except ImportError as error:
            raise CookieSecurityError(
                "保留 Cookie 需要系统 keyring；禁止把加密密钥与 Cookie 放在同一目录。"
            ) from error
        service, account = "noteforge-cookie-vault", "local-master-key"
        stored = keyring.get_password(service, account)
        if stored is None:
            stored = secrets.token_hex(32)
            keyring.set_password(service, account, stored)
        return bytes.fromhex(stored)

    def _load_retained(
        self, credential_id: str, platform: VideoPlatform
    ) -> http.cookiejar.MozillaCookieJar:
        """解密持久凭据到短期文件，加载后立即删除该文件。"""

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as error:
            raise CookieSecurityError("读取保留 Cookie 需要 cryptography。") from error
        root = self.vault_root / credential_id
        payload = (root / "cookies.enc").read_bytes()
        nonce, ciphertext = payload[:12], payload[12:]
        aad = f"noteforge:{credential_id}:{platform.value}:v1".encode()
        plain = AESGCM(self._vault_key()).decrypt(nonce, ciphertext, aad)
        lease = self._new_lease_root()
        path = lease / "restore.txt"
        try:
            path.write_bytes(plain)
            os.chmod(path, 0o600)
            jar = http.cookiejar.MozillaCookieJar(str(path))
            jar.load(ignore_discard=True, ignore_expires=True)
            return jar
        finally:
            shutil.rmtree(lease, ignore_errors=True)
