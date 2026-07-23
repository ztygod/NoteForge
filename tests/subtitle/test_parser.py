from pathlib import Path

import pytest

from noteforge.exceptions import SubtitleParseError
from noteforge.subtitle.models import SubtitleFile
from noteforge.subtitle.normalizer import TranscriptNormalizer
from noteforge.subtitle.parser import VttSubtitleParser


def _subtitle_file(tmp_path: Path, content: str) -> SubtitleFile:
    path = tmp_path / "subtitle.vtt"
    path.write_text(content, encoding="utf-8")
    return SubtitleFile(
        path=path,
        language="zh-CN",
        extension="vtt",
        is_automatic=False,
    )


def test_parses_vtt_with_both_timestamp_formats(tmp_path: Path) -> None:
    subtitle = _subtitle_file(
        tmp_path,
        """WEBVTT

1
00:01.250 --> 00:03.500
大家好

2
01:02:03.004 --> 01:02:05.500
课程开始
""",
    )

    transcript = VttSubtitleParser().parse(subtitle)

    assert transcript.language == "zh-CN"
    assert transcript.source == "manual_subtitle"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].start_seconds == 1.25
    assert transcript.segments[0].end_seconds == 3.5
    assert transcript.segments[0].text == "大家好"
    assert transcript.segments[1].start_seconds == 3723.004


def test_parses_multiline_text_and_removes_vtt_tags(tmp_path: Path) -> None:
    subtitle = _subtitle_file(
        tmp_path,
        """WEBVTT

cue-1
00:00:00.000 --> 00:00:03.200 align:start
<v 老师>大家好</v>
欢迎来到 <b>今天</b> 的课程
""",
    )

    transcript = VttSubtitleParser().parse(subtitle)

    assert transcript.segments[0].text == "大家好\n欢迎来到 今天 的课程"


def test_normalizer_merges_lines_and_removes_consecutive_duplicates(
    tmp_path: Path,
) -> None:
    subtitle = _subtitle_file(
        tmp_path,
        """WEBVTT

00:00.000 --> 00:01.000
  大家好
 欢迎

00:01.000 --> 00:02.000
大家好 欢迎

00:02.000 --> 00:03.000
下一节
""",
    )

    transcript = TranscriptNormalizer().normalize(
        VttSubtitleParser().parse(subtitle)
    )

    assert [segment.text for segment in transcript.segments] == [
        "大家好 欢迎",
        "下一节",
    ]
    assert transcript.segments[0].start_seconds == 0
    assert transcript.segments[0].end_seconds == 1


@pytest.mark.parametrize(
    "timing",
    [
        "invalid --> 00:01.000",
        "00:61.000 --> 00:62.000",
        "00:02 --> 00:03.000",
    ],
)
def test_invalid_timestamp_raises_parse_error(
    tmp_path: Path,
    timing: str,
) -> None:
    subtitle = _subtitle_file(
        tmp_path,
        f"WEBVTT\n\n{timing}\n正文\n",
    )

    with pytest.raises(SubtitleParseError):
        VttSubtitleParser().parse(subtitle)
