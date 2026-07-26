"""视频信息采集过程中可向用户安全展示的异常。"""

from noteforge.exceptions.base import NoteForgeError


class CollectionError(NoteForgeError):
    """采集失败的基础异常。"""


class RiskControlError(CollectionError):
    """远程平台触发访问风控。"""


class RemoteCollectionError(CollectionError):
    """远程平台请求失败。"""


class UnsupportedSourceError(RemoteCollectionError):
    """远程采集器不支持该来源 URL。"""


class VideoUnavailableError(RemoteCollectionError):
    """视频不存在或当前不可访问。"""


class LoginRequiredError(RemoteCollectionError):
    """视频需要登录后访问。"""


class InvalidCollectionResponseError(CollectionError):
    """远程平台返回了无法解析的数据。"""
