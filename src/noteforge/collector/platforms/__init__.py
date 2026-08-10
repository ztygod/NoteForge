"""不同视频平台的采集策略。"""

from noteforge.collector.platforms.base import PlatformCollector
from noteforge.collector.platforms.bilibili import BilibiliVideoCollector
from noteforge.collector.platforms.youtube import YouTubeCollector

__all__ = ["BilibiliVideoCollector", "PlatformCollector", "YouTubeCollector"]
