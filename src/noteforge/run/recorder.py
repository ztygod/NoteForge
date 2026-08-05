"""Run manifest、事件与阶段产物记录器。"""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import re
import secrets
import socket
import traceback
from typing import Any
from urllib.parse import urlsplit

from noteforge.core.events import PipelineEvent, PipelineStatus
from noteforge.run.serialization import json_value
from noteforge.run.writer import append_jsonl, atomic_write_json, atomic_write_text


# run 目录名只允许跨平台安全的 ASCII 字母、数字及少量分隔符，避免来源 ID
# 中的空格、斜杠或控制字符改变目录层级。
_SAFE_ID = re.compile(r"[^0-9A-Za-z._-]+")

# 对可能出现在第三方异常信息和 traceback 中的常见认证信息进行脱敏。
# 前两项保留 header 名称，方便诊断认证问题；第三项覆盖常见的 sk- Key。
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(x-api-key[=:]\s*)[^\s,]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _now() -> datetime:
    """返回带时区的 UTC 时间，避免运行记录依赖本机时区。"""

    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    """生成带毫秒精度的 RFC 3339 UTC 时间戳。"""

    instant = value or _now()
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _run_id(source_id: str | None, created_at: datetime) -> str:
    """使用 UTC 时间、清理后的来源 ID 和随机后缀生成唯一 run ID。"""

    # 未知来源使用固定占位符；来源 ID 最长保留 64 个字符，避免目录名过长。
    safe_source = _SAFE_ID.sub("_", source_id or "unknown").strip("._")
    safe_source = (safe_source or "unknown")[:64]
    stamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    # 4 字节随机数生成 8 位十六进制后缀，用于避免同秒并发运行冲突。
    return f"{stamp}-{safe_source}-{secrets.token_hex(4)}"


def _redact(text: str) -> str:
    """清除日志或异常文本中可能包含的认证凭据。"""

    result = text
    for pattern in _SECRET_PATTERNS:
        # 带捕获组的规则保留 header 前缀，只替换实际凭据内容。
        replacement = r"\1[REDACTED]" if pattern.groups else "[REDACTED]"
        result = pattern.sub(replacement, result)
    return result


def _package_version() -> str:
    """读取已安装版本；源码环境没有包元数据时使用 unknown。"""

    try:
        return version("noteforge-cli")
    except PackageNotFoundError:
        return "unknown"


