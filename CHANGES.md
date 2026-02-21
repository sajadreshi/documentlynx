# Doculord Changes

## Observability & Error Handling (Workstream 1)

### New Environment Variables

Add to your `.env` (see `.env.example`):

```
LANGSMITH_API_KEY=          # Optional — enables LangSmith tracing
LANGSMITH_PROJECT=doculord  # LangSmith project name
LANGSMITH_TRACING_V2=false  # Set to true to enable trace v2
```

### New Dependencies

Added to `requirements.txt`:

```
langsmith>=0.1.0
pytest>=7.0
pytest-asyncio>=0.21.0
httpx>=0.24.0
```

Install with:

```bash
pip install -r requirements.txt
```

### New Files

| File | Purpose |
|------|---------|
| `app/observability.py` | Safe `@traceable` decorator (no-op if langsmith not installed) |
| `app/exceptions.py` | Typed exceptions: `DoculordError`, `LLMError`, `LLMResponseParseError`, `DoclingError`, `StorageError`, `EmbeddingError`, `PipelineError`, `CircuitBreakerOpenError` |
| `app/retry.py` | `retry_with_backoff` decorator with exponential backoff |
| `app/circuit_breaker.py` | Circuit breaker pattern for external services |
| `app/question_routes.py` | Document and question CRUD endpoints |
| `app/evaluation/` | Evaluation framework with harness, metrics, and test datasets |
| `run_evals.py` | CLI for running evaluations |
| `tests/` | Test suite |
| `AGENT1_AUDIT.md` | Codebase audit documenting all findings |

### Changes to Existing Files

- **`app/config.py`** — Added `langsmith_api_key`, `langsmith_project`, `langsmith_tracing_v2` settings
- **`app/main.py`** — LangSmith env var setup on startup, CORS middleware, `/health/detailed` endpoint, question router
- **`llms.py`** — Added `request_timeout=60` to all LLM constructors
- **All agents** (`app/agents/*.py`) — Added `@traceable` decorators, retry on LLM calls
- **`app/tools/classification_tools.py`** — Added `@traceable` and retry on LLM calls
- **`app/services/embedding_service.py`** — Added retry on `embed_text`/`embed_texts`
- **`app/services/storage_service.py`** — Per-image retry in `upload_images_from_zip`
- **`app/services/extraction_orchestrator.py`** — `_update_job_status` now retries 3x, logs CRITICAL on final failure

### Error Handling Fixes

- `markdown_validation_agent.py` — LLM failure now defaults to `validation_passed=False` (was `True`)
- `markdown_validation_agent.py` — Exceptions now set `validation_passed=False` (was `True`)
- `persistence_agent.py` — JSON parse errors logged at ERROR level with exc_info

### Running Tests

```bash
pytest tests/ -v
```

### Running Evaluations

```bash
# Mock mode (no LLM calls needed)
python run_evals.py --mode mock --agent all

# Live mode (requires LLM API key)
python run_evals.py --mode live --agent extraction --output eval_results.json
```

### Health Check

```bash
curl http://localhost:8000/health/detailed
```

Returns:

```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "ok"},
    "gcs": {"status": "ok"},
    "docling": {"status": "ok"}
  }
}
```

---

## Document UI & Question Editor (Workstream 2)

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/documently/api/v1/documents` | GET | List documents (paginated) |
| `/documently/api/v1/documents/{id}` | GET | Document detail |
| `/documently/api/v1/documents/{id}/questions` | GET | Question list (paginated) |
| `/documently/api/v1/documents/{id}/questions/{qid}` | GET | Question detail |
| `/documently/api/v1/documents/{id}/questions/{qid}` | PUT | Update question text |

### Frontend

See `frontend/CHANGES.md` for frontend setup instructions.
