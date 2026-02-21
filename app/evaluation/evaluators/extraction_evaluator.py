"""Extraction evaluator -- tests the question extraction pipeline.

Runs each test case through the extraction logic (either using a mock LLM
response or the real LLM) and compares the result against the expected
ground truth.
"""

import json
import logging
import time
from typing import Optional

from app.evaluation.metrics import score_format_correctness, score_completeness

logger = logging.getLogger(__name__)


class ExtractionEvaluator:
    """Evaluator for the question-extraction stage of the Doculord pipeline.

    In *mock* mode the evaluator uses the pre-recorded ``mock_llm_response``
    from the test case, skipping any real LLM call.  In *live* mode it
    instantiates a ``PersistenceAgent`` (which owns the extraction prompt)
    and calls the LLM for real.
    """

    # Minimum scores required to consider a test case "passed"
    FORMAT_THRESHOLD = 0.8
    COMPLETENESS_THRESHOLD = 1.0

    def evaluate(self, test_case: dict, mode: str = "mock") -> dict:
        """Run extraction evaluation on a single test case.

        Args:
            test_case: A dict loaded from baseline_questions.json containing
                ``id``, ``input_markdown``, ``expected``, and optionally
                ``mock_llm_response``.
            mode: ``"mock"`` to use saved responses, ``"live"`` to call the
                real LLM.

        Returns:
            A result dict with keys:
              - test_id: str
              - agent: "extraction"
              - mode: str
              - passed: bool
              - scores: dict of individual metric scores
              - extracted_questions: list[dict] -- the questions that were
                produced (for debugging)
              - duration_ms: float
              - error: optional error message
        """
        test_id = test_case.get("id", "unknown")
        start = time.perf_counter()

        result = {
            "test_id": test_id,
            "agent": "extraction",
            "mode": mode,
            "passed": False,
            "scores": {},
            "extracted_questions": [],
            "duration_ms": 0.0,
            "error": None,
        }

        try:
            if mode == "mock":
                questions = self._extract_mock(test_case)
            elif mode == "live":
                questions = self._extract_live(test_case)
            else:
                raise ValueError(f"Unknown mode: {mode}")

            result["extracted_questions"] = questions

            # --- Scoring ---
            expected = test_case.get("expected", {})
            expected_count = expected.get("question_count", 0)

            # Completeness: did we get the right number of questions?
            completeness = score_completeness(questions, expected_count)
            result["scores"]["completeness"] = completeness

            # Format correctness: average over all extracted questions
            if questions:
                format_scores = [score_format_correctness(q) for q in questions]
                avg_format = round(sum(format_scores) / len(format_scores), 4)
            else:
                avg_format = 0.0
            result["scores"]["format_correctness"] = avg_format

            # Question-type accuracy: compare extracted types to expected types
            type_accuracy = self._score_type_accuracy(questions, expected)
            result["scores"]["type_accuracy"] = type_accuracy

            # Pass / fail
            result["passed"] = (
                completeness >= self.COMPLETENESS_THRESHOLD
                and avg_format >= self.FORMAT_THRESHOLD
            )

        except Exception as exc:
            logger.error("Extraction evaluation failed for %s: %s", test_id, exc, exc_info=True)
            result["error"] = str(exc)

        result["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_mock(self, test_case: dict) -> list[dict]:
        """Parse the mock LLM response stored in the test case."""
        mock = test_case.get("mock_llm_response", {})

        # Support both old (string) and new (dict with extraction key) formats
        if isinstance(mock, str):
            raw = mock
        elif isinstance(mock, dict):
            raw = mock.get("extraction", "[]")
        else:
            raw = "[]"

        return self._parse_json_array(raw)

    def _extract_live(self, test_case: dict) -> list[dict]:
        """Call the real extraction pipeline via PersistenceAgent internals.

        We deliberately avoid standing up the full agent-state machinery.
        Instead we directly invoke the LLM extraction helper that the
        PersistenceAgent uses internally.
        """
        from app.agents.persistence_agent import PersistenceAgent

        agent = PersistenceAgent()
        markdown = test_case.get("input_markdown", "")
        questions = agent._extract_questions_with_llm(markdown)
        return questions if questions else []

    @staticmethod
    def _parse_json_array(text: str) -> list[dict]:
        """Safely parse a JSON array from a (potentially messy) string."""
        text = text.strip()

        # Strip markdown code fences
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Locate the JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            if isinstance(data, list):
                return data
        return []

    @staticmethod
    def _score_type_accuracy(questions: list[dict], expected: dict) -> float:
        """Compare extracted question_type values against expected.

        Returns the fraction of expected questions whose type was correctly
        identified.  If expected does not specify per-question types, returns
        1.0 (nothing to verify).
        """
        expected_questions = expected.get("questions", [])
        if not expected_questions:
            return 1.0

        matches = 0
        comparisons = min(len(questions), len(expected_questions))

        for i in range(comparisons):
            expected_type = expected_questions[i].get("question_type", "").lower().strip()
            actual_type = (questions[i].get("question_type") or "").lower().strip()
            if expected_type and expected_type == actual_type:
                matches += 1

        if not expected_questions:
            return 1.0

        return round(matches / len(expected_questions), 4)
