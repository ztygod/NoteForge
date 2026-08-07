"""将业务对象转换为 CLI 调试输出所需的字典。"""

from dataclasses import asdict

from noteforge.media.models import VideoResource


_SUBTITLE_PREVIEW_LIMIT = 5


def subtitle_debug_output(
    collection: VideoResource,
) -> dict[str, object]:
    """构造字幕轨道、选择结果和字幕片段预览。"""

    selected = collection.subtitles[0] if collection.transcript and collection.subtitles else None
    transcript = collection.transcript
    return {
        "available_track_count": len(collection.subtitles),
        "subtitle_tracks": [asdict(track) for track in collection.subtitles],
        "selected_subtitle": asdict(selected) if selected else None,
        "transcript": (
            {
                "language": selected.language if selected else "unknown",
                "source": collection.transcript_source,
                "segment_count": len(transcript),
                "preview_limit": _SUBTITLE_PREVIEW_LIMIT,
                "preview": [
                    asdict(segment)
                    for segment in transcript[:_SUBTITLE_PREVIEW_LIMIT]
                ],
            }
            if transcript
            else None
        ),
    }
