"""视频资源采集应用层。"""

from noteforge.collector.factory import collect_video, create_video_collector, discover_video
from noteforge.collector.platforms import BilibiliVideoCollector, YouTubeCollector
from noteforge.collector.source import InspectionPlatform, InspectionResult, inspect_source

__all__ = [
    "BilibiliVideoCollector",
    "YouTubeCollector",
    "InspectionPlatform",
    "InspectionResult",
    "create_video_collector",
    "collect_video",
    "discover_video",
    "inspect_source",
]
