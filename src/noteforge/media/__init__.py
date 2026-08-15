"""NoteForge 唯一公共媒体 API。"""

from noteforge.media.assets import AssetReference, MediaAsset
from noteforge.media.config import (
    ExtractorConfig,
    PlatformConfig,
    load_extractor_config,
)
from noteforge.media.cookies import CookieLease, CookieService, CredentialInfo
from noteforge.media.models import (
    AudioFormat,
    AudioRequest,
    AuthRequest,
    Browser,
    CookiePersistence,
    MediaFormats,
    MediaType,
    Metadata,
    Platform,
    Playlist,
    PlaylistEntry,
    Subtitle,
    SubtitleRequest,
    SubtitleSegment,
    VideoFormat,
    VideoMetadata,
    VideoPlatform,
    VideoRequest,
    VideoResource,
)
from noteforge.media.protocols import AudioTranscriber
from noteforge.media.service import MediaService, collect_video, discover_video
from noteforge.media.source import (
    InspectedSource,
    InspectionPlatform,
    InspectionResult,
    inspect_source,
)
from noteforge.media.subtitle import SubtitleParser

__all__ = [
    "AssetReference",
    "AudioTranscriber",
    "AudioFormat",
    "AudioRequest",
    "AuthRequest",
    "Browser",
    "CookieLease",
    "CookiePersistence",
    "CookieService",
    "CredentialInfo",
    "ExtractorConfig",
    "MediaAsset",
    "MediaFormats",
    "MediaService",
    "MediaType",
    "Metadata",
    "Platform",
    "PlatformConfig",
    "Playlist",
    "PlaylistEntry",
    "Subtitle",
    "SubtitleParser",
    "SubtitleRequest",
    "SubtitleSegment",
    "VideoFormat",
    "VideoMetadata",
    "VideoPlatform",
    "VideoRequest",
    "VideoResource",
    "InspectedSource",
    "InspectionPlatform",
    "InspectionResult",
    "collect_video",
    "discover_video",
    "inspect_source",
    "load_extractor_config",
]
