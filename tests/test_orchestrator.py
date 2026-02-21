"""Unit tests for _update_job_status in app.services.extraction_orchestrator."""

import logging
from unittest.mock import patch, MagicMock


class TestUpdateJobStatus:
    """Tests for the _update_job_status helper with retry logic."""

    @patch("app.services.extraction_orchestrator.SessionLocal")
    @patch("app.services.extraction_orchestrator.JobService")
    def test_update_job_status_succeeds(self, mock_job_service, mock_session_cls):
        """On first success the function should call update_status and close the session."""
        from app.services.extraction_orchestrator import _update_job_status

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        _update_job_status("job-1", "parsing")

        mock_job_service.update_status.assert_called_once_with(
            mock_db, "job-1", "parsing", None
        )
        mock_db.close.assert_called_once()

    @patch("app.services.extraction_orchestrator.SessionLocal")
    @patch("app.services.extraction_orchestrator.JobService")
    def test_update_job_status_retries_on_failure(self, mock_job_service, mock_session_cls):
        """When update_status fails on the first attempt it should retry and succeed."""
        from app.services.extraction_orchestrator import _update_job_status

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        # First call raises, second call succeeds
        mock_job_service.update_status.side_effect = [
            RuntimeError("db down"),
            None,
        ]

        _update_job_status("job-2", "ingesting")

        assert mock_job_service.update_status.call_count == 2
        # Session should be closed after each attempt (success or failure)
        assert mock_db.close.call_count == 2

    @patch("app.services.extraction_orchestrator.SessionLocal")
    @patch("app.services.extraction_orchestrator.JobService")
    def test_update_job_status_logs_critical_on_exhaustion(
        self, mock_job_service, mock_session_cls, caplog
    ):
        """After all 3 attempts fail, a CRITICAL log should be emitted."""
        from app.services.extraction_orchestrator import _update_job_status

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        mock_job_service.update_status.side_effect = RuntimeError("always fails")

        with caplog.at_level(logging.CRITICAL, logger="app.services.extraction_orchestrator"):
            _update_job_status("job-3", "failed", "boom")

        assert mock_job_service.update_status.call_count == 3

        # Verify CRITICAL message was logged
        critical_messages = [r for r in caplog.records if r.levelno == logging.CRITICAL]
        assert len(critical_messages) >= 1
        assert "job-3" in critical_messages[0].message
