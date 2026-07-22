"""B站视频信息收集

关于具体的 B站视频信息接口请求接口的返回数据结构，请参考野生文档：
https://github.com/renovate-bot/catlair-_-bilibili-API-collect/blob/master/video/info.md
"""

from dataclasses import dataclass
from typing import Any, Mapping

import requests

from noteforge.collector.collect.base import Collector
from noteforge.exceptions import (
    InvalidCollectionResponseError,
    RemoteCollectionError,
    RiskControlError,
)

_VIDEO_INFO_URL = "https://api.bilibili.com/x/web-interface/view"
_REQUEST_TIMEOUT_SECONDS = 10

# 模拟浏览器请求头，避开b站风控
_REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.bilibili.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True, slots=True)
class BilibiliVideoOwner:
    """B站视频 UP 主信息。"""

    # UP主 mid
    mid: int

    # UP主昵称
    name: str

    # UP主头像链接
    face: str


@dataclass(frozen=True, slots=True)
class BilibiliVideoStat:
    """B站视频状态数信息。"""

    # 播放数
    view: int

    # 弹幕数
    danmaku: int

    # 评论数
    reply: int

    # 收藏数
    favorite: int

    # 投币数
    coin: int

    # 分享数
    share: int

    # 点赞数
    like: int


@dataclass(frozen=True, slots=True)
class BilibiliVideoPage:
    """B站视频分 P 信息。"""

    # 分P的 CID
    cid: int

    # 分P的页码序号
    page: int

    # 分P标题
    part: str

    # 分P时长，单位为秒
    duration: int


@dataclass(frozen=True, slots=True)
class BilibiliVideoSubtitle:
    """B站视频 CC 字幕信息。"""

    # 字幕 ID
    id: int

    # 字幕语言
    lan: str

    # 字幕语言名称
    lan_doc: str

    # JSON 格式字幕文件 URL
    subtitle_url: str

    # 字幕上传者信息
    # author


@dataclass(frozen=True, slots=True)
class BilibiliVideoData:
    """B站视频信息。"""

    # 视频 BV 号
    bvid: str

    # 视频 AV 号
    aid: int

    # 视频分P总数，默认为 1
    videos: int

    # 稿件标题
    title: str

    # 稿件发布时间
    pubdate: int

    # 视频简介
    desc: str

    # 视频 UP 主信息
    owner: BilibiliVideoOwner

    # 视频状态数
    stat: BilibiliVideoStat

    # 视频 1P 的 CID
    cid: int

    # 视频分P信息列表
    pages: list[BilibiliVideoPage]

    # 视频 CC 字幕信息，默认为空列表
    subtitle: list[BilibiliVideoSubtitle]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BilibiliVideoData":
        """把接口数据转换为类型化模型，并忽略接口新增的无关字段"""

        owner = payload["owner"]
        stat = payload["stat"]
        pages = payload.get("pages") or []
        subtitle_container = payload.get("subtitle") or {}
        subtitles = subtitle_container.get("list") or []

        return cls(
            bvid=payload["bvid"],
            aid=payload["aid"],
            videos=payload.get("videos", 1),
            title=payload["title"],
            pubdate=payload["pubdate"],
            desc=payload.get("desc", ""),
            owner=BilibiliVideoOwner(
                mid=owner["mid"], name=owner["name"], face=owner["face"]
            ),
            stat=BilibiliVideoStat(
                view=stat["view"],
                danmaku=stat["danmaku"],
                reply=stat["reply"],
                favorite=stat["favorite"],
                coin=stat["coin"],
                share=stat["share"],
                like=stat["like"],
            ),
            cid=payload["cid"],
            pages=[
                BilibiliVideoPage(
                    cid=page["cid"],
                    page=page["page"],
                    part=page["part"],
                    duration=page["duration"],
                )
                for page in pages
            ],
            subtitle=[
                BilibiliVideoSubtitle(
                    id=subtitle["id"],
                    lan=subtitle["lan"],
                    lan_doc=subtitle["lan_doc"],
                    subtitle_url=subtitle["subtitle_url"],
                )
                for subtitle in subtitles
            ],
        )


@dataclass(frozen=True, slots=True)
class BilibiliCollectorResult:
    """B站视频信息接口响应。"""

    # 接口请求状态码
    # 0：成功
    # 400：请求错误
    # 403：权限不足
    # 404：无视频
    # 62002：稿件不可见
    code: int

    # 接口请求错误信息，默认为 0
    message: str

    # 默认为 1
    ttl: int

    # 视频信息
    data: BilibiliVideoData | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BilibiliCollectorResult":
        data = payload.get("data")
        return cls(
            code=payload["code"],
            message=str(payload.get("message", "")),
            ttl=payload.get("ttl", 1),
            data=BilibiliVideoData.from_mapping(data) if data is not None else None,
        )


class BilibiliCollector(Collector[BilibiliCollectorResult]):
    """B站视频信息采集器。"""

    def collect(self, source_id: str) -> BilibiliCollectorResult:
        """根据 BV 号采集B站视频信息。"""

        try:
            response = requests.get(
                _VIDEO_INFO_URL,
                params={"bvid": source_id},
                headers=_REQUEST_HEADERS,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else None
            )
            if status_code == 412:
                raise RiskControlError(
                    "B站拒绝了本次请求（HTTP 412），请稍后重试或更换网络。"
                ) from error
            raise RemoteCollectionError(
                f"B站接口请求失败（HTTP {status_code or '未知'}）。"
            ) from error
        except requests.Timeout as error:
            raise RemoteCollectionError("连接B站超时，请稍后重试。") from error
        except requests.ConnectionError as error:
            raise RemoteCollectionError(
                "无法连接B站，请检查网络后重试。"
            ) from error
        except requests.RequestException as error:
            raise RemoteCollectionError("请求B站接口失败，请稍后重试。") from error

        try:
            payload = response.json()
        except requests.JSONDecodeError as error:
            raise InvalidCollectionResponseError(
                "B站返回了无法解析的响应。"
            ) from error

        if not isinstance(payload, dict):
            raise InvalidCollectionResponseError("B站返回了格式异常的响应。")

        result = BilibiliCollectorResult.from_mapping(payload)
        if result.code != 0:
            raise RemoteCollectionError(
                f"B站接口返回错误（{result.code}）：{result.message or '未知错误'}"
            )
        return result


def get_bilibili_video_info(bvid: str) -> BilibiliCollectorResult:
    """获取B站视频信息。

    获取方式：http://api.bilibili.com/x/web-interface/view
    请求方式：GET

    Args:
        bvid (str): 视频 BV 号

    Returns:
        BilibiliCollectorResult: B站视频信息接口响应
    """

    return BilibiliCollector().collect(bvid)
