from typing import Any, Dict, List, Optional

from app.document_processor import DocumentProcessor
from app.fraud_detector import FraudDetector
from app.memory import ClaimMemory
from app.pii_redactor import PIIRedactor
from app.policy_rag import PolicyRAG
from app.tools import ClaimTools


class ClaimAgent:
    """
    Main claim adjudication orchestration layer.

    Responsibilities:

        1. Sanitize sensitive information.
        2. Process claim/document input.
        3. Retrieve relevant policy evidence.
        4. Retrieve policyholder claim history.
        5. Run deterministic claim tools.
        6. Run fraud/anomaly detection.
        7. Produce an intermediate adjudication context.

    The class intentionally does not make a final approval/rejection
    decision. Final decision logic belongs to Adjudicator and
    Guardrails.
    """

    def __init__(
        self,
        pii_redactor: Optional[PIIRedactor] = None,
        document_processor: Optional[DocumentProcessor] = None,
        policy_rag: Optional[PolicyRAG] = None,
        memory: Optional[ClaimMemory] = None,
        tools: Optional[ClaimTools] = None,
        fraud_detector: Optional[FraudDetector] = None,
    ):
        self.pii_redactor = (
            pii_redactor
            if pii_redactor is not None
            else PIIRedactor()
        )

        self.document_processor = (
            document_processor
            if document_processor is not None
            else DocumentProcessor()
        )

        self.policy_rag = (
            policy_rag
            if policy_rag is not None
            else PolicyRAG()
        )

        self.memory = (
            memory
            if memory is not None
            else ClaimMemory()
        )

        self.tools = (
            tools
            if tools is not None
            else ClaimTools()
        )

        self.fraud_detector = (
            fraud_detector
            if fraud_detector is not None
            else FraudDetector()
        )

    # =========================================================
    # Main claim processing method
    # =========================================================

    def process_claim(
        self,
        claim: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process a claim through the adjudication pipeline.

        The returned dictionary is an intermediate claim context.
        It is not yet the final validated adjudication response.
        """

        if not isinstance(
            claim,
            dict,
        ):
            raise TypeError(
                "claim must be a dictionary"
            )

        claim_id = str(
            claim.get(
                "claim_id",
                "",
            )
        )

        policyholder_id = str(
            claim.get(
                "policyholder_id",
                "",
            )
        )

        # -----------------------------------------------------
        # Step 1: Sanitize claim
        # -----------------------------------------------------

        sanitized_claim = self._sanitize_claim(
            claim
        )

        # -----------------------------------------------------
        # Step 2: Retrieve policy evidence
        # -----------------------------------------------------

        policy_evidence = (
            self._retrieve_policy_evidence(
                sanitized_claim
            )
        )

        # -----------------------------------------------------
        # Step 3: Retrieve memory
        # -----------------------------------------------------

        claim_history = self._retrieve_memory(
            policyholder_id
        )

        # -----------------------------------------------------
        # Step 4: Run deterministic rules
        # -----------------------------------------------------

        rule_results = (
            self._run_rule_checks(
                sanitized_claim
            )
        )

        # -----------------------------------------------------
        # Step 5: Fraud detection
        # -----------------------------------------------------

        fraud_result = (
            self.fraud_detector.analyze(
                sanitized_claim
            )
        )

        # -----------------------------------------------------
        # Step 6: Build agent context
        # -----------------------------------------------------

        return {
            "claim_id": claim_id,
            "policyholder_id": policyholder_id,
            "sanitized_claim": sanitized_claim,
            "policy_evidence": policy_evidence,
            "claim_history": claim_history,
            "rule_results": rule_results,
            "fraud_result": self._serialize(
                fraud_result
            ),
            "status": "PENDING_ADJUDICATION",
        }

    # =========================================================
    # PII sanitization
    # =========================================================

    def _sanitize_claim(
        self,
        claim: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Recursively sanitize strings inside the claim.

        This ensures that sensitive values are not passed to
        downstream RAG, memory, or LLM components.
        """

        return self._sanitize_value(
            claim
        )

    def _sanitize_value(
        self,
        value: Any,
    ) -> Any:

        if isinstance(
            value,
            str,
        ):
            result = self.pii_redactor.redact_text(
                value
            )

            return result.text

        if isinstance(
            value,
            dict,
        ):
            return {
                key: self._sanitize_value(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            list,
        ):
            return [
                self._sanitize_value(
                    item
                )
                for item in value
            ]

        return value

    # =========================================================
    # Policy RAG
    # =========================================================

    def _retrieve_policy_evidence(
        self,
        claim: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Retrieve policy clauses relevant to the claim.

        Policy type defaults to INDIVIDUAL_HEALTH.
        """

        query_parts = []

        diagnosis = claim.get(
            "diagnosis"
        )

        treatment = claim.get(
            "treatment"
        )

        claim_text = claim.get(
            "claim_text"
        )

        if diagnosis:
            query_parts.append(
                str(diagnosis)
            )

        if treatment:
            query_parts.append(
                str(treatment)
            )

        if claim_text:
            query_parts.append(
                str(claim_text)
            )

        # Add policy-relevant concepts to improve retrieval.
        query_parts.extend(
            [
                "room rent",
                "waiting period",
                "non payable items",
                "Sum Insured",
                "medical necessity",
            ]
        )

        query = " ".join(
            query_parts
        )

        if not query.strip():
            query = (
                "room rent waiting period "
                "non payable Sum Insured"
            )

        policy_type = claim.get(
            "policy_type",
            "INDIVIDUAL_HEALTH",
        )

        try:
            return self.policy_rag.retrieve(
                query,
                top_k=5,
                policy_type=policy_type,
            )
        except TypeError:
            # Compatibility fallback if the current
            # PolicyRAG implementation does not accept
            # policy_type.
            return self.policy_rag.retrieve(
                query,
                top_k=5,
            )

    # =========================================================
    # Memory retrieval
    # =========================================================

    def _retrieve_memory(
        self,
        policyholder_id: str,
        ) -> Dict[str, Any]:
        
            """
            Retrieve long-term policyholder context.
            """

            if not policyholder_id:
                return {
                    "peds": [],
                    "claims": [],
                    "policies": [],
                    "history": [],
                }

            peds = self.memory.get_peds(policyholder_id)
            claims = self.memory.get_claims(policyholder_id)
            policies = self.memory.get_policies(policyholder_id)
            history = self.memory.get_history(policyholder_id)

            # Demo/observability logging
            print(
                f"[MEMORY] Policyholder: {policyholder_id}"
            )
            print(
                f"[MEMORY] Previous claims: {len(claims)}"
            )
            print(
                f"[MEMORY] PED records: {len(peds)}"
            )
            print(
                f"[MEMORY] Policy records: {len(policies)}"
            )
            print(
                f"[MEMORY] Total history records: {len(history)}"
            )

            for claim in claims:
                print(
                    f"[MEMORY] Previous claim: "
                    f"{claim.get('data', {}).get('claim_id')}"
                )

            return {
                "peds": peds,
                "claims": claims,
                "policies": policies,
                "history": history,
            }

    # =========================================================
    # Rule checks
    # =========================================================

    def _run_rule_checks(
        self,
        claim: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute deterministic claim checks.

        Missing inputs are handled safely rather than causing
        the entire pipeline to fail.
        """

        results = {}

        # -----------------------------------------------------
        # Room rent
        # -----------------------------------------------------

        sum_insured = claim.get(
            "sum_insured"
        )

        selected_room_rent = claim.get(
            "selected_room_rent"
        )

        if (
            sum_insured is not None
            and selected_room_rent is not None
        ):
            results["room_rent"] = (
                self.tools.calculate_room_rent(
                    sum_insured=float(
                        sum_insured
                    ),
                    selected_room_rent=float(
                        selected_room_rent
                    ),
                )
            )

        # -----------------------------------------------------
        # Sum Insured
        # -----------------------------------------------------

        claimed_amount = claim.get(
            "claimed_amount"
        )

        remaining_sum_insured = claim.get(
            "remaining_sum_insured"
        )

        if (
            claimed_amount is not None
            and remaining_sum_insured is not None
        ):
            results["sum_insured"] = (
                self.tools.check_sum_insured(
                    claimed_amount=float(
                        claimed_amount
                    ),
                    remaining_sum_insured=float(
                        remaining_sum_insured
                    ),
                )
            )

        # -----------------------------------------------------
        # Non-payable items
        # -----------------------------------------------------

        bill_items = claim.get(
            "bill_items"
        )

        if isinstance(
            bill_items,
            list,
        ):
            results["non_payable_items"] = (
                self.tools.calculate_non_payable_deductions(
                    bill_items=bill_items
                )
            )

        # -----------------------------------------------------
        # Waiting period
        # -----------------------------------------------------

        policy_start_date = claim.get(
            "policy_start_date"
        )

        treatment_date = claim.get(
            "treatment_date"
        )

        waiting_period_years = claim.get(
            "waiting_period_years"
        )

        if (
            policy_start_date
            and treatment_date
        ):
            results["waiting_period"] = (
                self.tools.check_waiting_period(
                    policy_start_date=(
                        policy_start_date
                    ),
                    treatment_date=(
                        treatment_date
                    ),
                    waiting_period_years=(
                        waiting_period_years
                    ),
                )
            )

        # -----------------------------------------------------
        # ICD-10
        # -----------------------------------------------------

        diagnosis = claim.get(
            "diagnosis"
        )

        if diagnosis:
            results["icd10"] = (
                self.tools.lookup_icd10(
                    diagnosis
                )
            )

        # -----------------------------------------------------
        # Clinical alignment
        # -----------------------------------------------------

        treatment = claim.get(
            "treatment"
        )

        if diagnosis and treatment:
            results["clinical_alignment"] = (
                self.tools.check_clinical_alignment(
                    diagnosis=diagnosis,
                    treatment=treatment,
                )
            )

        # -----------------------------------------------------
        # Final calculation
        # -----------------------------------------------------

        deductions = 0.0

        if (
            "non_payable_items"
            in results
        ):
            deductions += float(
                results[
                    "non_payable_items"
                ].get(
                    "deduction",
                    0.0,
                )
            )

        if (
            "room_rent"
            in results
        ):
            deductions += float(
                results[
                    "room_rent"
                ].get(
                    "deduction",
                    0.0,
                )
            )

        if (
            claimed_amount is not None
            and remaining_sum_insured is not None
        ):
            results["final_payable"] = (
                self.tools.calculate_final_payable(
                    claimed_amount=float(
                        claimed_amount
                    ),
                    remaining_sum_insured=float(
                        remaining_sum_insured
                    ),
                    deductions=deductions,
                )
            )

        return results

    # =========================================================
    # Memory update
    # =========================================================

    def update_memory(
        self,
        claim: Dict[str, Any],
        adjudication_result: Dict[str, Any],
    ):
        """
        Update long-term memory after adjudication.

        Only sanitized claim data should be stored.
        """

        policyholder_id = str(
            claim.get(
                "policyholder_id",
                "",
            )
        )

        claim_id = str(
            claim.get(
                "claim_id",
                "",
            )
        )

        if not policyholder_id:
            return

        if not claim_id:
            return

        sanitized_claim = self._sanitize_claim(
            claim
        )

        self.memory.add_claim(
            policyholder_id=policyholder_id,
            claim_id=claim_id,
            claim_data={
                "diagnosis": sanitized_claim.get(
                    "diagnosis"
                ),
                "treatment": sanitized_claim.get(
                    "treatment"
                ),
                "claim_status": adjudication_result.get(
                    "claim_status"
                ),
                "approved_amount": adjudication_result.get(
                    "approved_amount"
                ),
            },
        )

    # =========================================================
    # Utility
    # =========================================================

    @staticmethod
    def _serialize(
        value: Any,
    ) -> Any:
        """
        Convert Pydantic objects into dictionaries where
        possible.
        """

        if isinstance(
            value,
            dict,
        ):
            return {
                key: ClaimAgent._serialize(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            list,
        ):
            return [
                ClaimAgent._serialize(
                    item
                )
                for item in value
            ]

        if hasattr(
            value,
            "model_dump",
        ):
            return value.model_dump()

        if hasattr(
            value,
            "dict",
        ):
            return value.dict()

        return value