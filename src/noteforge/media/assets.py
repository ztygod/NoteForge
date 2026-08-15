"""有界生命周期的媒体资产。"""

from __future__ import annotations

import shutil
import threading
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from noteforge.media.models import MediaType, VideoMetadata


class AssetExpiredError(RuntimeError):
    """访问已关闭或超过 TTL 的媒体资产。"""


@dataclass(frozen=True, slots=True)
class AssetReference:
    """可安全传递的资产描述，不暴露 Worker 内部参数。"""

    id: str  # 单次下载产生的随机资产 ID。
    media_type: MediaType
    expires_at: datetime  # UTC 绝对过期时间。
    metadata: VideoMetadata


class MediaAsset:
    """调用方持有的临时资产；close 或退出上下文后立即回收。"""

    def __init__(
        self,
        reference: AssetReference,
        path: Path,
        lease_root: Path,
    ) -> None:
        self.reference = reference
        self._path = path  # 仅在租约有效期内可访问。
        self._lease_root = lease_root  # close 时整体删除，避免遗漏旁路文件。
        self._closed = False
        self._lock = threading.Lock()
        self._finalizer = weakref.finalize(self, shutil.rmtree, lease_root, True)

    @property
    def path(self) -> Path:
        """返回有效临时路径；过期访问会先回收再报错。"""

        if self._closed or datetime.now(UTC) >= self.reference.expires_at:
            self.close()
            raise AssetExpiredError(f"媒体资产 {self.reference.id} 已失效。")
        return self._path

    def open(self, mode: str = "rb") -> BinaryIO:
        """以二进制流读取临时媒体。"""

        if "b" not in mode:
            raise ValueError("媒体资产只能以二进制模式打开。")
        return self.path.open(mode)

    def export_to(self, destination: Path) -> Path:
        """显式持久化；这是唯一允许长期保存媒体的操作。"""

        destination.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(self.path, destination))

    def close(self) -> None:
        """幂等回收整个资产租约目录。"""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._finalizer()

    def __enter__(self) -> MediaAsset:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


DEFAULT_ASSET_TTL = timedelta(hours=1)
