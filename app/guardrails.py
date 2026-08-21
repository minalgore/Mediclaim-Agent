from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class AmountBreakdown(BaseModel):
    """
    Approved amount breakdown for a claim.
    """

    base_room: float = Field(
        default=0.0,
        ge=0.0,
    )

    surgeon_fees: float = Field(
        default=0.0,
        ge=0.0,
    )

    diagnostics: float = Field(
        default=0.0,
        ge=0.0,
    )

    consumables_deductions: float = Field(
        default=0.0,
        ge=0.0,
    )

    other_deductions: float = Field(
        default=0.0,
        ge=0.0,
    )

    approved_amount: float = Field(
        default=0.0,
        ge=0.0,
    )


class FraudAssessment(BaseModel):
    """
    Fraud/anomaly assessment.
    """

    risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )

    risk_level: str = "LOW"

    anomaly_flags: List[str] = Field(
        default_factory=list,
    )

    requires_human_review: bool = False

    @validator("risk_level")
    def validate_risk_level(
        cls,
        value: str,
    ) -> str:

        allowed = {
            "LOW",
            "MEDIUM",
            "HIGH",
        }

        value = str(value).upper()

        if value not in allowed:
            raise ValueError(
                "risk_level must be LOW, MEDIUM or HIGH"
            )

        return value


class AdjudicationOutput(BaseModel):
    """
    Strict final claim adjudication schema.

    This is the contract between the adjudication engine
    and downstream consumers such as APIs, dashboards,
    claim systems and human reviewers.
    """

    claim_id: str

    claim_status: str

    claimed_amount: float = Field(
        default=0.0,
        ge=0.0,
    )

    approved_amount: float = Field(
        default=0.0,
        ge=0.0,
    )

    amount_breakdown: AmountBreakdown

    policy_clause_citations: List[str] = Field(
        default_factory=list,
    )

    deduction_reasons: List[str] = Field(
        default_factory=list,
    )

    fraud_assessment: FraudAssessment

    query_reasons: List[str] = Field(
        default_factory=list,
    )

    guardrail_flags: List[str] = Field(
        default_factory=list,
    )

    @validator("claim_status")
    def validate_claim_status(
        cls,
        value: str,
    ) -> str:

        allowed = {
            "APPROVED",
            "PARTIAL_APPROVAL",
            "REJECTED",
            "QUERY_RAISED",
        }

        value = str(value).upper()

        if value not in allowed:
            raise ValueError(
                "Invalid claim status: {}".format(
                    value
                )
            )

        return value

    @validator("approved_amount")
    def validate_approved_amount(
        cls,
        value: float,
        values: Dict[str, Any],
    ) -> float:

        claimed_amount = values.get(
            "claimed_amount"
        )

        if (
            claimed_amount is not None
            and value > claimed_amount
        ):
            raise ValueError(
                "Approved amount cannot exceed "
                "claimed amount."
            )

        return value


class GuardrailViolation(Exception):
    """
    Raised when a deterministic guardrail is violated.
    """

    pass


