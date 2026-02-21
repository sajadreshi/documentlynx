"""Tests for the /health and /health/detailed endpoints in app.main."""

import pytest
from unittest.mock import patch, MagicMock

import httpx


@pytest.mark.asyncio
async def test_health_returns_status():
    """GET /health should return 200 with status 'healthy'."""
    with patch("app.main.Base"), \
         patch("app.main.engine"), \
         patch("app.main.SessionLocal"):

        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_detailed_structure():
    """GET /health/detailed should return JSON with 'status' and 'checks' keys.

    Because the database, GCS, and Docling are not available in tests the
    overall status will be 'degraded', but the response structure must be
    correct.
    """
    mock_session = MagicMock()
    # db.execute will raise so the database check reports as error
    mock_session.execute.side_effect = RuntimeError("no db")

    # Mock the StorageService that the endpoint imports at call time
    mock_storage_cls = MagicMock()
    mock_storage_instance = MagicMock()
    mock_storage_instance.bucket.exists.return_value = True
    mock_storage_cls.return_value = mock_storage_instance

    with patch("app.main.Base"), \
         patch("app.main.engine"), \
         patch("app.main.SessionLocal", return_value=mock_session), \
         patch("app.services.storage_service.StorageService", mock_storage_cls):

        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/health/detailed")

    assert response.status_code == 200
    data = response.json()

    # Structure checks
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)

    # With mocked-out dependencies we expect either healthy or degraded
    # (database is mocked to fail, GCS is mocked to succeed, docling is unreachable)
    assert data["status"] in ("healthy", "degraded")

    # The checks dict should contain entries for our monitored services
    assert "database" in data["checks"]
    assert "gcs" in data["checks"]
    assert "docling" in data["checks"]
