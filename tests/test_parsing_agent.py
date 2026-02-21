"""Unit tests for app.agents.parsing_agent.ParsingAgent."""

import os
import tempfile
import zipfile
from unittest.mock import patch, MagicMock

import pytest


class TestParsingAgent:
    """Tests for the ParsingAgent LLM fallback behaviour."""

    @staticmethod
    def _make_zip_with_markdown(content: str) -> str:
        """Create a temporary ZIP file containing a single .md file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp.name, "w") as zf:
            zf.writestr("document.md", content)
        return tmp.name

    @patch("app.agents.parsing_agent.get_llm")
    @patch("app.agents.parsing_agent.PromptTemplateBuilder")
    def test_process_uses_original_on_llm_failure(
        self, mock_ptb, mock_get_llm, sample_agent_state
    ):
        """When the LLM call raises, cleaned_markdown should equal the original markdown."""
        from app.agents.parsing_agent import ParsingAgent

        original_md = "# Original\n\nSome content"
        zip_path = self._make_zip_with_markdown(original_md)

        try:
            # Make LLM raise so the fallback path executes
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = RuntimeError("LLM unreachable")
            mock_get_llm.return_value = mock_llm

            mock_ptb.build_from_file.return_value = "fake prompt"

            state = dict(sample_agent_state)
            state["output_zip_path"] = zip_path

            # Create agent without calling __init__ (avoids settings import)
            agent = ParsingAgent.__new__(ParsingAgent)
            agent.llm_model = "test-model"

            result = agent.process(state)

            # Fallback: cleaned_markdown should be the original content
            assert result["cleaned_markdown"] == original_md
            assert result.get("metadata", {}).get("parsing_fallback") is True
        finally:
            os.unlink(zip_path)

    @patch("app.agents.parsing_agent.get_llm")
    @patch("app.agents.parsing_agent.PromptTemplateBuilder")
    def test_process_uses_llm_output_on_success(
        self, mock_ptb, mock_get_llm, sample_agent_state
    ):
        """When the LLM succeeds, cleaned_markdown should be the LLM output."""
        from app.agents.parsing_agent import ParsingAgent

        original_md = "# Raw\n\nPage 1 footer"
        cleaned_md = "# Cleaned\n\nNice content"
        zip_path = self._make_zip_with_markdown(original_md)

        try:
            mock_response = MagicMock()
            mock_response.content = cleaned_md
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            mock_ptb.build_from_file.return_value = "fake prompt"

            state = dict(sample_agent_state)
            state["output_zip_path"] = zip_path

            agent = ParsingAgent.__new__(ParsingAgent)
            agent.llm_model = "test-model"

            result = agent.process(state)

            assert result["cleaned_markdown"] == cleaned_md
            assert result.get("metadata", {}).get("parsing_fallback") is not True
        finally:
            os.unlink(zip_path)
