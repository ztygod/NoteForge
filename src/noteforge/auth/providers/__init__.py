"""NoteForge 内置 Cookie Provider。"""

from noteforge.auth.providers.base import CookieProvider
from noteforge.auth.providers.browser import BrowserCookieProvider
from noteforge.auth.providers.json_file import JsonCookieProvider
from noteforge.auth.providers.playwright import PlaywrightCookieProvider
from noteforge.auth.providers.raw import RawCookieProvider

__all__ = [
    "BrowserCookieProvider",
    "CookieProvider",
    "JsonCookieProvider",
    "PlaywrightCookieProvider",
    "RawCookieProvider",
]
