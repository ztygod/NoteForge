from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DownloadError

from noteforge.collector.base import Collector
from noteforge.collector.bilibili import (
    BilibiliCollector,
    get_bilibili_video_info,
)
from noteforge.exceptions import (
    CollectionError,
    InvalidCollectionResponseError,
    LoginRequiredError,
    RemoteCollectionError,
    RiskControlError,
    UnsupportedSourceError,
    VideoUnavailableError,
)
from noteforge.subtitle.models import SubtitleFile

SOURCE = "https://www.bilibili.com/video/BV1CkArz1E4o?p=2"
INFO = {
    "id": "BV1CkArz1E4o",
    "title": "测试视频",
    "description": "简介",
    "uploader": "UP主",
    "uploader_id": "789",
    "duration": 60,
    "webpage_url": SOURCE,
    "thumbnail": "https://example.com/cover.jpg",
    "upload_date": "20231114",
    "view_count": 100,
    "like_count": 7,
    "extractor": "BiliBili",
    "extractor_key": "BiliBili",
    "formats": [{"url": "不应被 NoteForge 模型暴露"}],
}


def _downloader_returning(info: object) -> Mock:
    downloader = Mock()
    downloader.__enter__ = Mock(return_value=downloader)
    downloader.__exit__ = Mock(return_value=False)
    downloader.extract_info.return_value = info
    return downloader


def test_bilibili_collector_implements_collector_abstraction() -> None:
    assert isinstance(BilibiliCollector(), Collector)


def test_get_bilibili_video_info_maps_metadata_without_exposing_raw_data() -> None:
    downloader = _downloader_returning(INFO)

    with patch(
        "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
        return_value=downloader,
    ) as youtube_dl:
        result = get_bilibili_video_info(SOURCE)

    options = youtube_dl.call_args.args[0]
    assert options == {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreconfig": True,
        "noplaylist": True,
        "impersonate": ImpersonateTarget(client="chrome"),
        "cookiesfrombrowser": ("chrome",),
        "writesubtitles": True,
        "writeautomaticsub": True,
        "http_headers": {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        },
    }
    downloader.extract_info.assert_called_once_with(SOURCE, download=False)
    assert result.metadata.id == "BV1CkArz1E4o"
    assert result.metadata.title == "测试视频"
    assert result.metadata.uploader == "UP主"
    assert result.metadata.like_count == 7
    assert not hasattr(result.metadata, "formats")


def test_collector_can_load_browser_cookies() -> None:
    downloader = _downloader_returning(INFO)

    with patch(
        "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
        return_value=downloader,
    ) as youtube_dl:
        BilibiliCollector(cookies_from_browser="chrome").collect(SOURCE)

    assert youtube_dl.call_args.args[0]["cookiesfrombrowser"] == ("chrome",)


def test_collector_parses_manual_and_automatic_subtitle_tracks() -> None:
    info = INFO | {
        "subtitles": {
            "zh-CN": [
                {
                    "ext": "vtt",
                    "url": "https://example.com/manual.vtt",
                    "name": "中文",
                }
            ]
        },
        "automatic_captions": {
            "en": [
                {
                    "ext": "srt",
                    "url": "https://example.com/automatic.srt",
                }
            ]
        },
    }
    downloader = _downloader_returning(info)

    with patch(
        "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
        return_value=downloader,
    ):
        result = BilibiliCollector().collect(SOURCE)

    assert result.metadata.title == "测试视频"
    assert len(result.subtitle_tracks) == 2
    assert result.subtitle_tracks[0].language == "zh-CN"
    assert result.subtitle_tracks[0].name == "中文"
    assert result.subtitle_tracks[0].is_automatic is False
    assert result.subtitle_tracks[1].language == "en"
    assert result.subtitle_tracks[1].is_automatic is True


