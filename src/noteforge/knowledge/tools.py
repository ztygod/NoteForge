"""知识处理阶段使用的固定结构化提交工具。"""

from noteforge.llm import LLMTool


SEMANTIC_ANALYSIS_TOOL = LLMTool(
    name="submit_semantic_analysis",
    description="提交完整的语义切分结果。",
    parameters={
        "type": "object",
        "additionalProperties": False,
        "required": ["semantic_chunks"],
        "properties": {
            "semantic_chunks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "source_indexes", "topic", "summary", "chunk_type", "importance"
                    ],
                    "properties": {
                        "source_indexes": {"type": "array", "items": {"type": "integer"}},
                        "topic": {"type": "string"},
                        "summary": {"type": "string"},
                        "chunk_type": {
                            "type": "string",
                            "enum": ["definition", "explanation", "example", "comparison", "procedure", "conclusion", "transition", "question", "other"],
                        },
                        "importance": {"type": "number"},
                    },
                },
            }
        },
    },
)


KNOWLEDGE_POINTS_TOOL = LLMTool(
    name="submit_knowledge_points",
    description="提交完整的知识点提取结果。",
    parameters={
        "type": "object",
        "additionalProperties": False,
        "required": ["knowledge_points"],
        "properties": {
            "knowledge_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_indexes", "title", "explanation", "point_type", "keywords", "importance"],
                    "properties": {
                        "source_indexes": {"type": "array", "items": {"type": "integer"}},
                        "title": {"type": "string"},
                        "explanation": {"type": "string"},
                        "point_type": {
                            "type": "string",
                            "enum": ["concept", "principle", "procedure", "api", "example", "comparison", "pitfall", "conclusion", "other"],
                        },
                        "keywords": {"type": "array", "items": {"type": "string"}},
                        "importance": {"type": "number"},
                    },
                },
            }
        },
    },
)
