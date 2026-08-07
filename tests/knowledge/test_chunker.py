import pytest

from noteforge.knowledge.chunker import (
    RawChunk,
    TranscriptChunker,
    segment_to_raw_chunk,
    transcript_to_raw_chunks,
)
from noteforge.media.models import SubtitleSegment


def test_segment_to_raw_chunk_preserves_content_and_timing() -> None:
    segment = SubtitleSegment(
        start=1.25,
        end=3.5,
        text="  保留原始文本\n和换行  ",
    )

    chunk = segment_to_raw_chunk(segment)

    assert chunk == RawChunk(
        start_time=1.25,
        end_time=3.5,
        text="  保留原始文本\n和换行  ",
    )
    assert chunk.duration == pytest.approx(2.25)


def test_transcript_to_raw_chunks_preserves_segment_order() -> None:
    segments = (
        SubtitleSegment(4.0, 5.0, "后出现"),
        SubtitleSegment(1.0, 2.0, "先输入"),
    )

    chunks = transcript_to_raw_chunks(segments)

    assert [chunk.text for chunk in chunks] == ["后出现", "先输入"]
    assert isinstance(chunks, tuple)


@pytest.mark.parametrize(
    ("start_time", "end_time", "text"),
    [
        (-1.0, 1.0, "文本"),
        (2.0, 1.0, "文本"),
        (float("nan"), 1.0, "文本"),
        (0.0, float("inf"), "文本"),
        (0.0, 1.0, "  \n"),
    ],
)
def test_raw_chunk_rejects_invalid_data(
    start_time: float,
    end_time: float,
    text: str,
) -> None:
    with pytest.raises(ValueError):
        RawChunk(start_time=start_time, end_time=end_time, text=text)


def test_chunker_rejects_wrong_input_types() -> None:
    chunker = TranscriptChunker()

    with pytest.raises(TypeError):
        chunker.chunk("not a transcript")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        chunker.chunk_segment("not a segment")  # type: ignore[arg-type]
