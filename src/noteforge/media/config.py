"""媒体提取配置和可复用的身份认证设置。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """非交互式认证配置：使用 Cookie 文件或已登录的浏览器配置。"""

    cookie_file: Path | None = None
    cookies_from_browser: str | None = None
    proxy: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractorConfig:
    cache_path: Path = Path(".cache/noteforge/media")
    download_path: Path = Path(".cache/noteforge/downloads")
    platforms: Mapping[str, PlatformConfig] = field(default_factory=dict)

    def for_platform(self, platform: str) -> PlatformConfig:
        return self.platforms.get(platform, PlatformConfig())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExtractorConfig":
        root = value.get("extractor", value)
        if not isinstance(root, Mapping):
            return cls()
        platforms: dict[str, PlatformConfig] = {}
        reserved = {"cache_path", "download_path", "proxy"}
        for name, item in root.items():
            if name in reserved:
                continue
            if not isinstance(item, Mapping):
                continue
            cookie = item.get("cookie_file") or item.get("cookies")
            browser = item.get("cookies_from_browser")
            proxy = item.get("proxy") or root.get("proxy")
            platforms[name] = PlatformConfig(
                cookie_file=Path(cookie) if isinstance(cookie, str) and cookie else None,
                cookies_from_browser=(browser if isinstance(browser, str) and browser else None),
                proxy=proxy if isinstance(proxy, str) and proxy else None,
            )
        cache = root.get("cache_path", ".cache/noteforge/media")
        download = root.get("download_path", ".cache/noteforge/downloads")
        return cls(Path(str(cache)), Path(str(download)), platforms)


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
        text = raw_value.strip().strip('"\'')
        if not text:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = text
    return ExtractorConfig.from_mapping(root)
