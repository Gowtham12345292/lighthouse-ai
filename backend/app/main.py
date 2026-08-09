import json
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, engine, Base
from app.models import Project, Trace, Span, Alert
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
            retrieval_query=s.retrieval.query if s.retrieval else None,
            retrieval_chunks_json=json.dumps(s.retrieval.chunks) if s.retrieval and s.retrieval.chunks else None,
            retrieval_scores_json=json.dumps(s.retrieval.scores) if s.retrieval and s.retrieval.scores else None,
            retrieval_top_k=s.retrieval.top_k if s.retrieval else None,
        )
        db.add(span)

    if payload.status == "error":
        error_spans = [s for s in payload.spans if s.error]
        error_msg = error_spans[0].error if error_spans else "Unknown error"
        alert = Alert(
            project_id=project.id,
            trace_id=trace.id,
            alert_type="trace_error",
            severity="critical",
            message=f"Agent '{payload.name}' failed: {error_msg}",
        )
        db.add(alert)

    await db.commit()
    return {"id": trace.id, "trace_id": trace.trace_id, "spans_ingested": len(payload.spans)}


@app.get("/v1/traces", response_model=list[TraceOut])
async def list_traces(
    project: Project = Depends(get_project),
    db: AsyncSession = Depends(get_db),
    since: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
):
    query = (
        select(Trace)
        .where(Trace.project_id == project.id)
        .options(selectinload(Trace.spans))
        .order_by(Trace.created_at.desc())
        .limit(limit)
    )
    if since:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        query = query.where(Trace.created_at > since_dt)

    result = await db.execute(query)
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


@app.get("/v1/alerts")
async def list_alerts(
    project: Project = Depends(get_project),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert)
        .where(Alert.project_id == project.id)
        .order_by(Alert.created_at.desc())
        .limit(50)
    )
    alerts = result.scalars().all()
    return [
        {
            "id": a.id,
            "trace_id": a.trace_id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "acknowledged": a.acknowledged,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]