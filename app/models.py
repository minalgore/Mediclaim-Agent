from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL_APPROVAL = "PARTIAL_APPROVAL"
    REJECTED = "REJECTED"
    QUERY_RAISED = "QUERY_RAISED"


class FraudRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyCitation(BaseModel):
    clause_id: str
    source: str
    page: Optional[int] = None
    content: Optional[str] = None


class ApprovedAmountBreakdown(BaseModel):
    base_room: float = 0.0
    surgeon_fees: float = 0.0
    diagnostics: float = 0.0
    consumables_deductions: float = 0.0


class AdjudicationOutput(BaseModel):
    claim_id: str
    claim_status: ClaimStatus

    claimed_amount: float = Field(ge=0)
    approved_amount: float = Field(ge=0)
    remaining_sum_insured: float = Field(ge=0)

    approved_amount_breakdown: ApprovedAmountBreakdown

    policy_clause_citations: List[PolicyCitation] = Field(
        default_factory=list
    )

    fraud_risk: FraudRisk

    anomaly_flags: List[str] = Field(
        default_factory=list
    )

    requires_human_review: bool = False

    query_reasons: List[str] = Field(
        default_factory=list
    )

    explanation: str = ""


class RedactionResult(BaseModel):
    text: str

    token_map: Dict[str, str] = Field(
        default_factory=dict
    )

    redaction_count: int = 0

class DocumentProcessingResult(BaseModel):
    """
    Result returned after processing a medical document.
    """

    filename: str
    document_type: str
    extracted_text: str
    sanitized_text: str
    detected_entities: List[Dict[str, Any]] = Field(
        default_factory=list
    )
    redaction_count: int = 0

class RuleResult(BaseModel):
    approved_amount: float = 0.0
    allowed_room_rent: float = 0.0
    deduction: float = 0.0
    payable: float = 0.0

    applicable: bool = False
    eligible: bool = True
    is_non_payable: bool = False

    reason: str = ""


class FraudResult(BaseModel):
    risk_score: float = 0.0
    risk_level: FraudRisk = FraudRisk.LOW

    anomaly_flags: List[str] = Field(
        default_factory=list
    )

    requires_human_review: bool = False


class ClaimRequest(BaseModel):
    claim_id: str
    policy_id: str
    policyholder_id: str

    policy_type: str = "INDIVIDUAL_HEALTH"

    sum_insured: float = Field(ge=0)
    remaining_sum_insured: float = Field(ge=0)
    claimed_amount: float = Field(ge=0)

    diagnosis: str = ""
    treatment: str = ""

    documents: List[str] = Field(
        default_factory=list
    )

    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    lab_test_date: Optional[str] = None

    policy_start_date: Optional[str] = None
    treatment_date: Optional[str] = None

    waiting_period_years: Optional[int] = None

    selected_room_rent: Optional[float] = None

    surgeon_fees: float = 0.0
    diagnostics: float = 0.0
    consumables: float = 0.0

    bill_items: List[Dict[str, Any]] = Field(
        default_factory=list
    )