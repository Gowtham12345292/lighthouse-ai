"""
Lighthouse SDK core.

Design principles:
1. FAIL-OPEN — any SDK error is swallowed, never raised into the user's app
2. ZERO LATENCY — spans queue in memory, a background thread flushes async
3. AUTOMATIC NESTING — contextvars track the span stack, so parent_span_id is set automatically
"""

from __future__ import annotations

import atexit
import functools
import json
import logging
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Callable, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger("lighthouse")

_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar(
    "_current_trace", default=None
)


@dataclass
class SpanData:
    """Raw span data that gets queued for export."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: Optional[str] = None
    span_type: str = "generic"
    name: str = ""
    model: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict:
        """Serialize for export, dropping None values to keep payloads small."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


class TraceContext:
    """Holds the span stack for one trace (one agent run)."""

    def __init__(self, trace_id: str, name: str):
        self.trace_id = trace_id
        self.name = name
        self.span_stack: list[SpanData] = []
        self.completed_spans: list[SpanData] = []
        self.status: str = "running"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at: Optional[str] = None
        self.error: Optional[str] = None

    @property
    def current_span(self) -> Optional[SpanData]:
        return self.span_stack[-1] if self.span_stack else None

    def push_span(self, span: SpanData) -> None:
        parent = self.current_span
        span.parent_span_id = parent.id if parent else None
        span.trace_id = self.trace_id
        self.span_stack.append(span)

    def pop_span(self) -> Optional[SpanData]:
        if self.span_stack:
            span = self.span_stack.pop()
            self.completed_spans.append(span)
            return span
        return None


