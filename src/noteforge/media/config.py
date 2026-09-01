"""媒体提取配置和可复用的身份认证设置。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """平台网络配置；身份认证由 AuthManager 独立管理。"""

    proxy: str | None = None  # 仅作用于该平台；不包含认证信息。


@dataclass(frozen=True, slots=True)
class ExtractorConfig:
    """媒体服务运行配置。"""

    cache_path: Path = Path(".cache/noteforge/media")  # 非敏感标准化数据。
    platforms: Mapping[str, PlatformConfig] = field(default_factory=dict)
    runtime_path: Path = Path(".cache/noteforge/runtime")  # 临时媒体租约根目录。
    credential_vault_path: Path = Path(".noteforge/credentials")  # 加密凭据库。
    worker_count: int = 2  # 隔离 yt-dlp 的最大进程数。

    def for_platform(self, platform: str) -> PlatformConfig:
        """返回平台配置；未配置时使用无代理默认值。"""

        return self.platforms.get(platform, PlatformConfig())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExtractorConfig":
        """从已解析的配置映射构造并校正字段。"""

        root = value.get("extractor", value)
        if not isinstance(root, Mapping):
            return cls()
        platforms: dict[str, PlatformConfig] = {}
        reserved = {
            "cache_path",
            "runtime_path",
            "credential_vault_path",
            "worker_count",
            "proxy",
        }
        for name, item in root.items():
            if name in reserved:
                continue
            if not isinstance(item, Mapping):
                continue
            proxy = item.get("proxy") or root.get("proxy")
            platforms[name] = PlatformConfig(
                proxy=proxy if isinstance(proxy, str) and proxy else None,
            )
        cache = root.get("cache_path", ".cache/noteforge/media")
        runtime = root.get("runtime_path", ".cache/noteforge/runtime")
        vault = root.get("credential_vault_path", ".noteforge/credentials")
        try:
            workers = max(1, int(root.get("worker_count", 2)))
        except (TypeError, ValueError):
            workers = 2
        return cls(
            Path(str(cache)),
            platforms,
            Path(str(runtime)),
            Path(str(vault)),
            workers,
        )


def load_extractor_config(path: str | Path = "config.yaml") -> ExtractorConfig:
    """在不增加 YAML 依赖的情况下读取项目约定的 YAML 配置子集。"""

    config_path = Path(path)
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return ExtractorConfig()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        key, raw_value = line.strip().split(":", 1)
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        text = raw_value.strip().strip("\"'")
        if not text:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = text
    return ExtractorConfig.from_mapping(root)
