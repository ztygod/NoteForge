from noteforge.collector.models import SubtitleTrack
from noteforge.subtitle.selector import SubtitleSelector


def _track(
    language: str,
    extension: str = "vtt",
    *,
    automatic: bool = False,
) -> SubtitleTrack:
    return SubtitleTrack(
        language=language,
        extension=extension,
        url=f"https://example.com/{language}.{extension}",
        is_automatic=automatic,
    )


def test_returns_none_when_no_subtitles_exist() -> None:
    assert SubtitleSelector().select(()) is None


def test_prefers_chinese_manual_subtitle() -> None:
    selected = SubtitleSelector().select(
        (_track("en"), _track("zh-CN"))
    )

    assert selected == _track("zh-CN")


def test_language_priority_beats_manual_status_across_languages() -> None:
    selected = SubtitleSelector().select(
        (_track("en"), _track("zh-CN", automatic=True))
    )

    assert selected == _track("zh-CN", automatic=True)


def test_prefers_manual_subtitle_within_same_language() -> None:
    selected = SubtitleSelector().select(
        (_track("zh", automatic=True), _track("zh"))
    )

    assert selected == _track("zh")


def test_prefers_vtt_when_language_and_type_are_equal() -> None:
    selected = SubtitleSelector().select(
        (_track("zh", "srt"), _track("zh", "vtt"))
    )

    assert selected == _track("zh", "vtt")


def test_falls_back_to_an_available_unlisted_language() -> None:
    selected = SubtitleSelector().select((_track("fr"),))

    assert selected == _track("fr")
