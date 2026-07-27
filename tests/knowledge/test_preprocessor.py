import pytest

from noteforge.knowledge.chunker import RawChunk
from noteforge.knowledge.preprocessor import (
    ChunkPreprocessor,
    PreprocessedChunk,
    normalize_text,
    preprocess_raw_chunks,
)


def test_merges_close_chunks_in_time_order() -> None:
    first = RawChunk(0, 2, "今天我们来讲")
    second = RawChunk(2.1, 5, "操作系统")

    results = preprocess_raw_chunks([first, second])

    assert results == (
        PreprocessedChunk(
            start_time=0,
            end_time=5,
            text="今天我们来讲\n操作系统",
            source_chunks=(first, second),
        ),
    )


def test_does_not_merge_at_or_beyond_threshold() -> None:
    chunks = [
        RawChunk(0, 1, "第一段"),
        RawChunk(1.5, 2, "第二段"),
        RawChunk(3, 4, "第三段"),
    ]

    results = preprocess_raw_chunks(chunks, gap_threshold_seconds=0.5)

    assert [result.text for result in results] == [
        "第一段",
        "第二段",
        "第三段",
    ]


def test_normalizes_whitespace_and_only_known_noise_markers() -> None:
    text = "  然后\n\n[音乐]   就是\t内容 [掌声] [噪音]  "

    assert normalize_text(text) == "然后 就是 内容"


def test_noise_only_group_is_ignored() -> None:
    noise = RawChunk(0, 1, "[音乐]\n [掌声]")
    content = RawChunk(2, 3, "有效内容")

    results = preprocess_raw_chunks([noise, content])

    assert len(results) == 1
    assert results[0].text == "有效内容"
    assert results[0].source_chunks == (content,)


def test_noise_chunk_inside_continuous_group_keeps_time_mapping() -> None:
    first = RawChunk(0, 1, "开始")
    noise = RawChunk(1.1, 2, "[音乐]")
    last = RawChunk(2.1, 3, "继续")

    result = preprocess_raw_chunks([first, noise, last])[0]

    assert result.text == "开始\n继续"
    assert result.start_time == 0
    assert result.end_time == 3
    assert result.source_chunks == (first, noise, last)


def test_overlapping_chunks_use_latest_end_time() -> None:
    chunks = [
        RawChunk(0, 10, "长片段"),
        RawChunk(2, 3, "内嵌片段"),
        RawChunk(10.1, 11, "后续片段"),
    ]

    result = preprocess_raw_chunks(chunks)[0]

    assert result.end_time == 11
    assert result.text == "长片段\n内嵌片段\n后续片段"


def test_rejects_out_of_order_input() -> None:
    first = RawChunk(0, 1, "第一段")
    second = RawChunk(2, 3, "第二段")

    with pytest.raises(ValueError, match="start_time"):
        preprocess_raw_chunks([second, first])


def test_starts_new_chunk_when_max_duration_would_be_exceeded() -> None:
    chunks = [
        RawChunk(0, 4, "第一段"),
        RawChunk(4.1, 8, "第二段"),
        RawChunk(8.1, 12, "第三段"),
    ]

    results = preprocess_raw_chunks(
        chunks,
        max_duration_seconds=10,
    )

    assert [result.text for result in results] == [
        "第一段\n第二段",
        "第三段",
    ]
    assert results[0].source_chunks == tuple(chunks[:2])
    assert results[1].source_chunks == (chunks[2],)


def test_starts_new_chunk_when_max_characters_would_be_exceeded() -> None:
    chunks = [
        RawChunk(0, 1, "1234"),
        RawChunk(1.1, 2, "5678"),
        RawChunk(2.1, 3, "90"),
    ]

    results = preprocess_raw_chunks(chunks, max_characters=9)

    assert [result.text for result in results] == ["1234\n5678", "90"]


def test_single_chunk_is_not_split_when_it_exceeds_limit() -> None:
    chunk = RawChunk(0, 20, "无法安全拆分的单个字幕块")

    result = preprocess_raw_chunks(
        [chunk],
        max_duration_seconds=10,
        max_characters=5,
    )[0]

    assert result.source_chunks == (chunk,)
    assert result.text == chunk.text


@pytest.mark.parametrize("threshold", [-0.1, float("inf"), float("nan")])
def test_rejects_invalid_threshold(threshold: float) -> None:
    with pytest.raises(ValueError):
        ChunkPreprocessor(threshold)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("max_duration_seconds", 0),
        ("max_duration_seconds", float("inf")),
        ("max_characters", 0),
        ("max_characters", 1.5),
        ("max_characters", True),
    ],
)
def test_rejects_invalid_merge_limit(keyword: str, value: object) -> None:
    with pytest.raises(ValueError):
        ChunkPreprocessor(**{keyword: value})  # type: ignore[arg-type]


def test_empty_input_returns_tuple() -> None:
    assert preprocess_raw_chunks([]) == ()
