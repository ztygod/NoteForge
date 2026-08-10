"""NoteForge 内部真正理解的知识节点。"""

from dataclasses import dataclass


@dataclass
class Evidence:
    timestamp: float
    text: str


@dataclass
class Concept:
    name: str
    description: str
    evidence: list[Evidence]


@dataclass
class KnowledgeChunk:
    id: str
    video_id: str
    video_title: str

    start_time: float
    end_time: float

    topic: str
    summary: str

    concepts: list[Concept]