def _endpoint_origin(base_url: str) -> str:
    """只保留端点的 scheme、hostname 和 port，移除敏感或可变部分。"""

    parsed = urlsplit(base_url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    # urlsplit.hostname 不包含账号密码；IPv6 地址需要恢复方括号才能形成合法 URL。
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        # 非法端口不应阻止 run manifest 落盘，忽略它并保留可识别的主机信息。
        port = None
    # 有意丢弃 userinfo、path、query 和 fragment，避免记录凭据及无关配置细节。
    return f"{parsed.scheme}://{host}{f':{port}' if port is not None else ''}"


class RunRecorder:
    """维护一次 generate 的可恢复运行事实。"""

    def __init__(self, run_dir: Path, manifest: dict[str, Any]) -> None:
        self.run_dir = run_dir
        self.manifest_path = run_dir / "manifest.json"
        self.events_path = run_dir / "events.jsonl"
        self.artifacts_dir = run_dir / "artifacts"
        self.logs_dir = run_dir / "logs"
        self.manifest = manifest
        self._sequence = 0

    @property
    def run_id(self) -> str:
        return str(self.manifest["run_id"])

    @classmethod
    def start(
        cls,
        *,
        root: Path,
        source: str,
        source_id: str | None,
        platform: str,
        normalized_source: str | None,
        page_number: int | None,
        output_path: Path,
    ) -> "RunRecorder":
        created_at = _now()
        for _ in range(5):
            run_id = _run_id(source_id, created_at)
            run_dir = root / run_id
            try:
                run_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            break
        else:
            raise RuntimeError("无法创建唯一的 NoteForge run 目录")

        (run_dir / "artifacts").mkdir()
        (run_dir / "logs").mkdir()
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "running",
            "created_at": _timestamp(created_at),
            "completed_at": None,
            "noteforge": {"version": _package_version()},
            "runtime": {"pid": os.getpid(), "hostname": socket.gethostname()},
            "invocation": {
                "command": "generate",
                "working_directory": str(Path.cwd()),
            },
            "source": {
                "original": source,
                "normalized": normalized_source,
                "platform": platform,
                "id": source_id,
                "page": page_number,
                "title": None,
                "duration_seconds": None,
            },
            "configuration": {"output_path": str(output_path)},
            "summary": {
                "duration_seconds": None,
                "llm_calls": 0,
                "validation_retries": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
            "stages": {},
            "artifacts": {},
            "error": None,
        }
        recorder = cls(run_dir, manifest)
        recorder._write_manifest()
        recorder._event("run.started")
        return recorder

    def configure(
        self,
        *,
        api_format: str,
        model: str,
        base_url: str,
        llm_concurrency: int,
        subtitle_language: str | None,
        cookie_strategy: str | None,
    ) -> None:
        self.manifest["configuration"].update({
            "api_format": api_format,
            "model": model,
            "base_url_origin": _endpoint_origin(base_url),
            "llm_concurrency": llm_concurrency,
            "subtitle_language": subtitle_language,
            "cookie_strategy": cookie_strategy,
        })
        self._write_manifest()

    def update_source(self, collection: Any) -> None:
        metadata = collection.metadata
        self.manifest["source"].update({
            "title": metadata.title,
            "duration_seconds": metadata.duration,
        })
        self._write_manifest()

    def handle_event(self, event: PipelineEvent) -> None:
        timestamp = _timestamp()
        stages = self.manifest["stages"]
        existing_stage = stages.get(event.stage)
        event_type = {
            PipelineStatus.RUNNING: (
                "stage.started"
                if existing_stage is None
                or existing_stage["started_at"] is None
                else "stage.progress"
            ),
            PipelineStatus.SUCCESS: "stage.completed",
            PipelineStatus.ERROR: "stage.failed",
            PipelineStatus.PENDING: "stage.pending",
        }[event.status]
        recorded_status = (
            "failed" if event.status is PipelineStatus.ERROR else event.status.value
        )
        self._event(
            event_type,
            timestamp=timestamp,
            stage=event.stage,
            status=recorded_status,
            message=event.message,
            progress=event.progress,
            metrics=json_value(dict(event.metrics)),
            duration_seconds=event.duration,
        )

        stage = stages.setdefault(event.stage, {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "progress": None,
            "metrics": {},
            "error": None,
        })
        if event.status is PipelineStatus.RUNNING and stage["started_at"] is None:
            stage["started_at"] = timestamp
        stage["status"] = recorded_status
        stage["progress"] = event.progress
        stage["metrics"] = json_value(dict(event.metrics))
        if event.status in {PipelineStatus.SUCCESS, PipelineStatus.ERROR}:
            stage["completed_at"] = timestamp
            stage["duration_seconds"] = event.duration
        if event.status is PipelineStatus.ERROR:
            stage["error"] = _redact(event.message)
        self._update_summary(event)
        self._write_manifest()

    def save_artifact(self, name: str, value: Any) -> Path:
        created_at = _timestamp()
        wrapper = {
            "schema_version": 1,
            "artifact_type": name,
            "run_id": self.run_id,
            "created_at": created_at,
            "data": json_value(value),
        }
        path = self.artifacts_dir / f"{name}.json"
        atomic_write_json(path, wrapper)
        content = path.read_bytes()
        item_count = len(value) if isinstance(value, (list, tuple)) else None
        self.manifest["artifacts"][name] = {
            "path": str(path.relative_to(self.run_dir)),
            "media_type": "application/json",
            "schema_version": 1,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "item_count": item_count,
            "created_at": created_at,
        }
        self._event("artifact.created", artifact=name)
        self._write_manifest()
        return path

    def save_note(self, markdown: str) -> Path:
        path = self.artifacts_dir / "note.md"
        atomic_write_text(path, markdown)
        content = path.read_bytes()
        self.manifest["artifacts"]["note"] = {
            "path": str(path.relative_to(self.run_dir)),
            "media_type": "text/markdown",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "created_at": _timestamp(),
        }
        self._event("artifact.created", artifact="note")
        self._write_manifest()
        return path

    def complete(self, output_path: Path) -> None:
        self.manifest["status"] = "success"
        self.manifest["completed_at"] = _timestamp()
        self.manifest["configuration"]["output_path"] = str(output_path)
        self._finish_duration()
        self._event("run.completed", output_path=str(output_path))
        self._write_manifest()

    def fail(self, error: BaseException) -> None:
        error_record = self._error_record(error)
        atomic_write_json(self.logs_dir / "error.json", error_record)
        self.manifest["status"] = "failed"
        self.manifest["completed_at"] = _timestamp()
        self.manifest["error"] = {
            "path": "logs/error.json",
            "type": type(error).__name__,
            "message": _redact(str(error)),
        }
        self._finish_duration()
        self._event("run.failed", error=self.manifest["error"])
        self._write_manifest()

    def cancel(self) -> None:
        self.manifest["status"] = "cancelled"
        self.manifest["completed_at"] = _timestamp()
        self._finish_duration()
        self._event("run.cancelled")
        self._write_manifest()

    def _update_summary(self, event: PipelineEvent) -> None:
        metrics = event.metrics
        summary = self.manifest["summary"]
        for source, target in (
            ("llm_calls", "llm_calls"),
            ("retries", "validation_retries"),
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
        ):
            value = metrics.get(source)
            if isinstance(value, int):
                summary[target] = max(summary[target], value)

    def _finish_duration(self) -> None:
        created = datetime.fromisoformat(
            str(self.manifest["created_at"]).replace("Z", "+00:00")
        )
        self.manifest["summary"]["duration_seconds"] = round(
            (_now() - created).total_seconds(), 3
        )

    def _error_record(self, error: BaseException) -> dict[str, Any]:
        causes = []
        current: BaseException | None = error
        while current is not None:
            causes.append({
                "type": type(current).__name__,
                "message": _redact(str(current)),
            })
            current = current.__cause__
        return {
            "schema_version": 1,
            "timestamp": _timestamp(),
            "exception_type": type(error).__name__,
            "message": _redact(str(error)),
            "cause_chain": causes,
            "traceback": _redact("".join(traceback.format_exception(error))),
        }

    def _event(self, event_type: str, **fields: Any) -> None:
        self._sequence += 1
        append_jsonl(self.events_path, {
            "schema_version": 1,
            "sequence": self._sequence,
            "timestamp": fields.pop("timestamp", _timestamp()),
            "type": event_type,
            "run_id": self.run_id,
            **json_value(fields),
        })

    def _write_manifest(self) -> None:
        atomic_write_json(self.manifest_path, json_value(self.manifest))
