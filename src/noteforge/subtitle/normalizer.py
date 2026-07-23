"""结构化字幕清洗。"""

from noteforge.subtitle.models import Transcript, TranscriptSegment


class TranscriptNormalizer:
    """清理空白并删除完全重复的连续字幕。"""

    def normalize(self, transcript: Transcript) -> Transcript:
        normalized_segments: list[TranscriptSegment] = []

        for segment in transcript.segments:
            text = " ".join(segment.text.split())
            if not text:
                continue
            if normalized_segments and normalized_segments[-1].text == text:
                continue
            normalized_segments.append(
                TranscriptSegment(
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    text=text,
                )
            )

        return Transcript(
            language=transcript.language,
            segments=tuple(normalized_segments),
            source=transcript.source,
        )
