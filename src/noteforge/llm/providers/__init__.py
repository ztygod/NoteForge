"""模型供应商实现及共用 HTTP 传输层。"""

from dataclasses import dataclass
import json
import socket
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from noteforge.exceptions import LLMRequestError, LLMTimeoutError
from noteforge.llm.models import RawJSON


@dataclass(frozen=True, slots=True)
class HTTPResult:
    """供应商适配器使用的最小 HTTP 响应。"""

    data: RawJSON
    headers: Mapping[str, str]


class HTTPTransport(Protocol):
    """可替换的 HTTP 传输协议，便于测试或接入其他网络库。"""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: RawJSON,
        timeout_seconds: float,
    ) -> HTTPResult:
        """发送 JSON POST 请求。"""


class UrllibHTTPTransport:
    """基于 Python 标准库的默认 HTTP 传输。"""

    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: RawJSON,
        timeout_seconds: float,
    ) -> HTTPResult:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
                response_headers = dict(response.headers.items())
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise LLMRequestError(
                f"LLM API 请求失败（HTTP {error.code}）：{detail}",
                status_code=error.code,
            ) from error
        except (TimeoutError, socket.timeout) as error:
            raise LLMTimeoutError("LLM API 请求超时") from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise LLMTimeoutError("LLM API 请求超时") from error
            raise LLMRequestError(f"无法连接 LLM API：{error.reason}") from error
        except OSError as error:
            raise LLMRequestError(f"LLM API 网络请求失败：{error}") from error

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise LLMRequestError("LLM API 返回了无效 JSON") from error
        if not isinstance(decoded, dict):
            raise LLMRequestError("LLM API 响应必须是 JSON 对象")
        return HTTPResult(data=decoded, headers=response_headers)


__all__ = ["HTTPResult", "HTTPTransport", "UrllibHTTPTransport"]
