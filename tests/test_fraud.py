from app.fraud_detector import FraudDetector, FraudRisk


def base_claim():
    return {
        "claim_id": "CLM-TEST-FRAUD-001",
        "diagnosis": "Appendicitis",
        "treatment": "Laparoscopic appendectomy",
        "admission_date": "2026-08-20",
        "discharge_date": "2026-08-21",
        "bill_items": [
            {"name": "Room Rent", "amount": 4000},
            {"name": "Surgeon Fees", "amount": 30000},
            {"name": "Diagnostics", "amount": 10000},
        ],
    }


def test_low_risk_claim():
    result = FraudDetector().analyze(base_claim())

    assert result.risk_score >= 0
    assert result.risk_level == FraudRisk.LOW
    assert result.anomaly_flags == []
    assert result.requires_human_review is False


def test_timeline_mismatch():
    claim = base_claim()

    claim["admission_date"] = "2026-08-25"
    claim["discharge_date"] = "2026-08-20"

    result = FraudDetector().analyze(claim)

    assert any(
        "TIMELINE_MISMATCH" in flag
        for flag in result.anomaly_flags
    )


def test_duplicate_billing():
    claim = base_claim()

    claim["bill_items"] = [
        {
            "name": "Surgical Charges",
            "amount": 30000,
        },
        {
            "name": "Surgical Charges",
            "amount": 30000,
        },
    ]

    result = FraudDetector().analyze(claim)

    assert any(
        "DUPLICATE_BILLING" in flag
        for flag in result.anomaly_flags
    )


def test_high_fraud_claim():
    claim = base_claim()

    claim["admission_date"] = "2026-08-25"
    claim["discharge_date"] = "2026-08-20"

    claim["bill_items"] = [
        {
            "name": "Surgical Charges",
            "amount": 30000,
        },
        {
            "name": "Surgical Charges",
            "amount": 30000,
        },
        {
            "name": "Appendectomy",
            "amount": 20000,
        },
        {
            "name": "Appendectomy Procedure Charges",
            "amount": 20000,
        },
    ]

    result = FraudDetector().analyze(claim)

    assert result.risk_score >= 0
    assert result.risk_level in FraudRisk
    assert len(result.anomaly_flags) >= 2