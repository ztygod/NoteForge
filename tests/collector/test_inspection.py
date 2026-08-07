import pytest

from noteforge.collector.source import InspectionPlatform, inspect_source


def test_inspect_standard_bilibili_url() -> None:
    source = "https://www.bilibili.com/video/BV1CkArz1E4o"

    result = inspect_source(source)

    assert result.original_source == source
    assert result.platform is InspectionPlatform.BILIBILI
    assert result.source_id == "BV1CkArz1E4o"
    assert result.page_number == 1
    assert result.normalized_source == source


def test_inspect_bilibili_url_with_escaped_query_characters() -> None:
    source = (
        "https://www.bilibili.com/video/BV1CkArz1E4o"
        r"\?vd_source\=source\&p\=2\&spm_id_from\=333.788"
    )

    result = inspect_source(source)

    assert result.platform is InspectionPlatform.BILIBILI
    assert result.source_id == "BV1CkArz1E4o"
    assert result.page_number == 2
    assert result.normalized_source == (
        "https://www.bilibili.com/video/BV1CkArz1E4o?p=2"
    )


def test_inspect_preserves_original_source() -> None:
    source = "  https://www.bilibili.com/video/BV1CkArz1E4o\\?p\\=2  "

    result = inspect_source(source)

    assert result.original_source == source
    assert result.platform is InspectionPlatform.BILIBILI


@pytest.mark.parametrize("page", ["abc", "0", "-3"])
def test_inspect_defaults_invalid_page_number_to_one(page: str) -> None:
    source = f"https://www.bilibili.com/video/BV1CkArz1E4o?p={page}"

    result = inspect_source(source)

    assert result.platform is InspectionPlatform.BILIBILI
    assert result.page_number == 1
    assert result.normalized_source == (
        "https://www.bilibili.com/video/BV1CkArz1E4o"
    )


@pytest.mark.parametrize(
    "source",
    [
        "https://www.bilibili.com/video/BVabc",
        "https://bilibili.com.evil.example/video/BV1CkArz1E4o",
        "https://example.com/video/BV1CkArz1E4o",
        "www.bilibili.com/video/BV1CkArz1E4o",
    ],
)
def test_inspect_rejects_invalid_or_unsupported_source(source: str) -> None:
    result = inspect_source(source)

    assert result.platform is InspectionPlatform.UNKNOWN
    assert result.source_id is None
    assert result.normalized_source is None


@pytest.mark.parametrize(
    "source",
    [
        "https://www.youtube.com/watch?v=M7lc1UVf-VE",
        "https://youtube.com/watch?v=M7lc1UVf-VE&t=30s",
        "https://m.youtube.com/watch?v=M7lc1UVf-VE",
        "https://music.youtube.com/watch?v=M7lc1UVf-VE&list=example",
        "https://youtu.be/M7lc1UVf-VE?si=example",
        "https://www.youtube.com/embed/M7lc1UVf-VE?autoplay=1",
        "https://www.youtube-nocookie.com/embed/M7lc1UVf-VE",
        "https://www.youtube.com/shorts/M7lc1UVf-VE",
        "https://www.youtube.com/live/M7lc1UVf-VE?feature=share",
        "https://www.youtube.com/v/M7lc1UVf-VE?version=3",
    ],
)
def test_inspect_youtube_video_url(source: str) -> None:
    result = inspect_source(source)

    assert result.original_source == source
    assert result.platform is InspectionPlatform.YOUTUBE
    assert result.source_id == "M7lc1UVf-VE"
    assert result.normalized_source == (
        "https://www.youtube.com/watch?v=M7lc1UVf-VE"
    )
    assert result.page_number is None
    assert result.requires_remote_resolution is False


def test_inspect_youtube_url_with_escaped_query_characters() -> None:
    source = r"https://www.youtube.com/watch\?v\=M7lc1UVf-VE\&t\=30s"

    result = inspect_source(source)

    assert result.platform is InspectionPlatform.YOUTUBE
    assert result.source_id == "M7lc1UVf-VE"


@pytest.mark.parametrize(
    "source",
    [
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=too-short",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/@youtubecreators",
        "https://youtube.com.evil.example/watch?v=M7lc1UVf-VE",
        "https://youtu.be/M7lc1UVf-VE-extra",
        "https://www.youtube-nocookie.com/watch?v=M7lc1UVf-VE",
    ],
)
def test_inspect_rejects_non_video_or_invalid_youtube_url(source: str) -> None:
    result = inspect_source(source)

    assert result.platform is InspectionPlatform.UNKNOWN
    assert result.source_id is None
    assert result.normalized_source is None
