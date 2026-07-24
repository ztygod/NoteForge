from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from yt_dlp.utils import DownloadError

from noteforge.collector.models import SubtitleTrack
from noteforge.exceptions import (
    InvalidSubtitleResponseError,
    SubtitleDownloadError,
    SubtitleNotFoundError,
)
from noteforge.subtitle.downloader import YtDlpSubtitleDownloader

SOURCE = "https://www.bilibili.com/video/BV1test"
TRACK = SubtitleTrack(
    language="zh-CN",
    extension="vtt",
    url="https://example.com/subtitle.vtt",
)


def _downloader_returning(info: object) -> Mock:
    downloader = Mock()
    downloader.__enter__ = Mock(return_value=downloader)
    downloader.__exit__ = Mock(return_value=False)
    downloader.extract_info.return_value = info
    return downloader


def test_downloads_only_subtitle_and_reads_requested_filepath(
    tmp_path: Path,
) -> None:
    expected_path = tmp_path / "subtitle.zh-CN.vtt"
    downloader = _downloader_returning(
        {
            "requested_subtitles": {
                "zh-CN": {
                    "ext": "vtt",
                    "filepath": str(expected_path),
                }
            }
        }
    )

    with patch(
        "noteforge.subtitle.downloader.yt_dlp.YoutubeDL",
        return_value=downloader,
    ) as youtube_dl:
        result = YtDlpSubtitleDownloader(
            cookies_from_browser="chrome"
        ).download(
            source=SOURCE,
            track=TRACK,
            output_dir=tmp_path,
            video_id="BV1test_p1",
            platform="bilibili",
        )

    options = youtube_dl.call_args.args[0]
    assert options["skip_download"] is True
    assert options["writesubtitles"] is True
    assert options["writeautomaticsub"] is True
    assert options["subtitleslangs"] == ["zh-CN"]
    assert options["subtitlesformat"] == "vtt/best"
    assert options["cookiesfrombrowser"] == ("chrome",)
    downloader.extract_info.assert_called_once_with(SOURCE, download=True)
    assert result.path == expected_path
    assert result.language == "zh-CN"
    assert result.extension == "vtt"
    assert result.is_automatic is False


def test_missing_requested_subtitles_raises_not_found(tmp_path: Path) -> None:
    downloader = _downloader_returning({})

    with (
        patch(
            "noteforge.subtitle.downloader.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(SubtitleNotFoundError),
    ):
        YtDlpSubtitleDownloader().download(
            SOURCE,
            TRACK,
            output_dir=tmp_path,
            video_id="BV1test",
            platform="bilibili",
        )


def test_missing_requested_filepath_raises_invalid_response(
    tmp_path: Path,
) -> None:
    downloader = _downloader_returning(
        {"requested_subtitles": {"zh-CN": {"ext": "vtt"}}}
    )

    with (
        patch(
            "noteforge.subtitle.downloader.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(InvalidSubtitleResponseError),
    ):
        YtDlpSubtitleDownloader().download(
            SOURCE,
            TRACK,
            output_dir=tmp_path,
            video_id="BV1test",
            platform="bilibili",
        )


def test_download_error_preserves_exception_chain(tmp_path: Path) -> None:
    downloader = _downloader_returning({})
    downloader.extract_info.side_effect = DownloadError("failed")

    with (
        patch(
            "noteforge.subtitle.downloader.yt_dlp.YoutubeDL",
            return_value=downloader,
        ),
        pytest.raises(SubtitleDownloadError) as raised,
    ):
        YtDlpSubtitleDownloader().download(
            SOURCE,
            TRACK,
            output_dir=tmp_path,
            video_id="BV1test",
            platform="bilibili",
        )

    assert isinstance(raised.value.__cause__, DownloadError)
