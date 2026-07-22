"""视频信息采集过程中可向用户安全展示的异常。"""


class CollectionError(Exception):
    """采集失败的基础异常。"""


class RiskControlError(CollectionError):
    """远程平台触发访问风控。"""


class RemoteCollectionError(CollectionError):
    """远程平台请求失败。"""


class InvalidCollectionResponseError(CollectionError):
    """远程平台返回了无法解析的数据。"""
