"""
Run the final MediClaim end-to-end demo claim set.

Usage:
    PYTHONPATH=. python scripts/run_demo.py
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from main import app


CLAIMS_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sample_claims"
    / "demo_claims.json"
)


def load_claims():
    with CLAIMS_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    claims = load_claims()
    client = TestClient(app)

    print("=" * 78)
    print("MediClaim Adjudication - Final E2E Demo")
    print("=" * 78)

    passed = 0

    for index, claim in enumerate(claims, start=1):

        print("\n" + "-" * 78)
        print(
            "DEMO CASE {}: {}".format(
                index,
                claim["claim_id"],
            )
        )
        print("-" * 78)

        # API expects claim as a multipart form field.
        response = client.post(
            "/api/v1/claims/adjudicate",
            data={
                "claim": json.dumps(claim),
            },
        )

        print(
            "HTTP STATUS : {}".format(
                response.status_code
            )
        )

        if response.status_code >= 400:
            print(
                "ERROR       : {}".format(
                    response.text
                )
            )
            continue

        result = response.json()

        print(
            "CLAIM STATUS: {}".format(
                result.get("claim_status")
            )
        )

        print(
            "CLAIMED     : {:.2f}".format(
                float(
                    result.get(
                        "claimed_amount",
                        0.0,
                    )
                )
            )
        )

        print(
            "APPROVED    : {:.2f}".format(
                float(
                    result.get(
                        "approved_amount",
                        0.0,
                    )
                )
            )
        )

        fraud = result.get(
            "fraud_assessment",
            {},
        )

        print(
            "FRAUD SCORE : {:.2f}".format(
                float(
                    fraud.get(
                        "risk_score",
                        0.0,
                    )
                )
            )
        )

        print(
            "FRAUD LEVEL : {}".format(
                fraud.get("risk_level")
            )
        )

        print(
            "HUMAN REVIEW: {}".format(
                fraud.get(
                    "requires_human_review"
                )
            )
        )

        flags = fraud.get(
            "anomaly_flags",
            [],
        )

        if flags:
            print("FRAUD FLAGS :")

            for flag in flags:
                print(
                    "  - {}".format(flag)
                )

        query_reasons = result.get(
            "query_reasons",
            [],
        )

        if query_reasons:
            print("QUERY REASONS:")

            for reason in query_reasons:
                print(
                    "  - {}".format(reason)
                )

        deduction_reasons = result.get(
            "deduction_reasons",
            [],
        )

        if deduction_reasons:
            print("DEDUCTIONS:")

            for reason in deduction_reasons:
                print(
                    "  - {}".format(reason)
                )

        policy_citations = result.get(
            "policy_clause_citations",
            [],
        )

        if policy_citations:
            print("POLICY CITATIONS:")

            for citation in policy_citations:
                print(
                    "  - {}".format(citation)
                )

        passed += 1

    print("\n" + "=" * 78)

    print(
        "DEMO COMPLETE: {}/{} claims processed".format(
            passed,
            len(claims),
        )
    )

    print("=" * 78)


if __name__ == "__main__":
    main()