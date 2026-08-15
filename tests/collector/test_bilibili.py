"""验证 Bilibili 平台适配策略。"""

from noteforge.media.platforms import BilibiliAdapter


def test_bilibili_adapter_recognizes_and_normalizes_url() -> None:
    adapter = BilibiliAdapter()
    source = "https://www.bilibili.com/video/BV1CkArz1E4o?p=2"
    assert adapter.supports(source)
    assert adapter.normalize(source) == source


def test_bilibili_adapter_provides_platform_headers() -> None:
    headers = BilibiliAdapter().backend_options()["http_headers"]
    assert headers["Referer"] == "https://www.bilibili.com/"
