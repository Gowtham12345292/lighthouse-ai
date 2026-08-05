from pydantic import BaseModel
from datetime import datetime


class SpanIn(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    name: str
    span_type: str = "general"
    input: dict | str | None = None
    output: dict | str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    token_usage: dict | None = None
    error: str | None = None


class TraceIn(BaseModel):
    trace_id: str
    name: str
    status: str = "ok"
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    metadata: dict | None = None
    spans: list[SpanIn] = []


class TraceOut(BaseModel):
    id: str
    trace_id: str
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_ms: float | None
    span_count: int