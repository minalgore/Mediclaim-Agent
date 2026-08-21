import json

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


# =========================================================
# Helpers
# =========================================================

def post_claim(claim):
    response = client.post(
        "/api/v1/claims/adjudicate",
        data={
            "claim": json.dumps(claim)
        },
    )

    assert response.status_code == 200, (
        "Unexpected HTTP status: "
        f"{response.status_code}\n"
        f"{response.text}"
    )

    return response.json()


def base_claim():
    return {
        "claim_id": "CLM-E2E-BASE-001",
        "policy_id": "POL-IND-001",
        "policyholder_id": "PH-001",
        "diagnosis": "Appendicitis",
        "treatment": "Laparoscopic appendectomy",
        "sum_insured": 500000,
        "remaining_sum_insured": 500000,
        "selected_room_rent": 4000,
        "claimed_amount": 95000,
        "policy_start_date": "2023-01-01",
        "treatment_date": "2026-08-20",
        "bill_items": [
            {
                "name": "Room Rent",
                "amount": 4000,
            },
            {
                "name": "Surgeon Fees",
                "amount": 30000,
            },
            {
                "name": "Diagnostics",
                "amount": 10000,
            },
            {
                "name": "Hospital Charges",
                "amount": 51000,
            },
        ],
    }


# =========================================================
# 1. Full eligible claim
# =========================================================

def test_e2e_full_claim_approved():
    claim = base_claim()

    result = post_claim(claim)

    assert result["claim_id"] == "CLM-E2E-BASE-001"
    assert result["claim_status"] == "APPROVED"
    assert result["claimed_amount"] == 95000.0
    assert result["approved_amount"] == 95000.0

    assert (
        result["fraud_assessment"]["risk_level"]
        == "FRAUDRISK.LOW"
    )

    assert (
        result["fraud_assessment"]["requires_human_review"]
        is False
    )

    assert result["query_reasons"] == []
    assert result["guardrail_flags"] == []


# =========================================================
# 2. Non-payable items
# =========================================================

def test_e2e_non_payable_items():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-NONPAY-001"
    claim["claimed_amount"] = 100000

    claim["bill_items"] = [
        {
            "name": "Room Rent",
            "amount": 4000,
        },
        {
            "name": "Surgeon Fees",
            "amount": 30000,
        },
        {
            "name": "Diagnostics",
            "amount": 10000,
        },
        {
            "name": "Food Charges",
            "amount": 5000,
        },
        {
            "name": "Hospital Charges",
            "amount": 51000,
        },
    ]

    result = post_claim(claim)

    assert result["claim_status"] == "PARTIAL_APPROVAL"
    assert result["claimed_amount"] == 100000.0
    assert result["approved_amount"] == 95000.0

    assert (
        "NON_PAYABLE_ITEMS"
        in result["policy_clause_citations"]
    )

    assert (
        result["amount_breakdown"][
            "consumables_deductions"
        ]
        == 5000.0
    )


# =========================================================
# 3. Waiting period rejection
# =========================================================

def test_e2e_waiting_period_rejection():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-WAIT-001"

    claim["policy_start_date"] = "2025-01-01"
    claim["treatment_date"] = "2026-01-01"

    result = post_claim(claim)

    assert result["claim_status"] == "REJECTED"
    assert result["approved_amount"] == 0.0

    assert (
        "WAITING_PERIOD"
        in result["policy_clause_citations"]
    )

    assert any(
        "waiting period" in reason.lower()
        for reason in result["deduction_reasons"]
    )


# =========================================================
# 4. Fraud detection / human review
# =========================================================

def test_e2e_high_fraud_risk():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-FRAUD-001"

    claim["diagnosis"] = "Migraine"
    claim["treatment"] = "Laparoscopic appendectomy"

    claim["admission_date"] = "2026-08-20"
    claim["discharge_date"] = "2026-08-19"

    claim["bill_items"] = [
        {
            "name": "Surgical Charges",
            "amount": 25000,
        },
        {
            "name": "Surgical Charges",
            "amount": 25000,
        },
        {
            "name": "Procedure Charges",
            "amount": 20000,
        },
        {
            "name": "Laparoscopic Procedure",
            "amount": 30000,
        },
    ]

    result = post_claim(claim)

    fraud = result["fraud_assessment"]

    assert result["claim_status"] == "QUERY_RAISED"

    assert fraud["risk_score"] >= 70.0
    assert fraud["risk_level"] == "FRAUDRISK.HIGH"
    assert fraud["requires_human_review"] is True

    assert len(fraud["anomaly_flags"]) > 0
    assert len(result["query_reasons"]) > 0


# =========================================================
# 5. Sum insured limit
# =========================================================

def test_e2e_sum_insured_limit():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-SI-001"

    claim["remaining_sum_insured"] = 50000
    claim["claimed_amount"] = 100000

    result = post_claim(claim)

    assert result["claim_status"] == "PARTIAL_APPROVAL"
    assert result["approved_amount"] == 50000.0

    assert any(
        "sum insured" in reason.lower()
        for reason in result["deduction_reasons"]
    )


# =========================================================
# 6. Missing mandatory bill_items
# =========================================================

def test_e2e_missing_bill_items():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-MISSING-001"

    del claim["bill_items"]

    result = post_claim(claim)

    assert result["claim_status"] == "QUERY_RAISED"

    assert "bill_items" in (
        " ".join(
            result["query_reasons"]
        ).lower()
    )


# =========================================================
# 7. Room rent exceeds limit
# =========================================================

def test_e2e_room_rent_limit():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-ROOM-001"

    claim["selected_room_rent"] = 10000
    claim["claimed_amount"] = 100000

    result = post_claim(claim)

    assert result["claim_status"] == "PARTIAL_APPROVAL"
    assert result["approved_amount"] == 95000.0

    assert (
        "ROOM_RENT_LIMIT"
        in result["policy_clause_citations"]
    )

    assert any(
        "room rent" in reason.lower()
        for reason in result["deduction_reasons"]
    )


# =========================================================
# 8. Response structure validation
# =========================================================

def test_e2e_response_structure():
    claim = base_claim()

    claim["claim_id"] = "CLM-E2E-STRUCTURE-001"

    result = post_claim(claim)

    required_fields = [
        "claim_id",
        "claim_status",
        "claimed_amount",
        "approved_amount",
        "amount_breakdown",
        "policy_clause_citations",
        "deduction_reasons",
        "fraud_assessment",
        "query_reasons",
        "guardrail_flags",
    ]

    for field in required_fields:
        assert field in result

    assert isinstance(
        result["amount_breakdown"],
        dict,
    )

    assert isinstance(
        result["policy_clause_citations"],
        list,
    )

    assert isinstance(
        result["deduction_reasons"],
        list,
    )

    assert isinstance(
        result["fraud_assessment"],
        dict,
    )

    assert isinstance(
        result["query_reasons"],
        list,
    )

    assert isinstance(
        result["guardrail_flags"],
        list,
    )