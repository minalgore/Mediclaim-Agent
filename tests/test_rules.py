from app.rule_engine import RuleEngine


def test_room_rent_within_limit():
    engine = RuleEngine()

    result = engine.calculate_room_rent_cap(
        sum_insured=500000,
        selected_room_rent=4000,
    )

    assert result.eligible is True
    assert result.deduction == 0
    assert result.payable == 4000


def test_room_rent_exceeds_limit():
    engine = RuleEngine()

    result = engine.calculate_room_rent_cap(
        sum_insured=500000,
        selected_room_rent=10000,
    )

    assert result.applicable is True
    assert result.eligible is True
    assert result.allowed_room_rent == 5000
    assert result.deduction == 5000
    assert result.payable == 5000


def test_room_rent_limit_calculation():
    engine = RuleEngine()

    result = engine.calculate_room_rent_cap(
        sum_insured=500000,
        selected_room_rent=10000,
    )

    # 1% of 500,000 = 5,000
    assert result.allowed_room_rent == 5000
    assert result.deduction == 5000
    assert result.payable == 5000


def test_proportional_deduction():
    engine = RuleEngine()

    result = engine.calculate_proportional_deduction(
        eligible_room_rent=5000,
        selected_room_rent=10000,
        associated_expenses=20000,
    )

    assert result.applicable is True
    assert result.eligible is True
    assert result.payable == 10000
    assert result.deduction == 10000


def test_no_proportional_deduction_when_room_within_limit():
    engine = RuleEngine()

    result = engine.calculate_proportional_deduction(
        eligible_room_rent=5000,
        selected_room_rent=4000,
        associated_expenses=20000,
    )

    assert result.applicable is False
    assert result.eligible is True
    assert result.payable == 20000
    assert result.deduction == 0


def test_non_payable_item():
    engine = RuleEngine()

    result = engine.check_non_payable_item(
        item_name="Food Charges",
        amount=5000,
    )

    assert result.is_non_payable is True
    assert result.eligible is False
    assert result.deduction == 5000
    assert result.payable == 0


def test_payable_item():
    engine = RuleEngine()

    result = engine.check_non_payable_item(
        item_name="Surgeon Fees",
        amount=30000,
    )

    assert result.is_non_payable is False
    assert result.eligible is True
    assert result.deduction == 0
    assert result.payable == 30000


def test_non_payable_deductions():
    engine = RuleEngine()

    bill_items = [
        {
            "name": "Room Rent",
            "amount": 4000,
        },
        {
            "name": "Food Charges",
            "amount": 5000,
        },
        {
            "name": "Surgeon Fees",
            "amount": 30000,
        },
    ]

    result = engine.calculate_non_payable_deductions(
        bill_items
    )

    # Total = 39,000
    # Food Charges = 5,000 non-payable
    # Payable = 34,000
    assert result.deduction == 5000
    assert result.payable == 34000
    assert result.approved_amount == 34000
    assert result.applicable is True
    assert result.eligible is True


def test_waiting_period_inside():
    engine = RuleEngine()

    result = engine.check_waiting_period(
        policy_start_date="2024-01-01",
        treatment_date="2025-01-01",
    )

    assert result.applicable is True
    assert result.eligible is False
    assert result.payable == 0


def test_waiting_period_completed():
    engine = RuleEngine()

    result = engine.check_waiting_period(
        policy_start_date="2023-01-01",
        treatment_date="2026-01-01",
    )

    assert result.applicable is True
    assert result.eligible is True
    assert result.payable == 0


def test_treatment_before_policy_start():
    engine = RuleEngine()

    result = engine.check_waiting_period(
        policy_start_date="2024-01-01",
        treatment_date="2023-12-01",
    )

    assert result.applicable is True
    assert result.eligible is False


def test_invalid_waiting_period_dates():
    engine = RuleEngine()

    result = engine.check_waiting_period(
        policy_start_date="invalid",
        treatment_date="2026-01-01",
    )

    assert result.applicable is True
    assert result.eligible is False
    assert result.reason == "Invalid policy or treatment date."