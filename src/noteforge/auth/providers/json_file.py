"""解析浏览器扩展导出的 JSON Cookie。"""

import http.cookiejar
import json
from pathlib import Path

from noteforge.auth.errors import CookieImportError
from noteforge.auth.models import AuthPlatform
from noteforge.auth.providers.base import PLATFORM_DOMAINS, filter_cookies, make_cookie


class JsonCookieProvider:
    """支持常见 Cookie 数组及简单 name-value 对象。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, platform: AuthPlatform) -> http.cookiejar.CookieJar:
        """读取 JSON 并严格过滤到目标平台域名。"""

        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CookieImportError("无法读取 Cookie JSON 文件。") from error
        jar = http.cookiejar.CookieJar()
        if isinstance(value, dict):
            domain = PLATFORM_DOMAINS[platform][0]
            for name, cookie_value in value.items():
                if isinstance(name, str) and isinstance(cookie_value, str):
                    jar.set_cookie(make_cookie(name, cookie_value, domain))
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                name, cookie_value, domain = (
                    item.get("name"),
                    item.get("value"),
                    item.get("domain"),
                )
                # 分别收窄类型，避免类型检查器无法从 all() 推断三个字段均为字符串。
                if not isinstance(name, str):
                    continue
                if not isinstance(cookie_value, str):
                    continue
                if not isinstance(domain, str):
                    continue
                raw_path = item.get("path")
                cookie_path = raw_path if isinstance(raw_path, str) else "/"
                expires = item.get("expirationDate", item.get("expires"))
                cookie_expires = (
                    int(expires)
                    if isinstance(expires, (int, float))
                    and not isinstance(expires, bool)
                    and expires > 0
                    else None
                )
                jar.set_cookie(
                    make_cookie(
                        name,
                        cookie_value,
                        domain,
                        path=cookie_path,
                        expires=cookie_expires,
                        secure=bool(item.get("secure", True)),
                    )
                )
        else:
            raise CookieImportError("Cookie JSON 必须是数组或键值对象。")
        result = filter_cookies(jar, platform)
        if not list(result):
            raise CookieImportError("Cookie JSON 中没有目标平台 Cookie。")
        return result
