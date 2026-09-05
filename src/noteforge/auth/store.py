"""Cookie 持久化接口及基于现有 Vault 约定的加密实现。"""

from __future__ import annotations

import base64
import binascii
import http.cookiejar
import json
import os
import secrets
import shutil
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from noteforge.auth.errors import CredentialStoreError
from noteforge.auth.models import AuthPlatform, CookieSource


class CookieStore(Protocol):
    """Cookie 持久化边界，不负责导入或远程验证。"""

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar | None: ...

    def save(
        self,
        platform: AuthPlatform,
        cookies: http.cookiejar.CookieJar,
        source: CookieSource,
    ) -> None: ...

    def clear(self, platform: AuthPlatform) -> None: ...

    def exists(self, platform: AuthPlatform) -> bool: ...


class EncryptedCookieStore:
    """使用 AES-GCM 和系统 Keyring 保存每个平台的当前凭据。"""

    FORMAT_VERSION = 3
    CREDENTIAL_FILENAME = "credential.v3.enc"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".noteforge" / "credentials"

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar | None:
        """解密并返回 CookieJar；不存在时返回空。"""

        credential_path = self._credential_path(platform)
        if not credential_path.exists():
            return None

        try:
            # Cookie 和 metadata 位于同一个加密 envelope 中，因此读取到的内容
            # 一定来自同一次成功保存，不会发生两个文件版本不一致的问题。
            envelope = self._load_envelope(platform)
            return self._jar_from_bytes(self._cookie_bytes(envelope))
        except CredentialStoreError:
            raise
        except Exception as error:
            raise CredentialStoreError("无法读取加密 Cookie 存储。") from error

    def save(
        self,
        platform: AuthPlatform,
        cookies: http.cookiejar.CookieJar,
        source: CookieSource,
    ) -> None:
        """验证非空后原子替换指定平台的加密 Cookie。"""

        if not list(cookies):
            raise ValueError("不能保存空 Cookie。")
        target = self._platform_root(platform)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(target, 0o700)
            cookie_bytes = self._jar_bytes(cookies)
            envelope = {
                "platform": platform.value,
                "source": source.kind,
                "browser": source.browser,
                "refreshed_at": datetime.now(UTC).isoformat(),
                "cookie_count": len(list(cookies)),
                "version": self.FORMAT_VERSION,
                "cookies": base64.b64encode(cookie_bytes).decode("ascii"),
            }
            # metadata 与 Cookie 一起序列化并整体加密，只产生一个待提交文件。
            plain = json.dumps(
                envelope, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            nonce = secrets.token_bytes(12)
            encrypted = nonce + AESGCM(self._vault_key()).encrypt(
                nonce,
                plain,
                self._aad(platform),
            )
            # 原子替换成功前，旧凭据文件始终保持完整可用。
            self._atomic_write(self._credential_path(platform), encrypted)
        except CredentialStoreError:
            raise
        except Exception as error:
            raise CredentialStoreError("无法写入加密 Cookie 存储。") from error

    def clear(self, platform: AuthPlatform) -> None:
        """删除 NoteForge 保存的凭据，不修改浏览器 Cookie。"""

        # 每个平台只有一个独立目录，删除目录即可清除密文及异常中断的临时文件。
        shutil.rmtree(self._platform_root(platform), ignore_errors=True)

    def exists(self, platform: AuthPlatform) -> bool:
        """判断指定平台是否有加密 Cookie。"""

        return self._credential_path(platform).exists()

    def metadata(self, platform: AuthPlatform) -> dict[str, object]:
        """读取不包含敏感值的来源元数据。"""

        if not self._credential_path(platform).exists():
            return {}

        # 对外只返回安全的描述字段，不暴露 envelope 内的 Cookie 数据。
        envelope = self._load_envelope(platform)
        return {
            key: envelope[key]
            for key in (
                "platform",
                "source",
                "browser",
                "refreshed_at",
                "cookie_count",
                "version",
            )
        }

    def _platform_root(self, platform: AuthPlatform) -> Path:
        return self.root / platform.value

    def _credential_path(self, platform: AuthPlatform) -> Path:
        """返回指定平台唯一的加密凭据文件路径。"""

        return self._platform_root(platform) / self.CREDENTIAL_FILENAME

    def _load_envelope(self, platform: AuthPlatform) -> dict[str, object]:
        """解密并严格校验单文件凭据 envelope。"""

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            payload = self._credential_path(platform).read_bytes()
            if len(payload) <= 12:
                raise ValueError("凭据密文长度无效")
            plain = AESGCM(self._vault_key()).decrypt(
                payload[:12], payload[12:], self._aad(platform)
            )
            envelope = json.loads(plain.decode("utf-8"))
            if not isinstance(envelope, dict):
                raise ValueError("凭据 envelope 必须是对象")
            if envelope.get("version") != self.FORMAT_VERSION:
                raise ValueError("凭据 envelope 版本不匹配")
            if envelope.get("platform") != platform.value:
                raise ValueError("凭据 envelope 平台不匹配")
            if not isinstance(envelope.get("source"), str):
                raise ValueError("凭据 envelope 来源无效")
            if envelope.get("browser") is not None and not isinstance(
                envelope.get("browser"), str
            ):
                raise ValueError("凭据 envelope 浏览器无效")
            refreshed_at = envelope.get("refreshed_at")
            if not isinstance(refreshed_at, str):
                raise ValueError("凭据 envelope 刷新时间无效")
            datetime.fromisoformat(refreshed_at)
            cookie_count = envelope.get("cookie_count")
            if (
                not isinstance(cookie_count, int)
                or isinstance(cookie_count, bool)
                or cookie_count <= 0
            ):
                raise ValueError("凭据 envelope Cookie 数量无效")
            cookie_bytes = self._cookie_bytes(envelope)
            jar = self._jar_from_bytes(cookie_bytes)
            if len(list(jar)) != cookie_count:
                raise ValueError("凭据 envelope Cookie 数量不匹配")
            return envelope
        except CredentialStoreError:
            raise
        except Exception as error:
            raise CredentialStoreError("无法读取加密 Cookie 存储。") from error

    @staticmethod
    def _cookie_bytes(envelope: dict[str, object]) -> bytes:
        encoded = envelope.get("cookies")
        if not isinstance(encoded, str):
            raise ValueError("凭据 envelope Cookie 数据无效")
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("凭据 envelope Cookie 编码无效") from error

    def _aad(self, platform: AuthPlatform) -> bytes:
        """构造绑定平台和格式版本的附加认证数据，防止密文跨平台复用。"""

        return f"noteforge:{platform.value}:v{self.FORMAT_VERSION}".encode()

    @staticmethod
    def _atomic_write(path: Path, value: bytes) -> None:
        temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
        try:
            with temp.open("xb") as output:
                os.chmod(temp, 0o600)
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, path)
            EncryptedCookieStore._sync_directory(path.parent)
        finally:
            temp.unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        """同步目录项；不支持目录 fsync 的平台安全跳过。"""

        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    @staticmethod
    def _jar_bytes(cookies: Iterable[http.cookiejar.Cookie]) -> bytes:
        jar = http.cookiejar.MozillaCookieJar()
        for cookie in cookies:
            jar.set_cookie(cookie)
        with tempfile.NamedTemporaryFile() as output:
            jar.filename = output.name
            jar.save(ignore_discard=True, ignore_expires=True)
            return Path(output.name).read_bytes()

    @staticmethod
    def _jar_from_bytes(value: bytes) -> http.cookiejar.MozillaCookieJar:
        with tempfile.NamedTemporaryFile() as source:
            Path(source.name).write_bytes(value)
            jar = http.cookiejar.MozillaCookieJar(source.name)
            jar.load(ignore_discard=True, ignore_expires=True)
            jar.filename = None
            return jar

    @staticmethod
    def _vault_key() -> bytes:
        supplied = os.environ.get("NOTEFORGE_COOKIE_VAULT_KEY")
        if supplied:
            try:
                key = bytes.fromhex(supplied)
            except ValueError as error:
                raise CredentialStoreError(
                    "Cookie Vault 密钥必须是十六进制。"
                ) from error
            if len(key) != 32:
                raise CredentialStoreError("Cookie Vault 密钥必须为 256 位。")
            return key
        try:
            import keyring
        except ImportError as error:
            raise CredentialStoreError("加密保存 Cookie 需要系统 keyring。") from error
        service, account = "noteforge-cookie-vault", "local-master-key"
        stored = keyring.get_password(service, account)
        if stored is None:
            stored = secrets.token_hex(32)
            keyring.set_password(service, account, stored)
        return bytes.fromhex(stored)
