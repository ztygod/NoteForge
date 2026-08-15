"""隔离执行 yt-dlp 的本地媒体 Worker。"""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from noteforge.media.ytdlp import YTDLPClient


def _execute(payload: dict[str, Any]) -> Mapping[str, Any]:
    """子进程入口；只接收可序列化命令，不接触应用领域对象。"""

    client = YTDLPClient(extra_options=payload.get("platform_options"))
    operation = payload["operation"]
    cookie = Path(payload["cookie_file"]) if payload.get("cookie_file") else None
    if operation == "extract":
        return client.extract_info(
            payload["source"],
            options=payload.get("options"),
            cookie_file=cookie,
        )
    if operation == "download_media":
        return client.download_media(
            payload["source"],
            target_dir=Path(payload["target_dir"]),
            audio_only=payload["audio_only"],
            format_id=payload.get("format_id"),
            codec=payload.get("codec", "mp3"),
            cookie_file=cookie,
        )
    if operation == "download_subtitle":
        return client.download_subtitle(
            payload["source"],
            language=payload["language"],
            subtitle_format=payload["subtitle_format"],
            target_dir=Path(payload["target_dir"]),
            cookie_file=cookie,
        )
    raise ValueError(f"未知媒体 Worker 操作：{operation}")


class ProcessMediaWorker:
    """懒启动的 yt-dlp 进程池，隔离下载器故障和资源占用。"""

    def __init__(self, max_workers: int = 2) -> None:
        self._max_workers = max_workers
        self._executor: ProcessPoolExecutor | None = None
        self._closed = False

    def execute(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        """同步等待一次子进程任务；异常会原样传播到服务层。"""

        if self._closed:
            raise RuntimeError("Media Worker 已关闭。")
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        return self._executor.submit(_execute, payload).result()

    def close(self) -> None:
        """幂等关闭进程池，并取消尚未开始的任务。"""

        if not self._closed:
            self._closed = True
            if self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> ProcessMediaWorker:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class InProcessMediaWorker:
    """仅用于测试或受控嵌入环境。生产默认不使用。"""

    def execute(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        """在当前进程执行同一命令协议。"""

        return _execute(payload)

    def close(self) -> None:
        pass
