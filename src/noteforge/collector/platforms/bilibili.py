"""Bilibili 平台采集器。"""

from noteforge.collector.source.inspection import InspectionPlatform, inspect_source
from noteforge.collector.platforms.base import PlatformCollector
from noteforge.exceptions import UnsupportedSourceError
from noteforge.media.models import VideoPlatform

class BilibiliVideoCollector(PlatformCollector):
    platform = VideoPlatform.BILIBILI.value

    def supports(self, source: str) -> bool:
        return inspect_source(source).platform is InspectionPlatform.BILIBILI

    def normalize(self, source: str) -> str:
        result = inspect_source(source)
        if result.platform is not InspectionPlatform.BILIBILI or result.normalized_source is None:
            raise UnsupportedSourceError(f"不支持的 Bilibili URL：{source}")
        return result.normalized_source

    def ytdlp_options(self):
        return {"http_headers": {"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Referer": "https://www.bilibili.com/"}}
