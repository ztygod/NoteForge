import pytest

from noteforge.collector.inspection import InspectionPlatform, inspect_source


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
