"""字幕选择、下载和解析过程中可安全展示的异常。"""

from noteforge.exceptions.base import NoteForgeError


class SubtitleError(NoteForgeError):
    """字幕处理失败的基础异常。"""


class SubtitleNotFoundError(SubtitleError):
    """没有发现或下载到符合条件的字幕。"""


class SubtitleDownloadError(SubtitleError):
    """字幕远程下载失败。"""


class InvalidSubtitleResponseError(SubtitleError):
    """字幕下载结果缺少预期字段。"""


class SubtitleParseError(SubtitleError):
    """字幕文件内容无法解析。"""
