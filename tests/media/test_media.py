from pathlib import Path
from unittest.mock import patch

from noteforge.collector.platforms.bilibili import BilibiliVideoCollector
from noteforge.collector.factory import create_video_collector
from noteforge.collector.platforms.youtube import YouTubeCollector
from noteforge.media.cache import MediaCache
from noteforge.media.config import ExtractorConfig, PlatformConfig, load_extractor_config
from noteforge.media.models import Subtitle, SubtitleSegment, VideoMetadata, VideoPlatform
from noteforge.media.subtitle import SubtitleParser
from noteforge.media.ytdlp import YTDLPClient


def test_collector_factory_recognizes_bilibili_and_youtube() -> None:
    assert isinstance(create_video_collector("https://www.bilibili.com/video/BV1CkArz1E4o"), BilibiliVideoCollector)
    assert isinstance(create_video_collector("https://youtu.be/M7lc1UVf-VE"), YouTubeCollector)


def test_cookie_file_has_priority_over_browser_cookie(tmp_path: Path) -> None:
    (tmp_path / "cookies.txt").touch()
    options = YTDLPClient(PlatformConfig(tmp_path / "cookies.txt", "chrome", None)).options()
    assert options["cookiefile"] == str(tmp_path / "cookies.txt")
    assert "cookiesfrombrowser" not in options


def test_missing_cookie_file_bootstraps_from_browser_once(tmp_path: Path) -> None:
    cookie_file = tmp_path / "private" / "cookies.txt"
    options = YTDLPClient(PlatformConfig(cookie_file, "chrome", None)).options()
    assert options["cookiefile"] == str(cookie_file)
    assert options["cookiesfrombrowser"] == ("chrome",)
    assert cookie_file.parent.is_dir()


def test_metadata_discovery_allows_missing_media_formats() -> None:
    options = YTDLPClient().options()
    assert options["skip_download"] is True
    assert options["ignore_no_formats_error"] is True


def test_media_download_requires_a_matching_format(tmp_path: Path) -> None:
    client = YTDLPClient()
    with patch.object(client, "extract_info", return_value={}) as extract_info:
        client.download_media("https://example.com/video", target_dir=tmp_path, audio_only=True)
    options = extract_info.call_args.kwargs["options"]
    assert options["skip_download"] is False
    assert options["ignore_no_formats_error"] is False


def test_load_yaml_style_extractor_config(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "extractor:\n  cache_path: .cache/media\n  youtube:\n"
        "    cookie_file: .secrets/youtube.txt\n"
        "    cookies_from_browser: chrome\n",
        encoding="utf-8",
    )
    config = load_extractor_config(path)
    assert config.cache_path == Path(".cache/media")
    assert config.for_platform("youtube").cookie_file == Path(".secrets/youtube.txt")


def test_subtitle_parser_supports_ass_and_json3() -> None:
    ass = "[Events]\nDialogue: 0,0:00:01.00,0:00:02.50,Default,,0,0,0,,{\\b1}你好\\N世界"
    assert SubtitleParser().parse(Subtitle("zh", "ass", content=ass)) == (
        SubtitleSegment(1.0, 2.5, "你好 世界"),
    )
    json3 = '{"events":[{"tStartMs":1000,"dDurationMs":500,"segs":[{"utf8":"Hello"}]}]}'
    assert SubtitleParser().parse(Subtitle("en", "json3", content=json3)) == (
        SubtitleSegment(1.0, 1.5, "Hello"),
    )


def test_subtitle_parser_supports_vtt_and_srt() -> None:
    vtt = "WEBVTT\n\n00:01.250 --> 00:03.500\n<b>大家好</b>\n"
    assert SubtitleParser().parse(Subtitle("zh", "vtt", content=vtt)) == (
        SubtitleSegment(1.25, 3.5, "大家好"),
    )
    srt = "1\n00:00:01,250 --> 00:00:03,500\nHello\n"
    assert SubtitleParser().parse(Subtitle("en", "srt", content=srt)) == (
        SubtitleSegment(1.25, 3.5, "Hello"),
    )


def test_subtitle_parser_normalizes_and_removes_duplicates() -> None:
    content = (
        "WEBVTT\n\n00:00.000 --> 00:01.000\n大家好\n 欢迎\n\n"
        "00:01.000 --> 00:02.000\n大家好 欢迎\n"
    )
    assert SubtitleParser().parse(Subtitle("zh", "vtt", content=content)) == (
        SubtitleSegment(0, 1, "大家好 欢迎"),
    )


def test_platform_collector_maps_metadata(tmp_path: Path) -> None:
    collector = YouTubeCollector(ExtractorConfig(cache_path=tmp_path))
    info = {"id": "M7lc1UVf-VE", "title": "Demo", "webpage_url": "https://www.youtube.com/watch?v=M7lc1UVf-VE"}
    with patch.object(collector.client, "extract_info", return_value=info) as request:
        resource = collector.discover(info["webpage_url"])
    assert resource.metadata.id == "M7lc1UVf-VE"
    request.assert_called_once()


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = MediaCache(tmp_path)
    metadata = VideoMetadata("id", "title", None, 10, None, VideoPlatform.YOUTUBE, "url")
    segments = (SubtitleSegment(0, 1, "text"),)
    cache.save_metadata(metadata)
    cache.save_transcript(metadata, segments)
    assert cache.load_metadata(VideoPlatform.YOUTUBE, "id") == metadata
    assert cache.load_transcript(VideoPlatform.YOUTUBE, "id") == segments
