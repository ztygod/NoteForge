"""从视频来源到 Markdown 学习笔记的应用流水线。"""

from collections.abc import Callable
from pathlib import Path

from noteforge.collector import bilibili, inspection
from noteforge.collector.models import VideoCollectionResult
from noteforge.document import generate_document
from noteforge.exceptions import NoteForgeError, UnsupportedSourceError
from noteforge.knowledge.chunker import TranscriptChunker
from noteforge.knowledge.extraction import (
    KnowledgeExtractor,
    LLMKnowledgeExtractor,
)
from noteforge.knowledge.preprocessor import ChunkPreprocessor
from noteforge.knowledge.semantic import LLMSemanticAnalyzer, SemanticAnalyzer
from noteforge.llm import LLMClient
from noteforge.renderer import MarkdownRenderer, write_markdown


VideoCollector = Callable[..., VideoCollectionResult]


class NoteGenerationPipeline:
    """组合视频采集、知识提取、文档生成与 Markdown 输出。"""

    def __init__(
        self,
        semantic_analyzer: SemanticAnalyzer,
        knowledge_extractor: KnowledgeExtractor,
        *,
        collector: VideoCollector = bilibili.collect_bilibili_video,
    ) -> None:
        self._semantic_analyzer = semantic_analyzer
        self._knowledge_extractor = knowledge_extractor
        self._collector = collector

    @classmethod
    def from_llm_client(cls, client: LLMClient) -> "NoteGenerationPipeline":
        """使用同一个 LLM Client 创建语义分析与知识提取组件。"""

        return cls(
            LLMSemanticAnalyzer(client),
            LLMKnowledgeExtractor(client),
        )

    async def run(
        self,
        source: str,
        output_path: str | Path,
        *,
        cookies_from_browser: str | None = "chrome",
        subtitle_language: str | None = None,
        subtitle_output_dir: Path = Path(".cache/noteforge/subtitles"),
    ) -> Path:
        """运行完整视频学习笔记流水线并返回生成文件路径。"""

        inspected = inspection.inspect_source(source)
        if (
            inspected.platform is not inspection.InspectionPlatform.BILIBILI
            or inspected.normalized_source is None
        ):
            raise UnsupportedSourceError(f"暂不支持该视频来源：{source}")

        collection = self._collector(
            source=inspected.normalized_source,
            cookies_from_browser=cookies_from_browser,
            subtitle_language=subtitle_language,
            subtitle_output_dir=subtitle_output_dir,
            page_number=inspected.page_number,
        )
        if collection.transcript is None:
            raise NoteForgeError("视频没有可供处理的受支持字幕")

        raw_chunks = TranscriptChunker().chunk(collection.transcript)
        preprocessed_chunks = ChunkPreprocessor().preprocess(raw_chunks)
        semantic_chunks = await self._semantic_analyzer.analyze(
            preprocessed_chunks
        )
        knowledge_points = await self._knowledge_extractor.extract(
            semantic_chunks
        )
        if not knowledge_points:
            raise NoteForgeError("未能从视频字幕中提取出知识点")
        document = generate_document(knowledge_points)
        markdown = MarkdownRenderer().render(document)
        return write_markdown(markdown, output_path)
