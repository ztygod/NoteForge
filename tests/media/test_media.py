import http.cookiejar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from noteforge.auth import AuthRequiredError
from noteforge.media.assets import AssetReference, MediaAsset
from noteforge.media.config import (
    ExtractorConfig,
    load_extractor_config,
)
from noteforge.media.cookies.policy import policy_for
from noteforge.media.cookies.service import CookieService
from noteforge.media.models import (
    AudioRequest,
    MediaType,
    Subtitle,
    SubtitleSegment,
    VideoMetadata,
    VideoPlatform,
)
from noteforge.media.platforms import BilibiliAdapter, YouTubeAdapter
from noteforge.media.repository import MediaRepository
from noteforge.media.service import MediaService
from noteforge.media.subtitle import SubtitleParser
from noteforge.media.ytdlp import YTDLPClient


class AnonymousAuthManager:
    """媒体测试专用认证替身，确保不会读取本机浏览器。"""

    def get_cookie(self, platform):
        del platform
        raise AuthRequiredError("测试使用匿名请求。")

    def refresh(self, platform, *, browser=None):
        del platform, browser
        raise AuthRequiredError("测试禁止刷新真实浏览器 Cookie。")


def test_platform_adapters_recognize_bilibili_and_youtube() -> None:
    assert BilibiliAdapter().supports("https://www.bilibili.com/video/BV1CkArz1E4o")
    assert YouTubeAdapter().supports("https://youtu.be/M7lc1UVf-VE")


def test_ytdlp_options_cannot_read_browser_cookies_directly() -> None:
    options = YTDLPClient().options()
    assert "cookiefile" not in options
    assert "cookiesfrombrowser" not in options


def test_cookie_service_filters_non_platform_domains() -> None:
    source = http.cookiejar.CookieJar()
    for domain in (".youtube.com", ".example.com"):
        source.set_cookie(
            http.cookiejar.Cookie(
                0,
                "session",
                "secret",
                None,
                False,
                domain,
                True,
                True,
                "/",
                True,
                False,
                None,
                False,
                None,
                None,
                {},
                False,
            )
        )
    filtered = CookieService._filter(source, policy_for(VideoPlatform.YOUTUBE))
    assert [cookie.domain for cookie in filtered] == [".youtube.com"]


def test_metadata_discovery_allows_missing_media_formats() -> None:
    options = YTDLPClient().options()
    assert options["skip_download"] is True
    assert options["ignore_no_formats_error"] is True


def test_media_download_requires_a_matching_format(tmp_path: Path) -> None:
    client = YTDLPClient()
    with patch.object(client, "extract_info", return_value={}) as extract_info:
        client.download_media(
            "https://example.com/video", target_dir=tmp_path, audio_only=True
        )
    options = extract_info.call_args.kwargs["options"]
    assert options["skip_download"] is False
    assert options["ignore_no_formats_error"] is False


def test_load_yaml_style_extractor_config(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "extractor:\n  cache_path: .cache/media\n  youtube:\n"
        "    proxy: http://127.0.0.1:7890\n",
        encoding="utf-8",
    )
    config = load_extractor_config(path)
    assert config.cache_path == Path(".cache/media")
    assert config.for_platform("youtube").proxy == "http://127.0.0.1:7890"


def test_subtitle_parser_supports_ass_and_json3() -> None:
    ass = (
        "[Events]\nDialogue: 0,0:00:01.00,0:00:02.50,Default,,0,0,0,,{\\b1}你好\\N世界"
    )
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
    info = {
        "id": "M7lc1UVf-VE",
        "title": "Demo",
        "webpage_url": "https://www.youtube.com/watch?v=M7lc1UVf-VE",
    }

    class Worker:
        def execute(self, payload):
            assert payload["operation"] == "extract"
            return info

        def close(self):
            pass

    service = MediaService(
        ExtractorConfig(cache_path=tmp_path),
        auth_manager=AnonymousAuthManager(),
        worker=Worker(),
    )
    resource = service.discover(info["webpage_url"])
    assert resource.metadata.id == "M7lc1UVf-VE"


def test_media_asset_removes_lease_on_close(tmp_path: Path) -> None:
    root = tmp_path / "lease"
    root.mkdir()
    path = root / "audio.mp3"
    path.write_bytes(b"audio")
    metadata = VideoMetadata("id", "title", None, 1, None, "youtube", "url")
    reference = AssetReference(
        "asset", MediaType.AUDIO, datetime.now(UTC) + timedelta(minutes=1), metadata
    )
    with MediaAsset(reference, path, root) as asset:
        assert asset.path.read_bytes() == b"audio"
    assert not root.exists()


def test_media_service_download_returns_expiring_asset(tmp_path: Path) -> None:
    info = {
        "id": "M7lc1UVf-VE",
        "title": "Demo",
        "webpage_url": "https://www.youtube.com/watch?v=M7lc1UVf-VE",
    }

    class Worker:
        def execute(self, payload):
            if payload["operation"] == "extract":
                return info
            path = Path(payload["target_dir"]) / "M7lc1UVf-VE.mp3"
            path.write_bytes(b"audio")
            return {"requested_downloads": [{"filepath": str(path)}]}

        def close(self):
            pass

    config = ExtractorConfig(cache_path=tmp_path / "cache", runtime_path=tmp_path)
    service = MediaService(
        config,
        auth_manager=AnonymousAuthManager(),
        worker=Worker(),
    )
    asset = service.download_audio(info["webpage_url"], AudioRequest(codec="mp3"))
    lease_root = asset.path.parent
    assert asset.path.read_bytes() == b"audio"
    asset.close()
    assert not lease_root.exists()


def test_repository_round_trip(tmp_path: Path) -> None:
    repository = MediaRepository(tmp_path)
    metadata = VideoMetadata(
        "id", "title", None, 10, None, VideoPlatform.YOUTUBE, "url"
    )
    segments = (SubtitleSegment(0, 1, "text"),)
    repository.save_metadata(metadata)
    repository.save_transcript(metadata, segments)
    assert repository.load_metadata(VideoPlatform.YOUTUBE, "id") == metadata
    assert repository.load_transcript(VideoPlatform.YOUTUBE, "id") == segments
