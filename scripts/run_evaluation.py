"""
Evaluation runner for the Mediclaim Adjudication Agent.

Usage:

    python Scripts/run_evaluation.py

Optional:

    python Scripts/run_evaluation.py \
        --dataset data/evaluation/claims.json

    python Scripts/run_evaluation.py \
        --output evaluation_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.claim_agent import adjudicate_claim_agent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    claim_id: str

    passed: bool

    expected_status: str
    actual_status: str

    expected_fraud_risk: str
    actual_fraud_risk: str

    expected_approved_amount: float | None
    actual_approved_amount: float

    amount_match: bool
    status_match: bool
    fraud_risk_match: bool

    policy_evidence_present: bool
    human_review_required: bool

    failures: List[str]


def load_dataset(
    dataset_path: Path,
) -> List[Dict[str, Any]]:
    """Load evaluation claims from JSON."""

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found: "
            f"{dataset_path}"
        )

    with dataset_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get(
            "claims",
            []
        )

    if not isinstance(data, list):
        raise ValueError(
            "Evaluation dataset must contain "
            "a JSON list of claims."
        )

    logger.info(
        "Loaded %d evaluation claims.",
        len(data),
    )

    return data


def compare_amount(
    expected: float | None,
    actual: float,
    tolerance: float = 0.01,
) -> bool:
    """
    Compare expected and actual amounts.

    A small tolerance handles floating-point
    arithmetic differences.
    """

    if expected is None:
        return True

    return abs(
        float(expected) - float(actual)
    ) <= tolerance


def evaluate_claim(
    test_case: Dict[str, Any],
) -> EvaluationResult:
    """Run one claim through the adjudication pipeline."""

    claim = test_case["claim"]
    expected = test_case["expected"]

    claim_id = claim.get(
        "claim_id",
        "UNKNOWN",
    )

    logger.info(
        "Evaluating claim %s",
        claim_id,
    )

    try:
        result = adjudicate_claim_agent(
            claim
        )

    except Exception as exc:
        logger.exception(
            "Claim %s failed during adjudication.",
            claim_id,
        )

        return EvaluationResult(
            claim_id=claim_id,
            passed=False,
            expected_status=expected.get(
                "status",
                "",
            ),
            actual_status="ERROR",
            expected_fraud_risk=expected.get(
                "fraud_risk",
                "",
            ),
            actual_fraud_risk="ERROR",
            expected_approved_amount=expected.get(
                "approved_amount",
            ),
            actual_approved_amount=0,
            amount_match=False,
            status_match=False,
            fraud_risk_match=False,
            policy_evidence_present=False,
            human_review_required=False,
            failures=[
                f"Adjudication exception: {exc}"
            ],
        )

    actual_status = result.get(
        "status",
        "",
    )

    actual_fraud_risk = result.get(
        "fraud_risk",
        "",
    )

    amount_breakdown = result.get(
        "amount_breakdown",
        {},
    )

    actual_approved_amount = float(
        amount_breakdown.get(
            "approved_amount",
            0,
        )
    )

    expected_status = expected.get(
        "status",
        "",
    )

    expected_fraud_risk = expected.get(
        "fraud_risk",
        "",
    )

    expected_amount = expected.get(
        "approved_amount",
    )

    status_match = (
        actual_status
        == expected_status
    )

    fraud_risk_match = (
        actual_fraud_risk
        == expected_fraud_risk
    )

    amount_match = compare_amount(
        expected_amount,
        actual_approved_amount,
    )

    policy_evidence_present = bool(
        result.get(
            "policy_citations",
            [],
        )
    )

    human_review_required = bool(
        result.get(
            "human_review_required",
            False,
        )
    )

    failures: List[str] = []

    if not status_match:
        failures.append(
            "Claim status mismatch: "
            f"expected={expected_status}, "
            f"actual={actual_status}"
        )

    if not fraud_risk_match:
        failures.append(
            "Fraud risk mismatch: "
            f"expected={expected_fraud_risk}, "
            f"actual={actual_fraud_risk}"
        )

    if not amount_match:
        failures.append(
            "Approved amount mismatch: "
            f"expected={expected_amount}, "
            f"actual={actual_approved_amount}"
        )

    if expected.get(
        "policy_evidence_required",
        False,
    ):
        if not policy_evidence_present:
            failures.append(
                "Expected policy evidence "
                "but none was returned."
            )

    if expected.get(
        "human_review_required",
        False,
    ):
        if not human_review_required:
            failures.append(
                "Expected human review "
                "but it was not required."
            )

    # Deterministic safety check:
    requested_amount = float(
        claim.get(
            "requested_amount",
            0,
        )
    )

    if actual_approved_amount > requested_amount:
        failures.append(
            "GUARDRAIL FAILURE: approved amount "
            "exceeds requested amount."
        )

    sum_insured = float(
        claim.get(
            "sum_insured",
            0,
        )
    )

    current_year_used = float(
        claim.get(
            "current_year_used",
            0,
        )
    )

    remaining_sum_insured = max(
        0,
        sum_insured - current_year_used,
    )

    if actual_approved_amount > remaining_sum_insured:
        failures.append(
            "GUARDRAIL FAILURE: approved amount "
            "exceeds remaining Sum Insured."
        )

    return EvaluationResult(
        claim_id=claim_id,
        passed=len(failures) == 0,
        expected_status=expected_status,
        actual_status=actual_status,
        expected_fraud_risk=expected_fraud_risk,
        actual_fraud_risk=actual_fraud_risk,
        expected_approved_amount=expected_amount,
        actual_approved_amount=actual_approved_amount,
        amount_match=amount_match,
        status_match=status_match,
        fraud_risk_match=fraud_risk_match,
        policy_evidence_present=(
            policy_evidence_present
        ),
        human_review_required=(
            human_review_required
        ),
        failures=failures,
    )


def calculate_metrics(
    results: List[EvaluationResult],
) -> Dict[str, Any]:
    """Calculate aggregate evaluation metrics."""

    total = len(results)

    if total == 0:
        return {
            "total_claims": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0,
        }

    passed = sum(
        result.passed
        for result in results
    )

    failed = total - passed

    status_correct = sum(
        result.status_match
        for result in results
    )

    fraud_correct = sum(
        result.fraud_risk_match
        for result in results
    )

    amount_correct = sum(
        result.amount_match
        for result in results
    )

    return {
        "total_claims": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(
            passed / total * 100,
            2,
        ),
        "status_accuracy": round(
            status_correct / total * 100,
            2,
        ),
        "fraud_risk_accuracy": round(
            fraud_correct / total * 100,
            2,
        ),
        "approved_amount_accuracy": round(
            amount_correct / total * 100,
            2,
        ),
    }


def print_report(
    results: List[EvaluationResult],
    metrics: Dict[str, Any],
) -> None:
    """Print human-readable evaluation report."""

    print()
    print("=" * 70)
    print("MEDICLAIM ADJUDICATION EVALUATION")
    print("=" * 70)

    print(
        f"Total Claims      : "
        f"{metrics['total_claims']}"
    )

    print(
        f"Passed            : "
        f"{metrics['passed']}"
    )

    print(
        f"Failed            : "
        f"{metrics['failed']}"
    )

    print(
        f"Pass Rate         : "
        f"{metrics['pass_rate']}%"
    )

    print(
        f"Status Accuracy   : "
        f"{metrics['status_accuracy']}%"
    )

    print(
        f"Fraud Accuracy    : "
        f"{metrics['fraud_risk_accuracy']}%"
    )

    print(
        f"Amount Accuracy   : "
        f"{metrics['approved_amount_accuracy']}%"
    )

    print()
    print("-" * 70)

    for result in results:
        status = (
            "PASS"
            if result.passed
            else "FAIL"
        )

        print(
            f"{status:4} | "
            f"{result.claim_id:15} | "
            f"Expected: {result.expected_status:18} | "
            f"Actual: {result.actual_status}"
        )

        if result.failures:
            for failure in result.failures:
                print(
                    f"       -> {failure}"
                )

    print("=" * 70)


def save_report(
    output_path: Path,
    results: List[EvaluationResult],
    metrics: Dict[str, Any],
) -> None:
    """Save machine-readable evaluation report."""

    report = {
        "metrics": metrics,
        "results": [
            asdict(result)
            for result in results
        ],
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    logger.info(
        "Evaluation report saved to %s",
        output_path,
    )


def run_evaluation(
    dataset_path: Path,
    output_path: Path | None = None,
) -> int:
    """Execute complete evaluation."""

    test_cases = load_dataset(
        dataset_path
    )

    results: List[EvaluationResult] = []

    for test_case in test_cases:
        result = evaluate_claim(
            test_case
        )

        results.append(result)

    metrics = calculate_metrics(
        results
    )

    print_report(
        results,
        metrics,
    )

    if output_path:
        save_report(
            output_path,
            results,
            metrics,
        )

    # Return non-zero exit code if evaluation
    # has failed. Useful for CI/CD pipelines.
    if metrics["failed"] > 0:
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the Mediclaim "
            "Adjudication Agent."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=(
            PROJECT_ROOT
            / "data"
            / "evaluation"
            / "claims.json"
        ),
        help=(
            "Evaluation dataset JSON file."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "data"
            / "evaluation"
            / "results.json"
        ),
        help=(
            "Output evaluation report."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    exit_code = run_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()