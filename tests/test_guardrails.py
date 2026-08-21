from app.guardrails import (
    ClaimGuardrails,
    GuardrailViolation,
)


def valid_result():
    return {
        "claim_id": "CLM-GUARD-001",
        "claim_status": "PARTIAL_APPROVAL",
        "claimed_amount": 100000.0,
        "approved_amount": 95000.0,
        "amount_breakdown": {
            "base_room": 4000.0,
            "surgeon_fees": 0.0,
            "diagnostics": 0.0,
            "consumables_deductions": 5000.0,
            "other_deductions": 0.0,
            "approved_amount": 95000.0,
        },
        "policy_clause_citations": [
            "NON_PAYABLE_ITEMS",
        ],
        "deduction_reasons": [
            "Non-payable bill items were deducted "
            "according to applicable policy terms."
        ],
        "fraud_assessment": {
            "risk_score": 0.0,
            "risk_level": "LOW",
            "anomaly_flags": [],
            "requires_human_review": False,
        },
        "query_reasons": [],
        "guardrail_flags": [],
    }


def test_valid_partial_approval_passes():
    guardrails = ClaimGuardrails()

    result = valid_result()

    output = guardrails.validate(
        result,
        remaining_sum_insured=100000,
    )

    assert output is not None


def test_rejected_claim_must_have_zero_approved_amount():
    guardrails = ClaimGuardrails()

    result = valid_result()

    result["claim_status"] = "REJECTED"
    result["approved_amount"] = 0.0
    result["amount_breakdown"]["approved_amount"] = 0.0

    result["policy_clause_citations"] = [
        "WAITING_PERIOD",
    ]

    result["deduction_reasons"] = [
        "Treatment falls within the applicable waiting period."
    ]

    output = guardrails.validate(
        result,
        remaining_sum_insured=100000,
    )

    assert output is not None

    assert output.claim_status == "REJECTED"
    assert output.approved_amount == 0.0

def test_rejected_claim_with_nonzero_approved_amount_fails():
    guardrails = ClaimGuardrails()

    result = valid_result()

    result["claim_status"] = "REJECTED"
    result["approved_amount"] = 1000.0
    result["amount_breakdown"]["approved_amount"] = 1000.0
    result["policy_clause_citations"] = [
        "WAITING_PERIOD",
    ]

    try:
        guardrails.validate(
            result,
            remaining_sum_insured=100000,
        )
        assert False, (
            "Expected GuardrailViolation"
        )
    except GuardrailViolation:
        pass


def test_partial_approval_requires_policy_citation():
    guardrails = ClaimGuardrails()

    result = valid_result()

    result["policy_clause_citations"] = []

    try:
        guardrails.validate(
            result,
            remaining_sum_insured=100000,
        )
        assert False, (
            "Expected GuardrailViolation"
        )
    except GuardrailViolation:
        pass
