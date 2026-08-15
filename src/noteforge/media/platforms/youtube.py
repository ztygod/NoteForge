from noteforge.media.models import VideoPlatform
from noteforge.media.platforms.base import PlatformAdapter


class YouTubeAdapter(PlatformAdapter):
    """YouTube 适配器；当前无需额外后端请求参数。"""

    platform = VideoPlatform.YOUTUBE
