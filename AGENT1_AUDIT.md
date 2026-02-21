# Doculord Codebase Audit

## LLM Call Locations (5 call sites)

| File | Line | Method |
|------|------|--------|
| `app/agents/parsing_agent.py` | 176 | `llm.invoke()` in `_cleanup_with_llm` |
| `app/agents/markdown_validation_agent.py` | 383 | `llm.invoke()` in `_validate_with_llm` |
| `app/agents/persistence_agent.py` | 255 | `llm.invoke()` in `_extract_questions_with_llm` |
| `app/tools/classification_tools.py` | 88 | `llm.invoke()` in `classify_question` |
| `app/tools/classification_tools.py` | 191 | `llm.invoke()` in `classify_questions_batch` |

## Silent Exception Swallowing (10 locations)

1. **`extraction_orchestrator.py:19-20`** — `_update_job_status()` catches all exceptions, never re-raises. If DB write fails, job status silently stays stale.
2. **`markdown_validation_agent.py:262-265`** — When LLM returns `None`, defaults to `validation_passed = True`. Should default to `False` to avoid passing bad documents.
3. **`markdown_validation_agent.py:276-281`** — Exception handler sets `validation_passed = True`, masking validation failures.
4. **`parsing_agent.py:97-99`** — LLM failure silently falls back to original markdown with only a warning log. No retry attempted.
5. **`persistence_agent.py:306-308`** — `JSONDecodeError` in `_parse_questions_json` returns `[]` silently, losing all extracted questions.
6. **`storage_service.py:229-230`** — `upload_images_from_zip` catches all exceptions and returns partial `url_mapping`, silently ignoring upload failures.
7. **`json_tools.py:68-73`** — `parse_json_array` returns `[]` on any error without distinguishing parse failures from empty results.
8. **`json_tools.py:129-133`** — `parse_json_object` returns `{}` on any error.
9. **`classification_tools.py:199-201`** — `classify_questions_batch` returns `[]` on error, silently dropping all classification results.
10. **`search_tools.py:71-73, 112-114`** — Search errors return `[]` silently.

## Missing Infrastructure

- **No retry logic** on any LLM call — a single transient API error loses the entire operation
- **No circuit breakers** — repeated failures to external services (LLM, Docling, GCS) are not tracked
- **No request timeouts** on LLM constructors in `llms.py` — calls can hang indefinitely
- **`question_extraction_node`** (`extraction_orchestrator.py:157-163`) is a TODO stub — pass-through only
- **No health checks** beyond basic `{"status": "healthy"}` — no DB/GCS/Docling connectivity checks
- **No tests** — zero test files exist
- **No observability** — no tracing, no metrics, no structured logging
