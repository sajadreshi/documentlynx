"""Unit tests for app.agents.persistence_agent.PersistenceAgent."""

from unittest.mock import patch, MagicMock

import pytest


class TestPersistenceAgent:
    """Tests for PersistenceAgent question extraction edge cases."""

    @patch("app.agents.persistence_agent.get_llm")
    @patch("app.agents.persistence_agent.PromptTemplateBuilder")
    @patch("app.agents.persistence_agent.SessionLocal")
    @patch("app.agents.persistence_agent.StorageService")
    def test_process_handles_empty_questions(
        self,
        mock_storage_cls,
        mock_session_cls,
        mock_ptb,
        mock_get_llm,
        sample_agent_state,
    ):
        """When the LLM returns no questions the agent should still succeed."""
        from app.agents.persistence_agent import PersistenceAgent

        # LLM returns empty JSON array
        mock_response = MagicMock()
        mock_response.content = "[]"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        mock_ptb.build_from_file.return_value = "fake prompt"

        # Mock storage service instance
        mock_storage = MagicMock()
        mock_storage.upload_images_from_zip.return_value = {}
        mock_storage_cls.return_value = mock_storage

        # Mock database session -- flush/commit succeed, but no real DB
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        # The agent calls db.add(document) then db.flush() which should set
        # document.id.  We simulate that by making the added Document's id
        # attribute return a fake UUID.
        import uuid

        fake_doc_id = uuid.uuid4()

        def side_effect_add(obj):
            # After add + flush, the Document should have an id
            obj.id = fake_doc_id

        mock_db.add.side_effect = side_effect_add

        state = dict(sample_agent_state)
        state["cleaned_markdown"] = "# Test\n\nNo real questions here."
        state["output_zip_path"] = None

        # Create agent without calling __init__ (avoids settings / GCS import)
        agent = PersistenceAgent.__new__(PersistenceAgent)
        agent.llm_model = "test-model"
        agent.storage_service = mock_storage

        result = agent.process(state)

        # No questions extracted -> question_ids should be empty list
        assert result.get("question_ids") == []
        assert result.get("metadata", {}).get("question_count") == 0

    def test_parse_questions_json_handles_malformed(self):
        """Malformed JSON should return an empty list, not raise."""
        from app.agents.persistence_agent import PersistenceAgent

        agent = PersistenceAgent.__new__(PersistenceAgent)

        # Completely invalid JSON
        assert agent._parse_questions_json("this is not json") == []

        # Valid JSON but not an array
        assert agent._parse_questions_json('{"key": "value"}') == []

        # Truncated JSON
        assert agent._parse_questions_json('[{"q": "test"') == []

        # Empty string
        assert agent._parse_questions_json("") == []

        # Code-fenced but garbled inside
        assert agent._parse_questions_json("```json\nnot valid\n```") == []
