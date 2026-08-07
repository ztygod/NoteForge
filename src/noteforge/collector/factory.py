from noteforge.collector.platforms import BilibiliVideoCollector, PlatformCollector, YouTubeCollector
from noteforge.exceptions import UnsupportedSourceError
from noteforge.media.config import ExtractorConfig
from noteforge.media.config import PlatformConfig, load_extractor_config
from noteforge.media.models import VideoResource
from pathlib import Path
from noteforge.collector.source import inspect_source


def create_video_collector(source: str, config: ExtractorConfig | None = None) -> PlatformCollector:
    for collector_type in (BilibiliVideoCollector, YouTubeCollector):
        collector = collector_type(config)
        if collector.supports(source):
            return collector
    raise UnsupportedSourceError(f"不支持的视频 URL：{source}")


def _runtime_config(
    source: str,
    *,
    cookies_from_browser: str | None,
    cache_path: Path | None = None,
) -> ExtractorConfig:
    """构造单次采集配置，显式命令行参数优先于配置文件。"""

    config = load_extractor_config()
    platforms = dict(config.platforms)
    if cookies_from_browser:
        platform = inspect_source(source).platform.value
        current = config.for_platform(platform)
        platforms[platform] = PlatformConfig(
            current.cookie_file,
            cookies_from_browser,
            current.proxy,
        )
    return ExtractorConfig(
        cache_path or config.cache_path,
        config.download_path,
        platforms,
    )


def collect_video(
    source: str,
    *,
    cookies_from_browser: str | None = None,
    subtitle_language: str | None = None,
    subtitle_output_dir: Path | None = None,
    page_number: int | None = None,
) -> VideoResource:
    """选择平台采集器并提取完整视频资源。"""

    del page_number
    config = _runtime_config(
        source,
        cookies_from_browser=cookies_from_browser,
        cache_path=subtitle_output_dir,
    )
    return create_video_collector(source, config).extract(
        source,
        subtitle_language=subtitle_language,
    )


def discover_video(
    source: str,
    *,
    cookies_from_browser: str | None = None,
) -> VideoResource:
    """选择平台采集器并发现视频元数据与字幕轨道。"""

    config = _runtime_config(source, cookies_from_browser=cookies_from_browser)
    return create_video_collector(source, config).discover(source)
