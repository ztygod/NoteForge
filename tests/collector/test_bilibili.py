"""验证 Bilibili 平台采集器的应用策略。"""

from noteforge.collector.platforms.bilibili import BilibiliVideoCollector


def test_bilibili_collector_recognizes_and_normalizes_url() -> None:
    collector = BilibiliVideoCollector()
    source = "https://www.bilibili.com/video/BV1CkArz1E4o?p=2"
    assert collector.supports(source)
    assert collector.normalize(source) == source


def test_bilibili_collector_provides_platform_headers() -> None:
    headers = BilibiliVideoCollector().ytdlp_options()["http_headers"]
    assert headers["Referer"] == "https://www.bilibili.com/"
