"""为媒体后端生成权限受限、用后即删的 Cookie 临时租约。"""

from __future__ import annotations

import http.cookiejar
import os
import shutil
import tempfile
import weakref
from datetime import UTC, datetime, timedelta
from pathlib import Path

from noteforge.media.cookies.policy import CookiePolicy, policy_for
from noteforge.media.models import VideoPlatform


class CookieSecurityError(RuntimeError):
    """Cookie 临时租约的安全约束被破坏。"""


class CookieLease:
    """仅供媒体后端消费的一次性凭据；关闭后立即删除明文文件。"""

    def __init__(self, lease_id: str, path: Path | None, root: Path) -> None:
        self.id = lease_id
        self._path = path  # 权限为 0600 的短期 Netscape Cookie 文件。
        self._root = root  # 权限为 0700 的独占租约目录。
        self._closed = False
        self._finalizer = weakref.finalize(self, shutil.rmtree, root, True)

    def backend_path(self) -> Path | None:
        """返回租约期内的后端路径；调用方不得记录或长期持有。"""

        if self._closed:
            raise CookieSecurityError("Cookie 租约已经释放。")
        return self._path

    def close(self) -> None:
        """删除临时 Cookie 文件及其独占目录；可重复调用。"""

        if not self._closed:
            self._closed = True
            self._finalizer()

    def __enter__(self) -> CookieLease:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class CookieService:
    """Cookie 临时租约工厂；不负责导入、验证或持久化。"""

    def __init__(
        self,
        runtime_root: Path | None = None,
        *,
        lease_ttl: timedelta = timedelta(minutes=30),
    ) -> None:
        self.runtime_root = (
            runtime_root or Path(tempfile.gettempdir()) / "noteforge-credentials"
        )
        self.lease_ttl = lease_ttl

    def anonymous(self) -> CookieLease:
        """创建无 Cookie 租约，统一匿名与认证后端调用路径。"""

        root = self._new_lease_root()
        return CookieLease(root.name, None, root)

    def lease(
        self,
        platform: VideoPlatform | str,
        jar: http.cookiejar.CookieJar,
    ) -> CookieLease:
        """过滤目标平台 Cookie 并生成权限为 0600 的临时文件。"""

        filtered = self._filter(jar, policy_for(platform))
        if not list(filtered):
            return self.anonymous()
        root = self._new_lease_root()
        path = root / "cookies.txt"
        filtered.filename = str(path)
        filtered.save(ignore_discard=True, ignore_expires=True)
        os.chmod(path, 0o600)
        return CookieLease(root.name, path, root)

    def cleanup_expired(self) -> int:
        """删除超过 TTL 的异常退出残留租约。"""

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
    def _filter(
        source: http.cookiejar.CookieJar, policy: CookiePolicy
    ) -> http.cookiejar.MozillaCookieJar:
        """按平台白名单复制 Cookie，拒绝把其他域凭据交给后端。"""

        target = http.cookiejar.MozillaCookieJar()
        for cookie in source:
            if policy.allows(cookie.domain):
                target.set_cookie(cookie)
        return target
