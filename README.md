# 🔦 Lighthouse AI

**Observability purpose-built for RAG agents.**

Lighthouse doesn't just show you traces — it automatically detects retrieval failures, hallucinations, and groundedness issues, and tells you exactly what to fix.

> 🚧 **Building in public** — 90-day solo founder challenge. Follow along on [LinkedIn](https://linkedin.com).

---

## What It Does

You add 3 lines to your AI agent. Lighthouse captures every trace, span, tool call, and failure — then stores it in a backend you can query.

```python
from lighthouse import Lighthouse

lh = Lighthouse(api_key="your-key", endpoint="http://localhost:8000")

@lh.trace
def my_agent(query):
    with lh.span("retrieve", span_type="retrieval") as s:
        chunks = retriever.search(query)
        s.record(input=query, output=chunks)

    with lh.span("generate", span_type="llm_call", model="claude-sonnet-4-6") as s:
        response = llm.generate(query, chunks)
        s.record(input=query, output=response, tokens_in=100, tokens_out=300)

    return response
```

Run your agent → traces flow to the backend → query them via API.

---

## Architecture

```
┌──────────────┐    POST /v1/traces    ┌──────────────┐      SQL      ┌──────────────┐
│   Your Agent │  ──────────────────►  │   FastAPI    │  ──────────►  │  PostgreSQL  │
│   + SDK      │    JSON + API key     │   Backend    │               │   Database   │
└──────────────┘                       └──────────────┘               └──────────────┘
```

---

## Quick Start

### 1. Clone & start the backend

```bash
git clone https://github.com/Gowtham12345292/lighthouse-ai.git
cd lighthouse-ai
docker-compose up --build
```

This starts PostgreSQL, Redis, and the FastAPI backend on `http://localhost:8000`.

### 2. Seed a project (one-time)

```bash
docker exec -it lighthouse_ai-postgres-1 psql -U lighthouse -d lighthouse \
  -c "INSERT INTO projects (id, name, api_key, created_at) VALUES ('proj-001', 'my-project', 'my-api-key', NOW());"
```

### 3. Run the demo agent

```bash
PYTHONPATH=. python examples/demo_agent.py
```

You'll see the trace printed in your terminal and flushed to the backend.

### 4. Query your traces

```bash
curl -H "X-API-Key: my-api-key" http://localhost:8000/v1/traces
```

---

## SDK Features

| Feature | Status |
|---|---|
| `@lh.trace` decorator | ✅ |
| `lh.span()` context manager | ✅ |
| Auto parent-child nesting via contextvars | ✅ |
| Background flush thread (zero latency) | ✅ |
| Fail-open design (SDK never crashes your app) | ✅ |
| Input/output/token/error capture | ✅ |
| POST traces to backend | ✅ |
| `lh.log_retrieval()` for RAG data | 🔜 |
| RAG metrics (relevance, groundedness) | 🔜 |
| Hallucination detection | 🔜 |
| AI root-cause engine | 🔜 |
| React dashboard | 🔜 |

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Health check |
| `POST` | `/v1/traces` | `X-API-Key` header | Ingest a trace + spans |
| `GET` | `/v1/traces` | `X-API-Key` header | List last 20 traces |

---

## Tech Stack

| Layer | Tool |
|---|---|
| SDK | Python (contextvars, threading, urllib) |
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) + asyncpg |
| Validation | Pydantic 2.x |
| Containers | Docker Compose |

---

## Project Structure

```
lighthouse-ai/
├── lighthouse/          # Python SDK
│   ├── __init__.py
│   └── Sdk.py
├── examples/            # Demo agents
│   └── demo_agent.py
├── backend/             # FastAPI backend
│   ├── app/
│   │   ├── main.py      # Endpoints
│   │   ├── models.py    # DB models
│   │   ├── schemas.py   # Request/response schemas
│   │   └── database.py  # SQLAlchemy setup
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Roadmap

- [x] SDK with tracing + spans
- [x] FastAPI backend with PostgreSQL
- [x] SDK → Backend flush pipeline
- [ ] `lh.log_retrieval()` — capture RAG-specific data
- [ ] Retrieval relevance scoring
- [ ] Groundedness scoring (NLI-based)
- [ ] Hallucination detection
- [ ] Failure pattern clustering
- [ ] AI root-cause engine
- [ ] React dashboard
- [ ] Slack/Discord alerts

---

## Why Lighthouse?

**Langfuse** and **LangSmith** show you traces for any agent. That's useful but generic.

**Lighthouse** is built specifically for RAG agents. It doesn't just show what happened — it tells you *why* your agent hallucinated and *what to fix*.

> "Ragas tells you your pipeline scores 0.72 in a test. Lighthouse tells you it hallucinated 47 times in production last week, shows you which documents caused it, and tells you how to fix it."

---

Built by [Gowtham](https://github.com/Gowtham12345292) in Hyderabad 🇮🇳
