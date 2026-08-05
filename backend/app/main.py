import json
from fastapi import FastAPI, Header, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, engine, Base
from app.models import Project, Trace, Span
from app.schemas import TraceIn, TraceOut

app = FastAPI(title="Lighthouse AI", version="0.1.0")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health():
    return {"status": "ok"}


async def get_project(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(Project.api_key == x_api_key)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return project


@app.post("/v1/traces", status_code=201)
async def ingest_trace(
    payload: TraceIn,
    project: Project = Depends(get_project),
    db: AsyncSession = Depends(get_db),
):
    trace = Trace(
        project_id=project.id,
        trace_id=payload.trace_id,
        name=payload.name,
        status=payload.status,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_ms=payload.duration_ms,
        metadata_json=json.dumps(payload.metadata) if payload.metadata else None,
    )
    db.add(trace)
    await db.flush()

    for s in payload.spans:
        span = Span(
            trace_id=trace.id,
            span_id=s.span_id,
            parent_span_id=s.parent_span_id,
            name=s.name,
            span_type=s.span_type,
            input_json=json.dumps(s.input) if s.input else None,
            output_json=json.dumps(s.output) if s.output else None,
            started_at=s.started_at,
            ended_at=s.ended_at,
            duration_ms=s.duration_ms,
            token_usage_json=json.dumps(s.token_usage) if s.token_usage else None,
            error_text=s.error,
        )
        db.add(span)

    await db.commit()
    return {"id": trace.id, "trace_id": trace.trace_id, "spans_ingested": len(payload.spans)}


@app.get("/v1/traces", response_model=list[TraceOut])
async def list_traces(
    project: Project = Depends(get_project),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trace)
        .where(Trace.project_id == project.id)
        .options(selectinload(Trace.spans))
        .order_by(Trace.created_at.desc())
        .limit(20)
    )
    traces = result.scalars().all()
    return [
        TraceOut(
            id=t.id,
            trace_id=t.trace_id,
            name=t.name,
            status=t.status,
            started_at=t.started_at,
            ended_at=t.ended_at,
            duration_ms=t.duration_ms,
            span_count=len(t.spans),
        )
        for t in traces
    ]