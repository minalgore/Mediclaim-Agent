from typing import Any, Dict, List, Optional

from app.rule_engine import RuleEngine


class ClaimTools:
    """
    Tool layer exposed to the claim adjudication agent.

    The tools in this class perform deterministic operations.
    The LLM should request these tools rather than calculating
    financial values itself.
    """

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
    ):
        self.rule_engine = (
            rule_engine
            if rule_engine is not None
            else RuleEngine()
        )

    # =========================================================
    # Room Rent Tool
    # =========================================================

    def calculate_room_rent(
        self,
        sum_insured: float,
        selected_room_rent: float,
    ) -> Dict[str, Any]:
        """
        Calculate eligible room rent and room-rent deduction.
        """

        result = (
            self.rule_engine.calculate_room_rent_cap(
                sum_insured=sum_insured,
                selected_room_rent=selected_room_rent,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Proportional Deduction Tool
    # =========================================================

    def calculate_proportional_deduction(
        self,
        eligible_room_rent: float,
        selected_room_rent: float,
        associated_expenses: float,
    ) -> Dict[str, Any]:
        """
        Calculate proportional deduction on associated
        expenses.
        """

        result = (
            self.rule_engine.calculate_proportional_deduction(
                eligible_room_rent=eligible_room_rent,
                selected_room_rent=selected_room_rent,
                associated_expenses=associated_expenses,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Sum Insured Tool
    # =========================================================

    def check_sum_insured(
        self,
        claimed_amount: float,
        remaining_sum_insured: float,
    ) -> Dict[str, Any]:
        """
        Ensure the claim cannot exceed the available
        Sum Insured.
        """

        result = (
            self.rule_engine.enforce_sum_insured(
                claimed_amount=claimed_amount,
                remaining_sum_insured=remaining_sum_insured,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Non-payable Item Tool
    # =========================================================

    def check_non_payable_item(
        self,
        item_name: str,
        amount: float,
    ) -> Dict[str, Any]:
        """
        Check whether a particular bill item is non-payable.
        """

        result = (
            self.rule_engine.check_non_payable_item(
                item_name=item_name,
                amount=amount,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Non-payable Bill Tool
    # =========================================================

    def calculate_non_payable_deductions(
        self,
        bill_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate deductions for all non-payable bill items.
        """

        result = (
            self.rule_engine.calculate_non_payable_deductions(
                bill_items=bill_items,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Waiting Period Tool
    # =========================================================

    def check_waiting_period(
        self,
        policy_start_date: str,
        treatment_date: str,
        waiting_period_years: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Check whether treatment falls within a waiting period.
        """

        result = (
            self.rule_engine.check_waiting_period(
                policy_start_date=policy_start_date,
                treatment_date=treatment_date,
                waiting_period_years=waiting_period_years,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # Final Claim Calculation Tool
    # =========================================================

    def calculate_final_payable(
        self,
        claimed_amount: float,
        remaining_sum_insured: float,
        deductions: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Calculate the final amount payable after deductions
        and Sum Insured enforcement.
        """

        result = (
            self.rule_engine.calculate_final_payable(
                claimed_amount=claimed_amount,
                remaining_sum_insured=remaining_sum_insured,
                deductions=deductions,
            )
        )

        return self._rule_result_to_dict(result)

    # =========================================================
    # ICD-10 Lookup
    # =========================================================

    def lookup_icd10(
        self,
        diagnosis: str,
    ) -> Dict[str, Any]:
        """
        ICD-10 lookup interface.

        This is currently a deterministic local development
        implementation.

        Later this method can be connected to:
            - ICD-10 API
            - MCP server
            - approved clinical terminology service

        We intentionally do not invent an ICD-10 code when
        one is not present in the local mapping.
        """

        if not diagnosis:
            return {
                "found": False,
                "diagnosis": "",
                "icd10_code": None,
                "source": "local_development_mapping",
            }

        normalized = (
            str(diagnosis)
            .strip()
            .lower()
        )

        local_mapping = {
            "type 2 diabetes": "E11.9",
            "diabetes mellitus type 2": "E11.9",
            "hypertension": "I10",
            "essential hypertension": "I10",
            "appendicitis": "K35.80",
            "cataract": "H26.9",
            "acute myocardial infarction": "I21.9",
            "myocardial infarction": "I21.9",
        }

        code = local_mapping.get(
            normalized
        )

        return {
            "found": code is not None,
            "diagnosis": diagnosis,
            "icd10_code": code,
            "source": "local_development_mapping",
        }

    # =========================================================
    # Clinical Alignment Tool
    # =========================================================

    def check_clinical_alignment(
        self,
        diagnosis: str,
        treatment: str,
    ) -> Dict[str, Any]:
        """
        Basic deterministic clinical alignment check.

        This is only a screening layer.

        Production implementation should use an approved
        ICD-10/clinical terminology service.
        """

        if not diagnosis or not treatment:
            return {
                "aligned": None,
                "reason": (
                    "Diagnosis and treatment are required."
                ),
            }

        diagnosis_normalized = (
            diagnosis.strip().lower()
        )

        treatment_normalized = (
            treatment.strip().lower()
        )

        known_alignments = {
            "appendicitis": [
                "appendectomy",
                "laparoscopic appendectomy",
                "antibiotic",
                "surgery",
            ],
            "cataract": [
                "cataract surgery",
                "phacoemulsification",
                "lens replacement",
            ],
            "hypertension": [
                "antihypertensive",
                "blood pressure",
                "medication",
            ],
            "type 2 diabetes": [
                "insulin",
                "metformin",
                "glucose",
                "diabetes medication",
            ],
        }

        expected_treatments = known_alignments.get(
            diagnosis_normalized
        )

        if expected_treatments is None:
            return {
                "aligned": None,
                "reason": (
                    "No local clinical mapping is available; "
                    "external ICD-10/clinical validation required."
                ),
            }

        for expected in expected_treatments:
            if expected in treatment_normalized:
                return {
                    "aligned": True,
                    "reason": (
                        "Treatment is consistent with "
                        "the configured clinical mapping."
                    ),
                }

        return {
            "aligned": False,
            "reason": (
                "Treatment does not match the configured "
                "clinical mapping for the diagnosis."
            ),
        }

    # =========================================================
    # Tool Registry
    # =========================================================

    def get_tool_registry(self) -> Dict[str, Any]:
        """
        Return the tools available to the claim agent.

        This registry will later be usable by either:
            - Function calling
            - MCP
            - LangChain tools
        """

        return {
            "calculate_room_rent": (
                self.calculate_room_rent
            ),
            "calculate_proportional_deduction": (
                self.calculate_proportional_deduction
            ),
            "check_sum_insured": (
                self.check_sum_insured
            ),
            "check_non_payable_item": (
                self.check_non_payable_item
            ),
            "calculate_non_payable_deductions": (
                self.calculate_non_payable_deductions
            ),
            "check_waiting_period": (
                self.check_waiting_period
            ),
            "calculate_final_payable": (
                self.calculate_final_payable
            ),
            "lookup_icd10": (
                self.lookup_icd10
            ),
            "check_clinical_alignment": (
                self.check_clinical_alignment
            ),
        }

    # =========================================================
    # Serialization helper
    # =========================================================

    @staticmethod
    def _rule_result_to_dict(
        result: Any,
    ) -> Dict[str, Any]:
        """
        Convert a Pydantic RuleResult into a plain dictionary.

        Supports both Pydantic v1 and v2 style serialization.
        """

        if hasattr(
            result,
            "dict",
        ):
            return result.dict()

        if hasattr(
            result,
            "model_dump",
        ):
            return result.model_dump()

        if isinstance(
            result,
            dict,
        ):
            return result

        return {
            "result": result
        }