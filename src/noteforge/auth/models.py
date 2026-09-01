"""认证领域模型；所有公开结果均不得包含 Cookie 明文。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AuthPlatform(StrEnum):
    """NoteForge 支持认证生命周期的平台。"""

    BILIBILI = "bilibili"
    YOUTUBE = "youtube"


class AuthStatus(StrEnum):
    """凭据验证后的稳定状态。"""

    AUTHENTICATED = "authenticated"
    NO_COOKIE = "no_cookie"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    COOKIE_EXPIRED = "cookie_expired"
    IMPORT_FAILED = "import_failed"


@dataclass(frozen=True, slots=True)
class CookieSource:
    """Cookie 来源的非敏感描述。"""

    kind: str
    browser: str | None = None


@dataclass(frozen=True, slots=True)
class AuthResult:
    """可安全展示和记录的认证结果。"""

    platform: AuthPlatform
    status: AuthStatus
    source: str | None = None
    browser: str | None = None
    refreshed_at: datetime | None = None
