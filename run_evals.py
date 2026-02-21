"""Evaluation runner CLI.

Usage examples::

    # Run all evaluations in mock mode (no LLM calls)
    python run_evals.py

    # Run only extraction evaluations in live mode
    python run_evals.py --mode live --agent extraction

    # Save results to a custom path
    python run_evals.py --output results/eval_2024.json

    # Use a custom dataset
    python run_evals.py --dataset path/to/custom_tests.json
"""

import argparse
import json
import logging
import sys

from app.evaluation.harness import EvaluationHarness


def main():
    parser = argparse.ArgumentParser(
        description="Run Doculord evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_evals.py                              # mock mode, all agents\n"
            "  python run_evals.py --mode live --agent extraction\n"
            "  python run_evals.py --output results.json --verbose\n"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="Evaluation mode: 'mock' uses saved responses, 'live' calls real LLM (default: mock)",
    )
    parser.add_argument(
        "--agent",
        choices=["all", "extraction", "classification"],
        default="all",
        help="Which agent(s) to evaluate (default: all)",
    )
    parser.add_argument(
        "--output",
        default="eval_results.json",
        help="Path to write the JSON results file (default: eval_results.json)",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to a custom test-case dataset JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG-level) logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Run evaluations
    harness = EvaluationHarness(dataset_path=args.dataset)
    results = harness.run(mode=args.mode, agent=args.agent)

    # Write results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    passed = results.get("passed", 0)
    total = results.get("total", 0)
    failed = results.get("failed", 0)
    pass_rate = results.get("pass_rate", 0.0)
    duration = results.get("duration_ms", 0.0)

    print()
    print("=" * 60)
    print("  DOCULORD EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Mode:     {args.mode}")
    print(f"  Agent:    {args.agent}")
    print(f"  Dataset:  {args.dataset or 'baseline_questions.json'}")
    print("-" * 60)
    print(f"  Passed:   {passed}/{total} ({pass_rate:.0%})")
    print(f"  Failed:   {failed}")
    print(f"  Duration: {duration:.0f}ms")
    print("-" * 60)

    # Print score distribution
    score_dist = results.get("score_distribution", {})
    if score_dist:
        print("  Score distribution:")
        for metric, stats in score_dist.items():
            print(
                f"    {metric:30s}  "
                f"min={stats['min']:.2f}  "
                f"max={stats['max']:.2f}  "
                f"mean={stats['mean']:.2f}"
            )
        print("-" * 60)

    # Print per-test details for failures
    failing = [r for r in results.get("results", []) if not r.get("passed")]
    if failing:
        print("  Failed test cases:")
        for r in failing:
            error_info = f" -- {r['error']}" if r.get("error") else ""
            print(f"    [{r['agent']}] {r['test_id']}: scores={r.get('scores', {})}{error_info}")
        print("-" * 60)

    print(f"  Results written to: {args.output}")
    print("=" * 60)
    print()

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
