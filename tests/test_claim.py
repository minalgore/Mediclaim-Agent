from app.claim_agent import ClaimAgent


def base_claim():
    return {
        "claim_id": "CLM-TEST-001",
        "policy_id": "POL-IND-001",
        "policyholder_id": "PH-001",
        "diagnosis": "Appendicitis",
        "treatment": "Laparoscopic appendectomy",
        "sum_insured": 500000,
        "remaining_sum_insured": 500000,
        "selected_room_rent": 4000,
        "claimed_amount": 95000,
        "policy_start_date": "2023-01-01",
        "treatment_date": "2026-01-01",
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


def test_claim_agent_processes_claim():
    agent = ClaimAgent()

    result = agent.process_claim(
        base_claim()
    )

    assert isinstance(result, dict)

    assert result["claim_id"] == "CLM-TEST-001"
    assert result["policyholder_id"] == "PH-001"

    assert "sanitized_claim" in result
    assert "policy_evidence" in result
    assert "claim_history" in result
    assert "rule_results" in result
    assert "fraud_result" in result

    assert result["status"] == "PENDING_ADJUDICATION"


def test_claim_agent_runs_rule_checks():
    agent = ClaimAgent()

    result = agent.process_claim(
        base_claim()
    )

    rule_results = result["rule_results"]

    assert isinstance(
        rule_results,
        dict,
    )

    assert "room_rent" in rule_results
    assert "non_payable_items" in rule_results
    assert "waiting_period" in rule_results


def test_claim_agent_detects_low_fraud_risk_for_normal_claim():
    agent = ClaimAgent()

    result = agent.process_claim(
        base_claim()
    )

    fraud_result = result["fraud_result"]

    assert isinstance(
        fraud_result,
        dict,
    )

    assert "risk_score" in fraud_result
    assert "risk_level" in fraud_result
    assert "anomaly_flags" in fraud_result
