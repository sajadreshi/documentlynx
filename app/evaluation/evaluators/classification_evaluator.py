"""Classification evaluator -- tests the question classification pipeline.

Runs each test case through the classification logic (either using a mock
LLM response or the real LLM) and compares the result against the expected
ground truth.
"""

import json
import logging
import time
from typing import Optional

from app.evaluation.metrics import score_classification_accuracy

logger = logging.getLogger(__name__)


class ClassificationEvaluator:
    """Evaluator for the classification stage of the Doculord pipeline.

    In *mock* mode the evaluator uses the pre-recorded ``mock_llm_response``
    from the test case.  In *live* mode it calls the real LLM via the
    ``classify_question`` tool.
    """

    # Minimum overall accuracy to consider the test case passed
    ACCURACY_THRESHOLD = 0.6

    def evaluate(self, test_case: dict, mode: str = "mock") -> dict:
        """Run classification evaluation on a single test case.

        Args:
            test_case: A dict loaded from baseline_questions.json.
            mode: ``"mock"`` or ``"live"``.

        Returns:
            A result dict with keys:
              - test_id, agent, mode, passed, scores,
                classifications, duration_ms, error
        """
        test_id = test_case.get("id", "unknown")
        start = time.perf_counter()

        result = {
            "test_id": test_id,
            "agent": "classification",
            "mode": mode,
            "passed": False,
            "scores": {},
            "classifications": [],
            "duration_ms": 0.0,
            "error": None,
        }

        try:
            if mode == "mock":
                classifications = self._classify_mock(test_case)
            elif mode == "live":
                classifications = self._classify_live(test_case)
            else:
                raise ValueError(f"Unknown mode: {mode}")

            result["classifications"] = classifications

            # --- Scoring ---
            expected_questions = test_case.get("expected", {}).get("questions", [])

            if not expected_questions:
                # Nothing to evaluate -- vacuously pass
                result["scores"]["classification_accuracy"] = 1.0
                result["passed"] = True
            else:
                per_question_scores = []
                comparisons = min(len(classifications), len(expected_questions))

                for i in range(comparisons):
                    score = score_classification_accuracy(
                        classifications[i], expected_questions[i]
                    )
                    per_question_scores.append(score)

                # Penalize missing classifications
                for _ in range(len(expected_questions) - comparisons):
                    per_question_scores.append(0.0)

                avg_accuracy = (
                    round(sum(per_question_scores) / len(per_question_scores), 4)
                    if per_question_scores
                    else 0.0
                )
                result["scores"]["classification_accuracy"] = avg_accuracy
                result["scores"]["per_question"] = per_question_scores

                result["passed"] = avg_accuracy >= self.ACCURACY_THRESHOLD

        except Exception as exc:
            logger.error(
                "Classification evaluation failed for %s: %s",
                test_id,
                exc,
                exc_info=True,
            )
            result["error"] = str(exc)

        result["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_mock(self, test_case: dict) -> list[dict]:
        """Parse the mock classification response stored in the test case."""
        mock = test_case.get("mock_llm_response", {})

        if isinstance(mock, str):
            # Legacy format: the entire mock is the classification string
            raw = mock
        elif isinstance(mock, dict):
            raw = mock.get("classification", "[]")
        else:
            raw = "[]"

        return self._parse_json_array(raw)

    def _classify_live(self, test_case: dict) -> list[dict]:
        """Call the real classification tool for each expected question.

        We first run mock extraction to get question texts (so that the
        classification evaluator does not depend on extraction correctness
        in live mode), then classify each question individually via the
        LangChain ``classify_question`` tool.
        """
        from app.tools.classification_tools import classify_question

        mock = test_case.get("mock_llm_response", {})
        if isinstance(mock, dict):
            extraction_raw = mock.get("extraction", "[]")
        elif isinstance(mock, str):
            extraction_raw = mock
        else:
            extraction_raw = "[]"

        questions = self._parse_json_array(extraction_raw)

        # Fall back to synthesising minimal question dicts from expected data
        if not questions:
            expected_qs = test_case.get("expected", {}).get("questions", [])
            questions = [
                {
                    "question_text": test_case.get("input_markdown", ""),
                    "question_type": eq.get("question_type", "open_ended"),
                }
                for eq in expected_qs
            ]

        classifications = []
        for idx, q in enumerate(questions):
            classification = classify_question.invoke(
                {
                    "question_text": q.get("question_text", ""),
                    "question_type": q.get("question_type", "open_ended"),
                    "options": q.get("options"),
                    "question_id": f"q{idx + 1}",
                }
            )
            classifications.append(classification)

        return classifications

    @staticmethod
    def _parse_json_array(text: str) -> list[dict]:
        """Safely parse a JSON array from a (potentially messy) string."""
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            if isinstance(data, list):
                return data
        return []
