"""Evaluation harness -- orchestrates running evaluators across test datasets.

The ``EvaluationHarness`` loads the baseline dataset, dispatches each test
case to the appropriate evaluator(s), and aggregates the results into a
summary report.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from app.evaluation.evaluators.extraction_evaluator import ExtractionEvaluator
from app.evaluation.evaluators.classification_evaluator import ClassificationEvaluator

logger = logging.getLogger(__name__)

# Default path to the baseline test-case dataset
_DATASET_DIR = Path(__file__).resolve().parent / "datasets"
_DEFAULT_DATASET = _DATASET_DIR / "baseline_questions.json"


class EvaluationHarness:
    """Main entry point for running Doculord evaluation suites.

    Usage::

        harness = EvaluationHarness()
        results = harness.run(mode="mock", agent="all")
        print(results["summary"])
    """

    def __init__(self, dataset_path: Optional[str] = None):
        """Initialise the harness.

        Args:
            dataset_path: Path to a JSON file containing test cases.  If
                *None*, the built-in ``baseline_questions.json`` is used.
        """
        self.dataset_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET
        self.extraction_evaluator = ExtractionEvaluator()
        self.classification_evaluator = ClassificationEvaluator()

    def run(self, mode: str = "mock", agent: str = "all") -> dict:
        """Execute the evaluation suite.

        Args:
            mode: ``"mock"`` (use saved responses) or ``"live"`` (call real
                LLM).
            agent: Which evaluator(s) to run.  One of ``"all"``,
                ``"extraction"``, or ``"classification"``.

        Returns:
            A dict with the following top-level keys:

            - **passed** (*int*) -- number of test cases that passed
            - **failed** (*int*) -- number that failed
            - **total** (*int*) -- total test cases evaluated
            - **pass_rate** (*float*) -- fraction passed (0.0-1.0)
            - **duration_ms** (*float*) -- total wall-clock time
            - **mode** (*str*) -- the mode used
            - **agent** (*str*) -- which agent(s) were evaluated
            - **results** (*list[dict]*) -- per-test-case detail dicts
            - **score_distribution** (*dict*) -- summary statistics per
              metric across all test cases
            - **summary** (*str*) -- human-readable one-liner
        """
        test_cases = self._load_dataset()
        logger.info(
            "Starting evaluation: mode=%s, agent=%s, test_cases=%d",
            mode,
            agent,
            len(test_cases),
        )

        all_results: list[dict] = []
        suite_start = time.perf_counter()

        for tc in test_cases:
            tc_id = tc.get("id", "unknown")

            if agent in ("all", "extraction"):
                logger.info("  [extraction] evaluating %s ...", tc_id)
                ext_result = self.extraction_evaluator.evaluate(tc, mode=mode)
                all_results.append(ext_result)

            if agent in ("all", "classification"):
                logger.info("  [classification] evaluating %s ...", tc_id)
                cls_result = self.classification_evaluator.evaluate(tc, mode=mode)
                all_results.append(cls_result)

        suite_duration = round((time.perf_counter() - suite_start) * 1000, 2)

        # Aggregate
        passed = sum(1 for r in all_results if r.get("passed"))
        failed = len(all_results) - passed
        total = len(all_results)
        pass_rate = round(passed / total, 4) if total > 0 else 0.0

        score_distribution = self._compute_score_distribution(all_results)

        summary = (
            f"{passed}/{total} passed ({pass_rate:.0%}) in {suite_duration:.0f}ms "
            f"[mode={mode}, agent={agent}]"
        )

        logger.info("Evaluation complete: %s", summary)

        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": pass_rate,
            "duration_ms": suite_duration,
            "mode": mode,
            "agent": agent,
            "results": all_results,
            "score_distribution": score_distribution,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_dataset(self) -> list[dict]:
        """Load and validate the test-case dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {self.dataset_path}"
            )

        with open(self.dataset_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        if not isinstance(data, list):
            raise ValueError("Dataset must be a JSON array of test cases")

        logger.info("Loaded %d test cases from %s", len(data), self.dataset_path)
        return data

    @staticmethod
    def _compute_score_distribution(results: list[dict]) -> dict:
        """Compute min / max / mean for every metric across all results.

        Returns a dict keyed by metric name, each value being a dict with
        ``min``, ``max``, ``mean``, and ``values`` (the raw list).
        """
        metric_values: dict[str, list[float]] = {}

        for r in results:
            scores = r.get("scores", {})
            for metric_name, value in scores.items():
                if isinstance(value, (int, float)):
                    metric_values.setdefault(metric_name, []).append(float(value))

        distribution: dict = {}
        for metric, values in metric_values.items():
            distribution[metric] = {
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "mean": round(sum(values) / len(values), 4),
                "count": len(values),
            }

        return distribution