class Span:
    """
    User-facing span handle. Used as a context manager:

        with lh.span("llm_call", model="claude-sonnet-4-6") as s:
            response = client.messages.create(...)
            s.record(input=messages, output=response.content, tokens=100)
    """

    def __init__(self, data: SpanData, trace_ctx: TraceContext):
        self._data = data
        self._trace_ctx = trace_ctx
        self._start_time: float = 0

    def record(
        self,
        input: Any = None,
        output: Any = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        tokens: int | None = None,
        error: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Record data into the current span. Call this before exiting the context."""
        if input is not None:
            self._data.input = _safe_serialize(input)
        if output is not None:
            self._data.output = _safe_serialize(output)
        if tokens_in is not None:
            self._data.tokens_in = tokens_in
        if tokens_out is not None:
            self._data.tokens_out = tokens_out
        if tokens is not None and tokens_in is None and tokens_out is None:
            self._data.tokens_out = tokens
        if error is not None:
            self._data.error = error

    def __enter__(self) -> "Span":
        self._start_time = time.monotonic()
        self._data.started_at = datetime.now(timezone.utc).isoformat()
        self._trace_ctx.push_span(self._data)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        elapsed = time.monotonic() - self._start_time
        self._data.latency_ms = int(elapsed * 1000)
        self._data.ended_at = datetime.now(timezone.utc).isoformat()
        if exc_val and not self._data.error:
            self._data.error = f"{exc_type.__name__}: {exc_val}"
        self._trace_ctx.pop_span()
        return False


class Lighthouse:
    """
    Main SDK client.

        lh = Lighthouse(api_key="lh_test_key", endpoint="http://localhost:8000")

        @lh.trace
        def my_agent(query): ...
    """

    def __init__(
        self,
        api_key: str = "lh_test_key",
        endpoint: str = "http://localhost:8000",
        flush_interval: float = 2.0,
        batch_size: int = 50,
        debug: bool = False,
    ):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._queue: Queue[dict] = Queue()
        self._debug = debug

        if debug:
            logging.basicConfig(level=logging.DEBUG)

        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="lighthouse-flush"
        )
        self._flush_thread.start()

        atexit.register(self._flush_remaining)

    # ── Public API ──────────────────────────────────────────────────

    def trace(self, func: Callable | None = None, *, name: str | None = None):
        if func is None:
            return lambda f: self.trace(f, name=name)

        trace_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            trace_id = uuid.uuid4().hex[:16]
            ctx = TraceContext(trace_id=trace_id, name=trace_name)
            token = _current_trace.set(ctx)

            try:
                result = func(*args, **kwargs)
                ctx.status = "success"
                return result
            except Exception as e:
                ctx.status = "error"
                ctx.error = f"{type(e).__name__}: {e}"
                raise
            finally:
                ctx.ended_at = datetime.now(timezone.utc).isoformat()
                _current_trace.reset(token)
                self._export_trace(ctx)

        return wrapper

    @contextmanager
    def span(
        self,
        name: str,
        span_type: str = "generic",
        model: str | None = None,
    ):
        ctx = _current_trace.get()
        if ctx is None:
            logger.debug("lh.span() called outside @lh.trace — skipping")
            yield Span(SpanData(), TraceContext("", ""))
            return

        span_data = SpanData(name=name, span_type=span_type, model=model)
        span_handle = Span(span_data, ctx)

        try:
            with span_handle as s:
                yield s
        except Exception:
            raise

    # ── Internal: export & flush ────────────────────────────────────

    def _export_trace(self, ctx: TraceContext) -> None:
        """Queue a completed trace for background export. Never raises."""
        try:
            api_spans = []
            for s in ctx.completed_spans:
                api_span = {
                    "span_id": s.id,
                    "name": s.name,
                    "span_type": s.span_type,
                    "started_at": s.started_at,
                    "ended_at": s.ended_at,
                    "duration_ms": s.latency_ms,
                }
                if s.parent_span_id:
                    api_span["parent_span_id"] = s.parent_span_id
                if s.input is not None:
                    api_span["input"] = s.input
                if s.output is not None:
                    api_span["output"] = s.output
                if s.error:
                    api_span["error"] = s.error
                if s.tokens_in is not None or s.tokens_out is not None:
                    api_span["token_usage"] = {
                        "tokens_in": s.tokens_in,
                        "tokens_out": s.tokens_out,
                    }
                api_spans.append(api_span)

            trace_data = {
                "trace_id": ctx.trace_id,
                "name": ctx.name,
                "status": ctx.status,
                "started_at": ctx.started_at,
                "ended_at": ctx.ended_at,
                "spans": api_spans,
            }

            if self._debug:
                logger.debug(
                    "Trace completed: %s (%s) — %d spans",
                    ctx.name,
                    ctx.status,
                    len(ctx.completed_spans),
                )
                display_data = {
                    "trace_id": ctx.trace_id,
                    "name": ctx.name,
                    "status": ctx.status,
                    "error": ctx.error,
                    "started_at": ctx.started_at,
                    "ended_at": ctx.ended_at,
                    "spans": [s.to_dict() for s in ctx.completed_spans],
                }
                print(_format_trace(display_data))

            self._queue.put(trace_data)
        except Exception:
            logger.debug("Failed to export trace", exc_info=True)

    def _flush_loop(self) -> None:
        """Background thread: flush queued traces every N seconds."""
        while True:
            time.sleep(self._flush_interval)
            self._flush_batch()

    def _flush_batch(self) -> None:
        """Drain the queue and send to the backend."""
        batch: list[dict] = []
        while len(batch) < self._batch_size:
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except Empty:
                break

        if not batch:
            return

        for trace_data in batch:
            try:
                payload = json.dumps(trace_data).encode("utf-8")
                req = Request(
                    f"{self.endpoint}/v1/traces",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                    },
                    method="POST",
                )
                with urlopen(req, timeout=5) as resp:
                    if self._debug:
                        logger.debug("Flushed trace %s — %s", trace_data["trace_id"], resp.status)
            except Exception:
                logger.debug("Failed to flush trace", exc_info=True)

    def _flush_remaining(self) -> None:
        """Called at process exit via atexit."""
        self._flush_batch()


# ── Utilities ───────────────────────────────────────────────────────


def _safe_serialize(obj: Any) -> Any:
    """Convert objects to JSON-safe representations without crashing."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _format_trace(trace_data: dict) -> str:
    """Pretty-print a trace for debug/console output."""
    lines = [
        "",
        "═" * 60,
        f"  TRACE: {trace_data['name']}",
        f"  ID:    {trace_data['trace_id']}",
        f"  Status: {trace_data['status']}",
        "─" * 60,
    ]

    if trace_data.get("error"):
        lines.append(f"  Error: {trace_data['error']}")
        lines.append("─" * 60)

    spans = trace_data.get("spans", [])
    for i, span in enumerate(spans):
        indent = "  "
        prefix = f"  {'├' if i < len(spans) - 1 else '└'}─"

        status_icon = "✓" if not span.get("error") else "✗"
        line = f"{prefix} [{status_icon}] {span['name']}"

        if span.get("model"):
            line += f"  (model: {span['model']})"
        if span.get("latency_ms") is not None:
            line += f"  [{span['latency_ms']}ms]"
        if span.get("tokens_out") is not None:
            line += f"  [{span['tokens_out']} tokens]"

        lines.append(line)

        if span.get("error"):
            lines.append(f"{indent}     Error: {span['error']}")

        if span.get("input"):
            inp = str(span["input"])[:80]
            lines.append(f"{indent}     Input: {inp}")
        if span.get("output"):
            out = str(span["output"])[:80]
            lines.append(f"{indent}     Output: {out}")

    lines.append("═" * 60)
    lines.append("")
    return "\n".join(lines)