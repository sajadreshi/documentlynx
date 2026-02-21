"""Shared pytest fixtures for Doculord tests.

All fixtures mock external dependencies (database, GCS, LLM) so that tests
can run without a live database or cloud services.

The ``_bootstrap_app_config`` autouse session fixture ensures that
``app.config.Settings`` can be instantiated and ``app.database`` can be
imported even when no ``.env`` file or real Google credentials are present.
"""

import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Session-scoped: set up env vars, fake credentials, and mock the DB engine
# BEFORE any ``app.*`` module is imported.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _bootstrap_app_config(tmp_path_factory):
    """Create a fake credential file, set dummy env vars, and patch the
    SQLAlchemy engine/sessionmaker so all ``app.*`` imports succeed without
    external services.
    """
    # -- 1. Fake Google credentials file -----------------------------------
    creds_dir = tmp_path_factory.mktemp("creds")
    creds_file = creds_dir / "fake-credentials.json"
    creds_file.write_text(json.dumps({"type": "service_account", "project_id": "test"}))

    # -- 2. Temp dir for Docling -------------------------------------------
    temp_dir = tmp_path_factory.mktemp("docling_temp")

    # -- 3. Env vars -------------------------------------------------------
    env_overrides = {
        "GOOGLE_CLOUD_PROJECT_ID": "test-project",
        "GOOGLE_CLOUD_STORAGE_BUCKET": "test-bucket",
        "GOOGLE_APPLICATION_CREDENTIALS": str(creds_file),
        "DATABASE_URL": "postgresql://testuser:testpass@localhost:5432/testdb",
        "DOCLING_API_URL": "http://localhost:9999/v1/convert/source",
        "DOCLING_FILE_API_URL": "http://localhost:9999/v1/convert/file",
        "DOCLING_TIMEOUT_SECONDS": "30",
        "DOCLING_TEMP_DIR": str(temp_dir),
    }

    saved = {}
    for key, value in env_overrides.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = value

    # -- 4. Evict cached app modules so they re-import with new env --------
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("app."):
            del sys.modules[mod_name]

    # -- 5. Patch the real sqlalchemy functions BEFORE app.database imports -
    #    ``app.database`` calls ``create_engine(...)`` at module level, so
    #    we must patch the source (``sqlalchemy.create_engine``) before
    #    the import happens.
    mock_engine = MagicMock()
    mock_session_factory = MagicMock()

    with patch("sqlalchemy.create_engine", return_value=mock_engine), \
         patch("sqlalchemy.orm.sessionmaker", return_value=mock_session_factory):
        yield

    # -- 6. Restore env vars -----------------------------------------------
    for key, orig in saved.items():
        if orig is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = orig


# ---------------------------------------------------------------------------
# mock_db -- a mocked SQLAlchemy session
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db():
    """Return a MagicMock that behaves like a SQLAlchemy Session.

    Common methods (add, commit, flush, refresh, close, rollback, query,
    execute) are available as regular MagicMocks so callers can assert on
    them or configure return values.
    """
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.flush = MagicMock()
    session.refresh = MagicMock()
    session.close = MagicMock()
    session.rollback = MagicMock()
    session.query = MagicMock()
    session.execute = MagicMock()
    return session


# ---------------------------------------------------------------------------
# mock_llm -- a mocked LangChain-style LLM
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm():
    """Return a MagicMock LLM whose ``invoke()`` response is configurable.

    By default ``invoke()`` returns an object with ``.content`` set to
    ``"mock llm response"``.  Override via::

        mock_llm.invoke.return_value.content = "custom response"
    """
    llm = MagicMock()
    response = MagicMock()
    response.content = "mock llm response"
    llm.invoke.return_value = response
    return llm


# ---------------------------------------------------------------------------
# mock_gcs -- a mocked StorageService
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_gcs():
    """Return a MagicMock that stands in for ``app.services.storage_service.StorageService``.

    Pre-configured methods:
    - ``upload_document`` returns a fake signed URL.
    - ``upload_image_public`` returns a fake public URL.
    - ``upload_images_from_zip`` returns an empty mapping.
    - ``bucket.exists()`` returns True.
    """
    svc = MagicMock()
    svc.upload_document.return_value = "https://storage.example.com/fake-signed-url"
    svc.upload_image_public.return_value = "https://example.com/images/fake.png"
    svc.upload_images_from_zip.return_value = {}
    svc.bucket = MagicMock()
    svc.bucket.exists.return_value = True
    return svc


# ---------------------------------------------------------------------------
# sample_agent_state -- a valid AgentState dict
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_agent_state():
    """Return a valid ``AgentState`` dictionary with all required fields populated."""
    return {
        "job_id": "test-job-123",
        "user_id": "test-user-456",
        "document_url": "https://storage.example.com/documents/test.pdf",
        "document_filename": "test.pdf",
        "file_type": "pdf",
        "raw_content": None,
        "parsed_markdown": None,
        "cleaned_markdown": None,
        "extracted_questions": None,
        "validated_markdown": None,
        "vector_ids": None,
        "status": "pending",
        "error_message": None,
        "metadata": {},
        "validation_attempts": 0,
        "validation_passed": False,
        "docling_options": None,
        "use_file_conversion": False,
        "output_zip_path": None,
        "source_file_path": None,
        "validation_feedback": None,
        "document_id": None,
        "question_ids": None,
        "public_markdown": None,
    }


# ---------------------------------------------------------------------------
# app_client -- httpx AsyncClient wired to the FastAPI app
# ---------------------------------------------------------------------------
@pytest.fixture
async def app_client():
    """Yield an ``httpx.AsyncClient`` connected to the FastAPI application.

    All heavy startup side-effects (database init, LangSmith config) are
    patched out so the test runs without external services.
    """
    import httpx

    with patch("app.main.Base") as mock_base, \
         patch("app.main.engine"), \
         patch("app.main.SessionLocal") as mock_sl:

        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
