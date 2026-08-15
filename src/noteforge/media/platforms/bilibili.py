from collections.abc import Mapping
from typing import Any

from noteforge.media.models import VideoPlatform
from noteforge.media.platforms.base import PlatformAdapter


class BilibiliAdapter(PlatformAdapter):
    """补充 Bilibili 请求所需的来源页和语言请求头。"""

    platform = VideoPlatform.BILIBILI

    def backend_options(self) -> Mapping[str, Any]:
        """Referer 用于满足 Bilibili 的媒体请求校验。"""

        return {
            "http_headers": {
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.bilibili.com/",
            }
        }
