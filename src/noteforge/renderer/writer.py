"""Markdown 文件输出工具。"""

from pathlib import Path


def write_markdown(content: str, output_path: str | Path) -> Path:
    """创建所需目录，并使用 UTF-8 将 Markdown 写入目标文件。"""

    if not isinstance(content, str):
        raise TypeError("content 必须是字符串")
    if not isinstance(output_path, (str, Path)):
        raise TypeError("output_path 必须是字符串或 Path")

    path = Path(output_path)
    if not path.name:
        raise ValueError("output_path 必须指向文件")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
