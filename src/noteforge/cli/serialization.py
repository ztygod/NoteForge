"""将业务对象转换为 CLI 调试输出所需的字典。"""

from dataclasses import asdict

from noteforge.collector.models import VideoCollectionResult


_SUBTITLE_PREVIEW_LIMIT = 5


def subtitle_debug_output(
    collection: VideoCollectionResult,
) -> dict[str, object]:
    """构造字幕轨道、选择结果和字幕片段预览。"""

    selected = collection.selected_subtitle
    transcript = collection.transcript
    return {
        "available_track_count": len(collection.subtitle_tracks),
        "subtitle_tracks": [asdict(track) for track in collection.subtitle_tracks],
        "selected_subtitle": asdict(selected) if selected else None,
        "transcript": (
            {
                "language": transcript.language,
                "source": transcript.source,
                "segment_count": len(transcript.segments),
                "preview_limit": _SUBTITLE_PREVIEW_LIMIT,
                "preview": [
                    asdict(segment)
                    for segment in transcript.segments[:_SUBTITLE_PREVIEW_LIMIT]
                ],
            }
            if transcript
            else None
        ),
    }

