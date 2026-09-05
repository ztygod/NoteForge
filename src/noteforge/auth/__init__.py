"""NoteForge 统一认证公共 API。"""

from noteforge.auth.errors import (
    AuthError,
    AuthRequiredError,
    CookieExpiredError,
    CookieImportError,
    CookieValidationError,
    CredentialStoreError,
    InteractiveLoginError,
)
from noteforge.auth.manager import AuthManager
from noteforge.auth.models import AuthPlatform, AuthResult, AuthStatus, CookieSource
from noteforge.auth.providers import (
    BrowserCookieProvider,
    JsonCookieProvider,
    PlaywrightCookieProvider,
    RawCookieProvider,
)
from noteforge.auth.store import CookieStore, EncryptedCookieStore

__all__ = [
    "AuthError",
    "AuthManager",
    "AuthPlatform",
    "AuthRequiredError",
    "AuthResult",
    "AuthStatus",
    "BrowserCookieProvider",
    "CookieExpiredError",
    "CookieImportError",
    "CookieSource",
    "CookieStore",
    "CookieValidationError",
    "CredentialStoreError",
    "EncryptedCookieStore",
    "InteractiveLoginError",
    "JsonCookieProvider",
    "PlaywrightCookieProvider",
    "RawCookieProvider",
]