class ClaimGuardrails:
    """
    Deterministic validation and safety layer.

    The LLM/agent is never trusted to enforce financial
    constraints by itself.

    This class validates:
        - Claim status
        - Non-negative amounts
        - Approved amount <= claimed amount
        - Approved amount <= remaining Sum Insured
        - Fraud risk score
        - Required policy evidence
    """

    def __init__(
        self,
        strict_policy_citation: bool = True,
    ):
        self.strict_policy_citation = (
            strict_policy_citation
        )

    # =========================================================
    # Main validation
    # =========================================================

    def validate(
        self,
        result: Dict[str, Any],
        remaining_sum_insured: Optional[float] = None,
    ) -> AdjudicationOutput:
        """
        Validate and normalize a proposed adjudication result.
        """

        if not isinstance(
            result,
            dict,
        ):
            raise GuardrailViolation(
                "Adjudication result must be a dictionary."
            )

        normalized = dict(result)

        # -----------------------------------------------------
        # Financial validation
        # -----------------------------------------------------

        self._validate_financial_values(
            normalized
        )

        # -----------------------------------------------------
        # Sum Insured guardrail
        # -----------------------------------------------------

        if remaining_sum_insured is not None:

            self._validate_sum_insured(
                normalized,
                remaining_sum_insured,
            )

        # -----------------------------------------------------
        # Policy citation guardrail
        # -----------------------------------------------------

        self._validate_policy_citations(
            normalized
        )

        # -----------------------------------------------------
        # Fraud validation
        # -----------------------------------------------------

        self._validate_fraud_assessment(
            normalized
        )

        # -----------------------------------------------------
        # Build strict Pydantic output
        # -----------------------------------------------------

        try:
            output = AdjudicationOutput(
                **normalized
            )
        except Exception as exc:
            raise GuardrailViolation(
                "Output schema validation failed: {}".format(
                    exc
                )
            )

        # -----------------------------------------------------
        # Final consistency checks
        # -----------------------------------------------------

        self._validate_status_consistency(
            output
        )

        return output

    # =========================================================
    # Financial validation
    # =========================================================

    def _validate_financial_values(
        self,
        result: Dict[str, Any],
    ) -> None:

        numeric_fields = [
            "claimed_amount",
            "approved_amount",
        ]

        for field_name in numeric_fields:

            value = result.get(
                field_name,
                0.0,
            )

            try:
                value = float(value)
            except (
                TypeError,
                ValueError,
            ):
                raise GuardrailViolation(
                    "{} must be numeric."
                    .format(field_name)
                )

            if value < 0:
                raise GuardrailViolation(
                    "{} cannot be negative."
                    .format(field_name)
                )

            result[field_name] = value

        claimed_amount = result.get(
            "claimed_amount",
            0.0,
        )

        approved_amount = result.get(
            "approved_amount",
            0.0,
        )

        if approved_amount > claimed_amount:
            raise GuardrailViolation(
                "Approved amount cannot exceed "
                "claimed amount."
            )

    # =========================================================
    # Sum Insured validation
    # =========================================================

    def _validate_sum_insured(
        self,
        result: Dict[str, Any],
        remaining_sum_insured: float,
    ) -> None:

        try:
            remaining = float(
                remaining_sum_insured
            )
        except (
            TypeError,
            ValueError,
        ):
            raise GuardrailViolation(
                "remaining_sum_insured must be numeric."
            )

        if remaining < 0:
            raise GuardrailViolation(
                "remaining_sum_insured cannot be negative."
            )

        approved_amount = float(
            result.get(
                "approved_amount",
                0.0,
            )
        )

        if approved_amount > remaining:

            result["approved_amount"] = (
                remaining
            )

            flags = result.setdefault(
                "guardrail_flags",
                [],
            )

            flags.append(
                "SUM_INSURED_LIMIT_ENFORCED"
            )

    # =========================================================
    # Policy citation validation
    # =========================================================

    def _validate_policy_citations(
        self,
        result: Dict[str, Any],
    ) -> None:

        status = str(
            result.get(
                "claim_status",
                "",
            )
        ).upper()

        citations = result.get(
            "policy_clause_citations",
            [],
        )

        if citations is None:
            citations = []

        if not isinstance(
            citations,
            list,
        ):
            raise GuardrailViolation(
                "policy_clause_citations must be a list."
            )

        # A rejection or partial approval must have
        # a policy basis.
        if (
            self.strict_policy_citation
            and status in {
                "REJECTED",
                "PARTIAL_APPROVAL",
            }
            and not citations
        ):
            raise GuardrailViolation(
                "Policy clause citation is required "
                "for REJECTED or PARTIAL_APPROVAL claims."
            )

    # =========================================================
    # Fraud validation
    # =========================================================

    def _validate_fraud_assessment(
        self,
        result: Dict[str, Any],
    ) -> None:

        fraud = result.get(
            "fraud_assessment"
        )

        if not isinstance(
            fraud,
            dict,
        ):
            raise GuardrailViolation(
                "fraud_assessment must be a dictionary."
            )

        risk_score = fraud.get(
            "risk_score",
            0.0,
        )

        try:
            risk_score = float(
                risk_score
            )
        except (
            TypeError,
            ValueError,
        ):
            raise GuardrailViolation(
                "Fraud risk score must be numeric."
            )

        if not 0.0 <= risk_score <= 100.0:
            raise GuardrailViolation(
                "Fraud risk score must be between 0 and 100."
            )

        risk_level = str(
            fraud.get(
                "risk_level",
                "LOW",
            )
        ).upper()

        if risk_level not in {
            "LOW",
            "MEDIUM",
            "HIGH",
        }:
            raise GuardrailViolation(
                "Fraud risk level must be LOW, "
                "MEDIUM or HIGH."
            )

        fraud["risk_score"] = risk_score
        fraud["risk_level"] = risk_level

    # =========================================================
    # Status consistency
    # =========================================================

    def _validate_status_consistency(
        self,
        output: AdjudicationOutput,
    ) -> None:

        status = output.claim_status

        if (
            status == "APPROVED"
            and output.approved_amount <= 0
            and output.claimed_amount > 0
        ):
            raise GuardrailViolation(
                "APPROVED claim must have a positive "
                "approved amount."
            )

        if (
            status == "REJECTED"
            and output.approved_amount != 0
        ):
            raise GuardrailViolation(
                "REJECTED claim must have zero "
                "approved amount."
            )

        if (
            status == "QUERY_RAISED"
            and not output.query_reasons
        ):
            raise GuardrailViolation(
                "QUERY_RAISED claim must include "
                "query_reasons."
            )

    # =========================================================
    # Safe JSON conversion
    # =========================================================

    @staticmethod
    def to_dict(
        output: AdjudicationOutput,
    ) -> Dict[str, Any]:
        """
        Convert validated output to a dictionary.

        Supports Pydantic v1 and v2.
        """

        if hasattr(
            output,
            "model_dump",
        ):
            return output.model_dump()

        return output.dict()

    @staticmethod
    def to_json(
        output: AdjudicationOutput,
    ) -> str:
        """
        Convert validated output to JSON.
        """

        return output.json()