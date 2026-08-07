"""YouTube 平台应用层采集器。"""

from noteforge.collector.source.inspection import InspectionPlatform, inspect_source
from noteforge.collector.platforms.base import PlatformCollector
from noteforge.exceptions import UnsupportedSourceError
from noteforge.media.models import VideoPlatform


class YouTubeCollector(PlatformCollector):
    platform = VideoPlatform.YOUTUBE.value

    def supports(self, source: str) -> bool:
        return inspect_source(source).platform is InspectionPlatform.YOUTUBE

    def normalize(self, source: str) -> str:
        result = inspect_source(source)
        if result.platform is not InspectionPlatform.YOUTUBE or result.normalized_source is None:
            raise UnsupportedSourceError(f"不支持的 YouTube URL：{source}")
        return result.normalized_source
