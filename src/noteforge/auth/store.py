"""Cookie 持久化接口及基于现有 Vault 约定的加密实现。"""

from __future__ import annotations

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

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".noteforge" / "credentials"

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar | None:
        """解密并返回 CookieJar；不存在时返回空。"""

        target = self._platform_root(platform)
        blob = target / "cookies.enc"
        if not blob.exists():
            return self._load_legacy(platform)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            payload = blob.read_bytes()
            nonce, ciphertext = payload[:12], payload[12:]
            plain = AESGCM(self._vault_key()).decrypt(
                nonce,
                ciphertext,
                f"noteforge:{platform.value}:v2".encode(),
            )
            return self._jar_from_bytes(plain)
        except Exception as error:
            raise RuntimeError("无法读取加密 Cookie 存储。") from error

    def save(
        self,
        platform: AuthPlatform,
        cookies: http.cookiejar.CookieJar,
        source: CookieSource,
    ) -> None:
        """验证非空后原子替换指定平台的加密 Cookie。"""

        if not list(cookies):
            raise ValueError("不能保存空 Cookie。")
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as error:
            raise RuntimeError("加密保存 Cookie 需要 cryptography。") from error
        target = self._platform_root(platform)
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target, 0o700)
        nonce = secrets.token_bytes(12)
        encrypted = nonce + AESGCM(self._vault_key()).encrypt(
            nonce,
            self._jar_bytes(cookies),
            f"noteforge:{platform.value}:v2".encode(),
        )
        self._atomic_write(target / "cookies.enc", encrypted)
        metadata = json.dumps(
            {
                "platform": platform.value,
                "source": source.kind,
                "browser": source.browser,
                "refreshed_at": datetime.now(UTC).isoformat(),
                "cookie_count": len(list(cookies)),
                "version": 2,
            },
            ensure_ascii=False,
        ).encode()
        self._atomic_write(target / "metadata.json", metadata)

    def clear(self, platform: AuthPlatform) -> None:
        """删除 NoteForge 保存的凭据，不修改浏览器 Cookie。"""

        shutil.rmtree(self._platform_root(platform), ignore_errors=True)
        for root, metadata in self._legacy_entries(platform):
            del metadata
            shutil.rmtree(root, ignore_errors=True)

    def exists(self, platform: AuthPlatform) -> bool:
        """判断指定平台是否有加密 Cookie。"""

        return (self._platform_root(platform) / "cookies.enc").exists() or bool(
            self._legacy_entries(platform)
        )

    def metadata(self, platform: AuthPlatform) -> dict[str, object]:
        """读取不包含敏感值的来源元数据。"""

        try:
            value = json.loads(
                (self._platform_root(platform) / "metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _platform_root(self, platform: AuthPlatform) -> Path:
        return self.root / platform.value

    def _load_legacy(self, platform: AuthPlatform) -> http.cookiejar.CookieJar | None:
        """兼容读取原 CookieService 创建的 v1 随机凭据目录。"""

        entries = self._legacy_entries(platform)
        if not entries:
            return None
        root, metadata = max(
            entries,
            key=lambda item: str(item[1].get("refreshed_at", "")),
        )
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            payload = (root / "cookies.enc").read_bytes()
            nonce, ciphertext = payload[:12], payload[12:]
            credential_id = str(metadata["id"])
            plain = AESGCM(self._vault_key()).decrypt(
                nonce,
                ciphertext,
                f"noteforge:{credential_id}:{platform.value}:v1".encode(),
            )
            return self._jar_from_bytes(plain)
        except Exception as error:
            raise RuntimeError("无法读取旧版加密 Cookie 存储。") from error

    def _legacy_entries(
        self, platform: AuthPlatform
    ) -> list[tuple[Path, dict[str, object]]]:
        entries: list[tuple[Path, dict[str, object]]] = []
        if not self.root.exists():
            return entries
        for path in self.root.glob("*/metadata.json"):
            if path.parent.name in {item.value for item in AuthPlatform}:
                continue
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
                if (
                    isinstance(metadata, dict)
                    and metadata.get("platform") == platform.value
                    and (path.parent / "cookies.enc").exists()
                ):
                    entries.append((path.parent, metadata))
            except (OSError, json.JSONDecodeError):
                continue
        return entries

    @staticmethod
    def _atomic_write(path: Path, value: bytes) -> None:
        temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
        try:
            temp.write_bytes(value)
            os.chmod(temp, 0o600)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

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
                raise RuntimeError("Cookie Vault 密钥必须是十六进制。") from error
            if len(key) != 32:
                raise RuntimeError("Cookie Vault 密钥必须为 256 位。")
            return key
        try:
            import keyring
        except ImportError as error:
            raise RuntimeError("加密保存 Cookie 需要系统 keyring。") from error
        service, account = "noteforge-cookie-vault", "local-master-key"
        stored = keyring.get_password(service, account)
        if stored is None:
            stored = secrets.token_hex(32)
            keyring.set_password(service, account, stored)
        return bytes.fromhex(stored)
