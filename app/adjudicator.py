"""
Claim adjudication orchestration.

Combines rule-engine results, fraud assessment, policy evidence,
and claim information into a final adjudication result.
"""

from typing import Any, Dict, List


class Adjudicator:
    """
    Converts rule-engine and fraud-detection results into a
    final claim adjudication decision.
    """

    def __init__(
        self,
        claim_agent: Any = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the adjudicator.

        The ClaimAgent is used to persist sanitized claim
        information into long-term memory after adjudication.
        """

        self.claim_agent = claim_agent

    # =========================================================
    # Main adjudication
    # =========================================================

    def adjudicate(
        self,
        claim: Dict[str, Any],
        rule_results: Dict[str, Any],
        fraud_result: Dict[str, Any] = None,
        policy_evidence: Any = None,
    ) -> Dict[str, Any]:
        """
        Produce the final claim adjudication result.
        """

        if fraud_result is None:
            fraud_result = {}

        if rule_results is None:
            rule_results = {}

        # -----------------------------------------------------
        # Basic claim values
        # -----------------------------------------------------

        claimed_amount = self._to_float(
            claim.get(
                "claimed_amount",
                0.0,
            )
        )

        # -----------------------------------------------------
        # Rule results
        # -----------------------------------------------------

        room_rent = rule_results.get(
            "room_rent",
            {},
        )

        sum_insured = rule_results.get(
            "sum_insured",
            {},
        )

        non_payable = rule_results.get(
            "non_payable_items",
            {},
        )

        waiting_period = rule_results.get(
            "waiting_period",
            {},
        )

        clinical_alignment = rule_results.get(
            "clinical_alignment",
            {},
        )

        final_payable = rule_results.get(
            "final_payable",
            {},
        )

        # -----------------------------------------------------
        # Normalize rule results
        # -----------------------------------------------------

        if not isinstance(room_rent, dict):
            room_rent = {}

        if not isinstance(sum_insured, dict):
            sum_insured = {}

        if not isinstance(non_payable, dict):
            non_payable = {}

        if not isinstance(waiting_period, dict):
            waiting_period = {}

        if not isinstance(clinical_alignment, dict):
            clinical_alignment = {}

        if not isinstance(final_payable, dict):
            final_payable = {}

        # -----------------------------------------------------
        # Deductions
        # -----------------------------------------------------

        room_deduction = self._to_float(
            room_rent.get(
                "deduction",
                0.0,
            )
        )

        non_payable_deduction = self._to_float(
            non_payable.get(
                "deduction",
                0.0,
            )
        )

        sum_insured_deduction = self._to_float(
            sum_insured.get(
                "deduction",
                0.0,
            )
        )

        total_deductions = (
            room_deduction
            + non_payable_deduction
            + sum_insured_deduction
        )

        # -----------------------------------------------------
        # Calculate approved amount
        # -----------------------------------------------------

        if final_payable:
            approved_amount = self._to_float(
                final_payable.get(
                    "payable_amount",
                    final_payable.get(
                        "approved_amount",
                        0.0,
                    ),
                )
            )

        else:
            approved_amount = max(
                claimed_amount
                - total_deductions,
                0.0,
            )

        # Never negative.
        approved_amount = max(
            approved_amount,
            0.0,
        )

        # Never exceed claimed amount.
        approved_amount = min(
            approved_amount,
            claimed_amount,
        )

        # -----------------------------------------------------
        # Determine status
        # -----------------------------------------------------

        claim_status = self._determine_status(
            claim=claim,
            claimed_amount=claimed_amount,
            approved_amount=approved_amount,
            waiting_period=waiting_period,
            clinical_alignment=clinical_alignment,
            fraud_result=fraud_result,
            rule_results=rule_results,
        )

        # -----------------------------------------------------
        # REJECTED claims must have zero approved amount
        # -----------------------------------------------------

        if claim_status == "REJECTED":
            approved_amount = 0.0

        # -----------------------------------------------------
        # Build amount breakdown
        # -----------------------------------------------------

        amount_breakdown = self._build_amount_breakdown(
            claim=claim,
            approved_amount=approved_amount,
            room_deduction=room_deduction,
            non_payable_deduction=non_payable_deduction,
            total_deductions=total_deductions,
        )

        # -----------------------------------------------------
        # Policy citations
        # -----------------------------------------------------

        policy_citations = self._extract_policy_citations(
            policy_evidence=policy_evidence,
            claim_status=claim_status,
            waiting_period=waiting_period,
            room_deduction=room_deduction,
            non_payable_deduction=non_payable_deduction,
        )

        # -----------------------------------------------------
        # Deduction reasons
        # -----------------------------------------------------

        deduction_reasons = self._build_deduction_reasons(
            room_deduction=room_deduction,
            non_payable_deduction=non_payable_deduction,
            sum_insured_deduction=sum_insured_deduction,
            waiting_period=waiting_period,
            clinical_alignment=clinical_alignment,
        )

        # -----------------------------------------------------
        # Query reasons
        # -----------------------------------------------------

        query_reasons = self._build_query_reasons(
            claim=claim,
            rule_results=rule_results,
            fraud_result=fraud_result,
        )

        # -----------------------------------------------------
        # Guardrail flags
        # -----------------------------------------------------

        guardrail_flags: List[str] = []

        if approved_amount > claimed_amount:
            guardrail_flags.append(
                "APPROVED_AMOUNT_CAPPED_TO_CLAIMED_AMOUNT"
            )

        if (
            claim_status == "REJECTED"
            and approved_amount != 0
        ):
            approved_amount = 0.0
            guardrail_flags.append(
                "REJECTED_AMOUNT_FORCED_TO_ZERO"
            )

        # -----------------------------------------------------
        # Final result
        # -----------------------------------------------------

        final_result = {
            "claim_id": str(
                claim.get(
                    "claim_id",
                    "",
                )
            ),
            "claim_status": claim_status,
            "claimed_amount": claimed_amount,
            "approved_amount": approved_amount,
            "amount_breakdown": amount_breakdown,
            "policy_clause_citations": policy_citations,
            "deduction_reasons": deduction_reasons,
            "fraud_assessment": self._normalize_fraud_result(
                fraud_result
            ),
            "query_reasons": query_reasons,
            "guardrail_flags": guardrail_flags,
        }

        # -----------------------------------------------------
        # Persist sanitized claim memory
        # -----------------------------------------------------

        if self.claim_agent is not None:
            try:
                self.claim_agent.update_memory(
                    claim,
                    final_result,
                )

                print(
                    "[MEMORY] Claim successfully stored:"
                    f" {claim.get('claim_id')}"
                )

            except Exception as exc:
                print(
                    "[MEMORY] Failed to update memory:"
                    f" {exc}"
                )

        return final_result
    # =========================================================
    # Status determination
    # =========================================================

    def _determine_status(
        self,
        claim: Dict[str, Any],
        claimed_amount: float,
        approved_amount: float,
        waiting_period: Dict[str, Any],
        clinical_alignment: Dict[str, Any],
        fraud_result: Dict[str, Any],
        rule_results: Dict[str, Any],
    ) -> str:

        # -----------------------------------------------------
        # Missing mandatory information
        # -----------------------------------------------------

        if self._claim_requires_query(
            claim,
            rule_results,
        ):
            return "QUERY_RAISED"

        # -----------------------------------------------------
        # Waiting period
        # -----------------------------------------------------

        waiting_eligible = waiting_period.get(
            "eligible"
        )

        if waiting_eligible is False:
            return "REJECTED"

        # -----------------------------------------------------
        # Clinical inconsistency
        # -----------------------------------------------------

        clinically_aligned = clinical_alignment.get(
            "aligned"
        )

        if clinically_aligned is False:
            return "QUERY_RAISED"

        # -----------------------------------------------------
        # Fraud review
        # -----------------------------------------------------

        fraud_level = fraud_result.get(
            "risk_level",
            "LOW",
        )

        if hasattr(
            fraud_level,
            "value",
        ):
            fraud_level = fraud_level.value

        fraud_level = str(
            fraud_level
        ).upper()

        requires_human_review = fraud_result.get(
            "requires_human_review",
            False,
        )

        if (
            fraud_level == "HIGH"
            or requires_human_review
        ):
            return "QUERY_RAISED"

        # -----------------------------------------------------
        # No payable amount
        # -----------------------------------------------------

        if (
            claimed_amount > 0
            and approved_amount <= 0
        ):
            return "REJECTED"

        # -----------------------------------------------------
        # Full approval
        # -----------------------------------------------------

        if (
            approved_amount >= claimed_amount
            and claimed_amount > 0
        ):
            return "APPROVED"

        # -----------------------------------------------------
        # Partial approval
        # -----------------------------------------------------

        if (
            approved_amount > 0
            and approved_amount < claimed_amount
        ):
            return "PARTIAL_APPROVAL"

        return "QUERY_RAISED"

    # =========================================================
    # Mandatory input checks
    # =========================================================

    @staticmethod
    def _claim_requires_query(
        claim: Dict[str, Any],
        rule_results: Dict[str, Any],
    ) -> bool:

        required_fields = [
            "claim_id",
            "policy_id",
            "policyholder_id",
            "diagnosis",
            "treatment",
            "sum_insured",
            "remaining_sum_insured",
            "selected_room_rent",
            "claimed_amount",
            "policy_start_date",
            "treatment_date",
            "bill_items",
        ]

        for field in required_fields:

            value = claim.get(field)

            if value is None:
                return True

            if (
                isinstance(value, str)
                and not value.strip()
            ):
                return True

            if field == "bill_items":
                if not isinstance(value, list) or not value:
                    return True

        # Waiting-period result must be a dictionary
        # if the rule was executed.

        if "waiting_period" in rule_results:

            waiting_result = rule_results.get(
                "waiting_period"
            )

            if not isinstance(
                waiting_result,
                dict,
            ):
                return True

        return False

    # =========================================================
    # Amount breakdown
    # =========================================================

    def _build_amount_breakdown(
        self,
        claim: Dict[str, Any],
        approved_amount: float,
        room_deduction: float,
        non_payable_deduction: float,
        total_deductions: float,
    ) -> Dict[str, float]:

        selected_room_rent = self._to_float(
            claim.get(
                "selected_room_rent",
                0.0,
            )
        )

        return {
            "base_room": selected_room_rent,
            "surgeon_fees": 0.0,
            "diagnostics": 0.0,
            "consumables_deductions": non_payable_deduction,
            "other_deductions": max(
                total_deductions
                - room_deduction
                - non_payable_deduction,
                0.0,
            ),
            "approved_amount": approved_amount,
        }

    # =========================================================
    # Policy citations
    # =========================================================

    def _extract_policy_citations(
        self,
        policy_evidence: Any,
        claim_status: str,
        waiting_period: Dict[str, Any],
        room_deduction: float,
        non_payable_deduction: float,
    ) -> List[str]:

        citations: List[str] = []

        # Preserve policy evidence citations when available.

        if isinstance(
            policy_evidence,
            list,
        ):
            for item in policy_evidence:

                if isinstance(
                    item,
                    str,
                ):
                    if item not in citations:
                        citations.append(item)

                elif isinstance(
                    item,
                    dict,
                ):
                    value = (
                        item.get("id")
                        or item.get("clause_id")
                        or item.get("citation")
                    )

                    if value and value not in citations:
                        citations.append(
                            str(value)
                        )

        elif isinstance(
            policy_evidence,
            dict,
        ):
            value = (
                policy_evidence.get("id")
                or policy_evidence.get("clause_id")
                or policy_evidence.get("citation")
            )

            if value:
                citations.append(
                    str(value)
                )

        # Waiting period citation.

        if waiting_period.get("eligible") is False:
            if "WAITING_PERIOD" not in citations:
                citations.append(
                    "WAITING_PERIOD"
                )

        # Room rent citation.

        if room_deduction > 0:
            if "ROOM_RENT_LIMIT" not in citations:
                citations.append(
                    "ROOM_RENT_LIMIT"
                )

        # Non-payable citation.

        if non_payable_deduction > 0:
            if "NON_PAYABLE_ITEMS" not in citations:
                citations.append(
                    "NON_PAYABLE_ITEMS"
                )

        return citations

    # =========================================================
    # Deduction reasons
    # =========================================================

    def _build_deduction_reasons(
        self,
        room_deduction: float,
        non_payable_deduction: float,
        sum_insured_deduction: float,
        waiting_period: Dict[str, Any],
        clinical_alignment: Dict[str, Any],
    ) -> List[str]:

        reasons: List[str] = []

        if room_deduction > 0:
            reasons.append(
                "Room rent exceeded the eligible room rent "
                "limit; applicable deduction applied."
            )

        if non_payable_deduction > 0:
            reasons.append(
                "Non-payable bill items were deducted "
                "according to applicable policy terms."
            )

        if sum_insured_deduction > 0:
            reasons.append(
                "Amount was limited by the available "
                "Sum Insured."
            )

        if waiting_period.get("eligible") is False:
            reasons.append(
                "Treatment falls within the applicable "
                "waiting period."
            )

        if clinical_alignment.get("aligned") is False:
            reasons.append(
                "Clinical information requires review."
            )

        return reasons

    
    # =========================================================
    # Query reasons
    # =========================================================

    def _build_query_reasons(
        self,
        claim: Dict[str, Any],
        rule_results: Dict[str, Any],
        fraud_result: Dict[str, Any],
    ) -> List[str]:

        reasons: List[str] = []

        # -----------------------------------------------------
        # Missing mandatory fields
        # -----------------------------------------------------

        required_fields = [
            "claim_id",
            "policy_id",
            "policyholder_id",
            "diagnosis",
            "treatment",
            "sum_insured",
            "remaining_sum_insured",
            "selected_room_rent",
            "claimed_amount",
            "policy_start_date",
            "treatment_date",
            "bill_items",
        ]

        missing_fields: List[str] = []

        for field in required_fields:

            value = claim.get(field)

            if value is None:
                missing_fields.append(field)

            elif (
                isinstance(value, str)
                and not value.strip()
            ):
                missing_fields.append(field)

            elif field == "bill_items":
                if not isinstance(value, list) or not value:
                    missing_fields.append(field)

        if missing_fields:
            reasons.append(
                "Missing mandatory claim information: "
                + ", ".join(missing_fields)
            )

        # -----------------------------------------------------
        # Clinical review
        # -----------------------------------------------------

        clinical_alignment = rule_results.get(
            "clinical_alignment",
            {},
        )

        if isinstance(
            clinical_alignment,
            dict,
        ):
            if clinical_alignment.get(
                "aligned"
            ) is False:
                reasons.append(
                    "Clinical diagnosis and treatment "
                    "require review."
                )

        # -----------------------------------------------------
        # Fraud review
        # -----------------------------------------------------

        if not isinstance(
            fraud_result,
            dict,
        ):
            fraud_result = {}

        fraud_level = fraud_result.get(
            "risk_level",
            "LOW",
        )

        # Handle Enum values such as FraudRisk.HIGH
        if hasattr(
            fraud_level,
            "value",
        ):
            fraud_level = fraud_level.value

        fraud_level = str(
            fraud_level
        ).upper()

        requires_human_review = fraud_result.get(
            "requires_human_review",
            False,
        )

        if (
            fraud_level == "HIGH"
            or requires_human_review
        ):
            reasons.append(
                "High fraud risk requires human review."
            )

        # -----------------------------------------------------
        # Fraud anomaly details
        # -----------------------------------------------------

        anomaly_flags = fraud_result.get(
            "anomaly_flags",
            [],
        )

        if not isinstance(
            anomaly_flags,
            list,
        ):
            anomaly_flags = [
                str(anomaly_flags)
            ]

        for flag in anomaly_flags:
            if flag:
                reasons.append(
                    str(flag)
                )

        return reasons

    # =========================================================
    # Fraud normalization
    # =========================================================

    def _normalize_fraud_result(
        self,
        fraud_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(
            fraud_result,
            dict,
        ):
            fraud_result = {}

        risk_score = self._to_float(
            fraud_result.get(
                "risk_score",
                0.0,
            )
        )

        risk_level = str(
            fraud_result.get(
                "risk_level",
                "LOW",
            )
        ).upper()

        anomaly_flags = fraud_result.get(
            "anomaly_flags",
            [],
        )

        if not isinstance(
            anomaly_flags,
            list,
        ):
            anomaly_flags = [
                str(anomaly_flags)
            ]

        requires_human_review = fraud_result.get(
            "requires_human_review",
            False,
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "anomaly_flags": anomaly_flags,
            "requires_human_review": bool(
                requires_human_review
            ),
        }

    # =========================================================
    # Utility
    # =========================================================

    @staticmethod
    def _to_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        if value is None:
            return default

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default