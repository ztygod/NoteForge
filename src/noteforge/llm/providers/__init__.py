"""模型供应商实现及共用异步 HTTP 传输层。"""

from dataclasses import dataclass
from typing import Mapping, Protocol

import httpx

from noteforge.exceptions import LLMRequestError, LLMTimeoutError
from noteforge.llm.models import RawJSON


@dataclass(frozen=True, slots=True)
class HTTPResult:
    data: RawJSON
    headers: Mapping[str, str]


class HTTPTransport(Protocol):
    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: RawJSON,
        timeout_seconds: float,
    ) -> HTTPResult:
        """异步发送 JSON POST 请求。"""

    async def aclose(self) -> None:
        """释放连接池。"""


class HttpxHTTPTransport:
    """复用 ``httpx.AsyncClient`` 连接池的默认传输。"""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: RawJSON,
        timeout_seconds: float,
    ) -> HTTPResult:
        try:
            response = await self._client.post(
                url, headers=headers, json=payload, timeout=timeout_seconds
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("LLM API 请求超时") from error
        except httpx.HTTPStatusError as error:
            raise LLMRequestError(
                f"LLM API 请求失败（HTTP {error.response.status_code}）：{error.response.text}",
                status_code=error.response.status_code,
            ) from error
        except httpx.RequestError as error:
            raise LLMRequestError(f"无法连接 LLM API：{error}") from error
        try:
            decoded = response.json()
        except ValueError as error:
            raise LLMRequestError("LLM API 返回了无效 JSON") from error
        if not isinstance(decoded, dict):
            raise LLMRequestError("LLM API 响应必须是 JSON 对象")
        return HTTPResult(decoded, dict(response.headers))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


__all__ = ["HTTPResult", "HTTPTransport", "HttpxHTTPTransport"]