def test_collector_skips_malformed_subtitle_entries() -> None:
    info = INFO | {
        "subtitles": {
            "": [{"ext": "vtt", "url": "https://example.com/empty.vtt"}],
            "zh": [
                None,
                {"ext": "vtt"},
                {"url": "https://example.com/no-extension"},
                {"ext": "vtt", "url": "https://example.com/valid.vtt"},
            ],
            "en": "not-a-list",
        }
    }
    downloader = _downloader_returning(info)

    with patch(
        "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
        return_value=downloader,
    ):
        result = BilibiliCollector().collect(SOURCE)

    assert len(result.subtitle_tracks) == 1
    assert result.subtitle_tracks[0].url.endswith("valid.vtt")


def test_collector_discovers_bilibili_inline_ai_subtitle() -> None:
    info = INFO | {
        "subtitles": {
            "ai-zh": [
                {
                    "ext": "srt",
                    "data": "1\n00:00:00,000 --> 00:00:01,000\n大家好\n",
                }
            ]
        }
    }
    downloader = _downloader_returning(info)

    with patch(
        "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
        return_value=downloader,
    ):
        result = BilibiliCollector().collect(SOURCE)

    assert len(result.subtitle_tracks) == 1
    assert result.subtitle_tracks[0].language == "ai-zh"
    assert result.subtitle_tracks[0].extension == "srt"
    assert result.subtitle_tracks[0].is_automatic is True
    assert result.subtitle_tracks[0].url.startswith("yt-dlp-inline://")


def test_get_bilibili_video_info_parses_selected_srt(
    tmp_path: Path,
) -> None:
    info = INFO | {
        "subtitles": {
            "ai-zh": [
                {
                    "ext": "srt",
                    "data": "1\n00:00:00,000 --> 00:00:01,000\n大家好\n",
                }
            ]
        }
    }
    downloader = _downloader_returning(info)
    subtitle_path = tmp_path / "subtitle.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n大家好\n",
        encoding="utf-8",
    )

    with (
        patch(
            "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        patch(
            "noteforge.collector.bilibili."
            "YtDlpSubtitleDownloader.download",
            return_value=SubtitleFile(
                path=subtitle_path,
                language="ai-zh",
                extension="srt",
                is_automatic=True,
            ),
        ),
    ):
        result = get_bilibili_video_info(
            SOURCE,
            subtitle_output_dir=tmp_path,
        )

    assert result.selected_subtitle is not None
    assert result.selected_subtitle.extension == "srt"
    assert result.transcript is not None
    assert result.transcript.source == "automatic_subtitle"
    assert result.transcript.segments[0].text == "大家好"


@pytest.mark.parametrize("missing_field", ["id", "title", "webpage_url"])
def test_get_bilibili_video_info_rejects_missing_required_field(
    missing_field: str,
) -> None:
    info = INFO | {missing_field: None}
    downloader = _downloader_returning(info)

    with (
        patch(
            "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(InvalidCollectionResponseError, match=missing_field),
    ):
        get_bilibili_video_info(SOURCE)


@pytest.mark.parametrize(
    ("message", "expected_exception"),
    [
        ("Unsupported URL: example:invalid", UnsupportedSourceError),
        ("Video is unavailable", VideoUnavailableError),
        ("Login required; use cookies", LoginRequiredError),
        ("HTTP Error 412: Precondition Failed", RiskControlError),
        ("The operation timed out", RemoteCollectionError),
        ("A different extractor failure", RemoteCollectionError),
    ],
)
def test_download_error_is_translated(
    message: str, expected_exception: type[CollectionError]
) -> None:
    downloader = _downloader_returning(INFO)
    downloader.extract_info.side_effect = DownloadError(message)

    with (
        patch(
            "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(expected_exception) as raised,
    ):
        get_bilibili_video_info(SOURCE)

    assert isinstance(raised.value.__cause__, DownloadError)


def test_unknown_downloader_error_preserves_exception_chain() -> None:
    downloader = _downloader_returning(INFO)
    downloader.extract_info.side_effect = RuntimeError("unexpected")

    with (
        patch(
            "noteforge.collector.bilibili.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(RemoteCollectionError) as raised,
    ):
        get_bilibili_video_info(SOURCE)

    assert isinstance(raised.value.__cause__, RuntimeError)
