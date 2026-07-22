from unittest.mock import Mock, patch

import pytest

from noteforge.collector.collect.base import Collector
from noteforge.collector.collect.bilibili import (
    BilibiliCollector,
    get_bilibili_video_info,
)


def test_bilibili_collector_implements_collector_abstraction() -> None:
    assert isinstance(BilibiliCollector(), Collector)


def test_get_bilibili_video_info_parses_nested_response() -> None:
    response = Mock()
    response.json.return_value = {
        "code": 0,
        "message": "0",
        "ttl": 1,
        "data": {
            "bvid": "BV1CkArz1E4o",
            "aid": 123,
            "videos": 1,
            "title": "测试视频",
            "pubdate": 1_700_000_000,
            "desc": "简介",
            "cid": 456,
            "owner": {"mid": 789, "name": "UP主", "face": "face.jpg"},
            "stat": {
                "view": 1,
                "danmaku": 2,
                "reply": 3,
                "favorite": 4,
                "coin": 5,
                "share": 6,
                "like": 7,
            },
            "pages": [
                {"cid": 456, "page": 1, "part": "第一P", "duration": 60}
            ],
            "subtitle": {
                "list": [
                    {
                        "id": 10,
                        "lan": "zh-CN",
                        "lan_doc": "中文（简体）",
                        "subtitle_url": "//example.com/subtitle.json",
                        "author": {"mid": 789},
                    }
                ]
            },
            "dynamic": "接口中未建模的字段应被忽略",
        },
    }

    with patch(
        "noteforge.collector.collect.bilibili.requests.get", return_value=response
    ) as request:
        result = get_bilibili_video_info("BV1CkArz1E4o")

    request.assert_called_once_with(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": "BV1CkArz1E4o"},
        timeout=10,
    )
    response.raise_for_status.assert_called_once_with()
    assert result.data is not None
    assert result.data.owner.name == "UP主"
    assert result.data.stat.like == 7
    assert result.data.pages[0].part == "第一P"
    assert result.data.subtitle[0].lan == "zh-CN"


def test_get_bilibili_video_info_preserves_api_error() -> None:
    response = Mock()
    response.json.return_value = {
        "code": -400,
        "message": "请求错误",
        "ttl": 1,
        "data": None,
    }

    with patch(
        "noteforge.collector.collect.bilibili.requests.get", return_value=response
    ):
        result = get_bilibili_video_info("invalid")

    assert result.code == -400
    assert result.data is None


def test_get_bilibili_video_info_rejects_non_object_response() -> None:
    response = Mock()
    response.json.return_value = []

    with (
        patch(
            "noteforge.collector.collect.bilibili.requests.get",
            return_value=response,
        ),
        pytest.raises(ValueError, match="non-object"),
    ):
        get_bilibili_video_info("BV1CkArz1E4o")
