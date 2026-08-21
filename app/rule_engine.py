from datetime import date
from typing import Any, Dict, List, Optional

from app.models import RuleResult


class RuleEngine:
    """
    Deterministic insurance claim rule engine.

    This component is intentionally independent of any LLM.

    Responsibilities:

        - Sum Insured validation
        - Room rent capping
        - Proportional deductions
        - Waiting period validation
        - Non-payable item deductions
        - Payable amount calculation

    Financial rules must be enforced here rather than delegated
    to an LLM.
    """

    DEFAULT_ROOM_RENT_PERCENT = 0.01

    DEFAULT_WAITING_PERIOD_YEARS = 2

    DEFAULT_NON_PAYABLE_ITEMS = {
        "registration charges",
        "admission charges",
        "administrative charges",
        "food charges",
        "toiletries",
    }

    def __init__(
        self,
        rules: Optional[Dict[str, Any]] = None,
    ):
        self.rules = rules or {}

        self.room_rent_percent = self._get_room_rent_percent()

        self.waiting_period_years = (
            self._get_waiting_period_years()
        )

        self.non_payable_items = (
            self._get_non_payable_items()
        )

    # =========================================================
    # Configuration
    # =========================================================

    def _get_room_rent_percent(self) -> float:
        value = self.rules.get(
            "room_rent_percent",
            self.DEFAULT_ROOM_RENT_PERCENT,
        )

        try:
            value = float(value)
        except (TypeError, ValueError):
            value = self.DEFAULT_ROOM_RENT_PERCENT

        if value <= 0 or value > 1:
            return self.DEFAULT_ROOM_RENT_PERCENT

        return value

    def _get_waiting_period_years(self) -> int:
        value = self.rules.get(
            "waiting_period_years",
            self.DEFAULT_WAITING_PERIOD_YEARS,
        )

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = self.DEFAULT_WAITING_PERIOD_YEARS

        if value < 0:
            return self.DEFAULT_WAITING_PERIOD_YEARS

        return value

    def _get_non_payable_items(self) -> set:
        configured = self.rules.get(
            "non_payable_items"
        )

        if not configured:
            return set(
                self.DEFAULT_NON_PAYABLE_ITEMS
            )

        return {
            str(item).strip().lower()
            for item in configured
            if str(item).strip()
        }

    # =========================================================
    # Sum Insured
    # =========================================================

    def enforce_sum_insured(
        self,
        claimed_amount: float,
        remaining_sum_insured: float,
    ) -> RuleResult:
        """
        Prevent approval beyond available Sum Insured.
        """

        claimed_amount = max(
            float(claimed_amount),
            0.0,
        )

        remaining_sum_insured = max(
            float(remaining_sum_insured),
            0.0,
        )

        payable = min(
            claimed_amount,
            remaining_sum_insured,
        )

        deduction = max(
            claimed_amount - payable,
            0.0,
        )

        if claimed_amount == 0:
            reason = "Claimed amount is zero."

        elif remaining_sum_insured <= 0:
            reason = (
                "No remaining Sum Insured is available."
            )

        elif claimed_amount > remaining_sum_insured:
            reason = (
                "Claim exceeds remaining Sum Insured."
            )

        else:
            reason = (
                "Claim is within remaining Sum Insured."
            )

        return RuleResult(
            approved_amount=payable,
            deduction=deduction,
            payable=payable,
            applicable=True,
            eligible=remaining_sum_insured > 0,
            reason=reason,
        )

    # =========================================================
    # Room Rent Cap
    # =========================================================

    def calculate_room_rent_cap(
        self,
        sum_insured: float,
        selected_room_rent: float,
    ) -> RuleResult:
        """
        Calculate the eligible room rent.

        Default rule:

            Eligible Room Rent =
                1% of Sum Insured per day
        """

        sum_insured = max(
            float(sum_insured),
            0.0,
        )

        selected_room_rent = max(
            float(selected_room_rent),
            0.0,
        )

        allowed_room_rent = (
            sum_insured
            * self.room_rent_percent
        )

        if selected_room_rent <= allowed_room_rent:
            deduction = 0.0
            payable = selected_room_rent
            applicable = False
            reason = (
                "Selected room rent is within "
                "the eligible room rent limit."
            )

        else:
            deduction = (
                selected_room_rent
                - allowed_room_rent
            )

            payable = allowed_room_rent
            applicable = True

            reason = (
                "Selected room rent exceeds the "
                "eligible room rent limit."
            )

        return RuleResult(
            approved_amount=payable,
            allowed_room_rent=allowed_room_rent,
            deduction=deduction,
            payable=payable,
            applicable=applicable,
            eligible=True,
            reason=reason,
        )

    # =========================================================
    # Proportional Deduction
    # =========================================================

    def calculate_proportional_deduction(
        self,
        eligible_room_rent: float,
        selected_room_rent: float,
        associated_expenses: float,
    ) -> RuleResult:
        """
        Calculate proportional deduction on associated expenses.

        Example:

            Eligible room = ₹5,000
            Selected room = ₹10,000

            Ratio = 5,000 / 10,000 = 50%

            Eligible associated expense =
                50% of associated expense
        """

        eligible_room_rent = max(
            float(eligible_room_rent),
            0.0,
        )

        selected_room_rent = max(
            float(selected_room_rent),
            0.0,
        )

        associated_expenses = max(
            float(associated_expenses),
            0.0,
        )

        if (
            selected_room_rent <= 0
            or eligible_room_rent >= selected_room_rent
        ):
            return RuleResult(
                approved_amount=associated_expenses,
                deduction=0.0,
                payable=associated_expenses,
                applicable=False,
                eligible=True,
                reason=(
                    "No proportional deduction "
                    "is applicable."
                ),
            )

        ratio = (
            eligible_room_rent
            / selected_room_rent
        )

        payable = (
            associated_expenses
            * ratio
        )

        deduction = (
            associated_expenses
            - payable
        )

        return RuleResult(
            approved_amount=payable,
            deduction=deduction,
            payable=payable,
            applicable=True,
            eligible=True,
            reason=(
                "Associated expenses reduced "
                "proportionately because the selected "
                "room exceeds the eligible room limit."
            ),
        )

    # =========================================================
    # Non-payable item
    # =========================================================

    def check_non_payable_item(
        self,
        item_name: str,
        amount: float,
    ) -> RuleResult:
        """
        Determine whether a billed item is non-payable.
        """

        normalized_name = (
            str(item_name)
            .strip()
            .lower()
        )

        amount = max(
            float(amount),
            0.0,
        )

        is_non_payable = (
            normalized_name
            in self.non_payable_items
        )

        if is_non_payable:
            return RuleResult(
                approved_amount=0.0,
                deduction=amount,
                payable=0.0,
                applicable=True,
                eligible=False,
                is_non_payable=True,
                reason=(
                    "Item is classified as non-payable."
                ),
            )

        return RuleResult(
            approved_amount=amount,
            deduction=0.0,
            payable=amount,
            applicable=False,
            eligible=True,
            is_non_payable=False,
            reason=(
                "Item is not classified as "
                "non-payable by the configured rule set."
            ),
        )

    # =========================================================
    # Calculate non-payable deductions
    # =========================================================

    def calculate_non_payable_deductions(
        self,
        bill_items: List[Dict[str, Any]],
    ) -> RuleResult:
        """
        Calculate deductions across bill items.

        Expected format:

            [
                {
                    "name": "Food charges",
                    "amount": 500
                },
                {
                    "name": "Diagnostics",
                    "amount": 3000
                }
            ]
        """

        total_amount = 0.0
        total_deduction = 0.0

        for item in bill_items:
            name = item.get(
                "name",
                "",
            )

            amount = item.get(
                "amount",
                0.0,
            )

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                amount = 0.0

            amount = max(
                amount,
                0.0,
            )

            total_amount += amount

            result = self.check_non_payable_item(
                name,
                amount,
            )

            total_deduction += (
                result.deduction
            )

        payable = max(
            total_amount
            - total_deduction,
            0.0,
        )

        return RuleResult(
            approved_amount=payable,
            deduction=total_deduction,
            payable=payable,
            applicable=total_deduction > 0,
            eligible=True,
            reason=(
                "Calculated non-payable item "
                "deductions."
            ),
        )

    # =========================================================
    # Waiting Period
    # =========================================================

    def check_waiting_period(
        self,
        policy_start_date: str,
        treatment_date: str,
        waiting_period_years: Optional[int] = None,
    ) -> RuleResult:
        """
        Check whether the treatment falls inside the waiting
        period.

        Dates must be supplied as:

            YYYY-MM-DD
        """

        try:
            start_date = date.fromisoformat(
                policy_start_date
            )

            treatment = date.fromisoformat(
                treatment_date
            )

        except (TypeError, ValueError):
            return RuleResult(
                approved_amount=0.0,
                deduction=0.0,
                payable=0.0,
                applicable=True,
                eligible=False,
                reason=(
                    "Invalid policy or treatment date."
                ),
            )

        years = (
            self.waiting_period_years
            if waiting_period_years is None
            else int(waiting_period_years)
        )

        if treatment < start_date:
            return RuleResult(
                approved_amount=0.0,
                deduction=0.0,
                payable=0.0,
                applicable=True,
                eligible=False,
                reason=(
                    "Treatment date occurs before "
                    "policy commencement."
                ),
            )

        waiting_end = date(
            start_date.year + years,
            start_date.month,
            start_date.day,
        )

        inside_waiting_period = (
            treatment < waiting_end
        )

        if inside_waiting_period:
            return RuleResult(
                approved_amount=0.0,
                deduction=0.0,
                payable=0.0,
                applicable=True,
                eligible=False,
                reason=(
                    "Treatment falls within the "
                    "configured waiting period."
                ),
            )

        return RuleResult(
            approved_amount=0.0,
            deduction=0.0,
            payable=0.0,
            applicable=True,
            eligible=True,
            reason=(
                "Treatment is outside the "
                "configured waiting period."
            ),
        )

    # =========================================================
    # Final payable amount
    # =========================================================

    def calculate_final_payable(
        self,
        claimed_amount: float,
        remaining_sum_insured: float,
        deductions: float = 0.0,
    ) -> RuleResult:
        """
        Calculate final payable amount after deductions and
        Sum Insured enforcement.
        """

        claimed_amount = max(
            float(claimed_amount),
            0.0,
        )

        remaining_sum_insured = max(
            float(remaining_sum_insured),
            0.0,
        )

        deductions = max(
            float(deductions),
            0.0,
        )

        amount_after_deductions = max(
            claimed_amount - deductions,
            0.0,
        )

        payable = min(
            amount_after_deductions,
            remaining_sum_insured,
        )

        total_deduction = (
            claimed_amount - payable
        )

        return RuleResult(
            approved_amount=payable,
            deduction=total_deduction,
            payable=payable,
            applicable=True,
            eligible=payable > 0,
            reason=(
                "Final payable amount calculated after "
                "deductions and remaining Sum Insured "
                "validation."
            ),
        )