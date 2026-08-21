from datetime import date
from typing import Any, Dict, List, Optional

from app.models import FraudResult, FraudRisk


class FraudDetector:
    """
    Deterministic fraud and anomaly detection layer.

    This component does not make a final claim decision.

    It identifies suspicious patterns and produces:
        - Risk score
        - Risk level
        - Explicit anomaly flags
        - Human-review recommendation

    The final adjudication decision is handled by Adjudicator.
    """

    # =========================================================
    # Risk thresholds
    # =========================================================

    LOW_RISK_THRESHOLD = 25
    MEDIUM_RISK_THRESHOLD = 50

    # =========================================================
    # Constructor
    # =========================================================

    def __init__(
        self,
        rules: Optional[Dict[str, Any]] = None,
    ):
        self.rules = rules or {}

    # =========================================================
    # Main fraud analysis
    # =========================================================

    def analyze(
        self,
        claim: Dict[str, Any],
    ) -> FraudResult:
        """
        Run all fraud/anomaly checks.

        Expected claim dictionary may contain:

            claim_id
            diagnosis
            treatment
            admission_date
            discharge_date
            lab_test_date
            claimed_amount
            bill_items
            procedure_items
            clinical_notes
        """

        anomaly_flags: List[str] = []
        risk_score = 0.0

        # -----------------------------------------------------
        # 1. Unbundling
        # -----------------------------------------------------

        unbundling_flags = (
            self.detect_unbundling(
                claim
            )
        )

        anomaly_flags.extend(
            unbundling_flags
        )

        risk_score += (
            len(unbundling_flags) * 20
        )

        # -----------------------------------------------------
        # 2. Timeline mismatch
        # -----------------------------------------------------

        timeline_flags = (
            self.detect_timeline_mismatch(
                claim
            )
        )

        anomaly_flags.extend(
            timeline_flags
        )

        risk_score += (
            len(timeline_flags) * 20
        )

        # -----------------------------------------------------
        # 3. Duplicate billing
        # -----------------------------------------------------

        duplicate_flags = (
            self.detect_duplicate_billing(
                claim
            )
        )

        anomaly_flags.extend(
            duplicate_flags
        )

        risk_score += (
            len(duplicate_flags) * 15
        )

        # -----------------------------------------------------
        # 4. Quantity anomalies
        # -----------------------------------------------------

        quantity_flags = (
            self.detect_quantity_anomalies(
                claim
            )
        )

        anomaly_flags.extend(
            quantity_flags
        )

        risk_score += (
            len(quantity_flags) * 10
        )

        # -----------------------------------------------------
        # 5. Clinical inconsistency
        # -----------------------------------------------------

        clinical_flags = (
            self.detect_clinical_inconsistency(
                claim
            )
        )

        anomaly_flags.extend(
            clinical_flags
        )

        risk_score += (
            len(clinical_flags) * 20
        )

        # -----------------------------------------------------
        # Clamp risk score
        # -----------------------------------------------------

        risk_score = min(
            max(risk_score, 0.0),
            100.0,
        )

        risk_level = (
            self._calculate_risk_level(
                risk_score
            )
        )

        requires_human_review = (
            risk_level == FraudRisk.HIGH
            or len(anomaly_flags) >= 2
        )

        return FraudResult(
            risk_score=risk_score,
            risk_level=risk_level,
            anomaly_flags=anomaly_flags,
            requires_human_review=(
                requires_human_review
            ),
        )

    # =========================================================
    # Unbundling detection
    # =========================================================

    def detect_unbundling(
        self,
        claim: Dict[str, Any],
    ) -> List[str]:
        """
        Detect possible unbundling of a procedure.

        A possible unbundling pattern exists when a procedure
        is billed together with separately billed procedure-
        related charges that may ordinarily be included in
        the procedure package.

        This is a screening indicator only and does not by
        itself establish fraud.
        """

        flags: List[str] = []

        bill_items = claim.get(
            "bill_items",
            [],
        )

        if not isinstance(
            bill_items,
            list,
        ):
            return flags

        procedure_keywords = {
            "surgery",
            "surgical",
            "appendectomy",
            "laparoscopic",
            "operation",
            "procedure",
            "cesarean",
            "c-section",
            "c section",
            "angioplasty",
            "cataract",
        }

        bundled_keywords = {
            "surgical tray",
            "operation theatre",
            "ot charges",
            "instrument charges",
            "procedure kit",
            "surgical kit",
            "minor surgical items",

            # Procedure-related charges that may indicate
            # possible unbundling.
            "surgical charges",
            "procedure charges",
            "operation charges",
            "operative charges",
        }

        procedures_found = []
        bundled_items_found = []

        for item in bill_items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            name = str(
                item.get(
                    "name",
                    "",
                )
            ).strip().lower()

            if not name:
                continue

            # Identify procedure-related bill items.
            for keyword in procedure_keywords:
                if keyword in name:
                    procedures_found.append(
                        name
                    )
                    break

            # Identify separately billed items that may
            # normally be included in a procedure package.
            for keyword in bundled_keywords:
                if keyword in name:
                    bundled_items_found.append(
                        name
                    )
                    break

        if (
            procedures_found
            and bundled_items_found
        ):
            flags.append(
                "POSSIBLE_UNBUNDLING: "
                "Procedure and separately billed "
                "procedure-related items detected."
            )

        return flags

    # =========================================================
    # Timeline mismatch
    # =========================================================

    def detect_timeline_mismatch(
        self,
        claim: Dict[str, Any],
    ) -> List[str]:
        """
        Detect suspicious date relationships.

        Primary check:

            Lab test date < admission date

        This can indicate:
            - OPD investigation
            - date-entry error
            - timeline inconsistency
        """

        flags: List[str] = []

        admission_date = self._parse_date(
            claim.get(
                "admission_date"
            )
        )

        lab_test_date = self._parse_date(
            claim.get(
                "lab_test_date"
            )
        )

        discharge_date = self._parse_date(
            claim.get(
                "discharge_date"
            )
        )

        treatment_date = self._parse_date(
            claim.get(
                "treatment_date"
            )
        )

        if (
            admission_date
            and lab_test_date
            and lab_test_date < admission_date
        ):
            flags.append(
                "TIMELINE_MISMATCH: "
                "Lab investigation date occurs "
                "before admission date."
            )

        if (
            admission_date
            and discharge_date
            and discharge_date < admission_date
        ):
            flags.append(
                "TIMELINE_MISMATCH: "
                "Discharge date occurs before "
                "admission date."
            )

        if (
            admission_date
            and treatment_date
            and treatment_date < admission_date
        ):
            flags.append(
                "TIMELINE_MISMATCH: "
                "Treatment date occurs before "
                "admission date."
            )

        return flags

    # =========================================================
    # Duplicate billing
    # =========================================================

    def detect_duplicate_billing(
        self,
        claim: Dict[str, Any],
    ) -> List[str]:
        """
        Detect identical bill item descriptions that appear
        multiple times with suspiciously similar amounts.
        """

        flags: List[str] = []

        bill_items = claim.get(
            "bill_items",
            [],
        )

        if not isinstance(
            bill_items,
            list,
        ):
            return flags

        seen: Dict[str, List[float]] = {}

        for item in bill_items:
            name = str(
                item.get(
                    "name",
                    ""
                )
            ).strip().lower()

            if not name:
                continue

            try:
                amount = float(
                    item.get(
                        "amount",
                        0.0
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                amount = 0.0

            if name not in seen:
                seen[name] = []

            seen[name].append(
                amount
            )

        for name, amounts in seen.items():

            if len(amounts) < 2:
                continue

            # Exact duplicate line items.
            if len(
                set(amounts)
            ) == 1:
                flags.append(
                    "DUPLICATE_BILLING: "
                    "Repeated bill item '{}' "
                    "with identical amounts."
                    .format(name)
                )

        return flags

    # =========================================================
    # Quantity anomalies
    # =========================================================

    def detect_quantity_anomalies(
        self,
        claim: Dict[str, Any],
    ) -> List[str]:
        """
        Detect unusually high quantities.

        This is a screening rule, not proof of fraud.

        Expected item format:

            {
                "name": "Syringe",
                "amount": 5000,
                "quantity": 100
            }
        """

        flags: List[str] = []

        bill_items = claim.get(
            "bill_items",
            [],
        )

        if not isinstance(
            bill_items,
            list,
        ):
            return flags

        for item in bill_items:

            quantity = item.get(
                "quantity"
            )

            if quantity is None:
                continue

            try:
                quantity = float(
                    quantity
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if quantity < 0:
                flags.append(
                    "QUANTITY_ANOMALY: "
                    "Negative quantity detected."
                )

            elif quantity > 100:
                name = str(
                    item.get(
                        "name",
                        "Unknown item"
                    )
                )

                flags.append(
                    "QUANTITY_ANOMALY: "
                    "Unusually high quantity "
                    "for '{}'."
                    .format(name)
                )

        return flags

    # =========================================================
    # Clinical inconsistency
    # =========================================================

    def detect_clinical_inconsistency(
        self,
        claim: Dict[str, Any],
    ) -> List[str]:
        """
        Detect obvious diagnosis/treatment inconsistencies.

        This is a deterministic screening rule only.
        It is not a clinical diagnosis engine and does not
        replace ICD-10 or clinician review.
        """

        flags: List[str] = []

        diagnosis = str(
            claim.get(
                "diagnosis",
                "",
            )
        ).strip().lower()

        treatment = str(
            claim.get(
                "treatment",
                "",
            )
        ).strip().lower()

        if not diagnosis or not treatment:
            return flags

        # -----------------------------------------------------
        # Clearly incompatible diagnosis/treatment pairs
        # -----------------------------------------------------

        incompatible_pairs = [
            (
                ("fracture",),
                ("cancer", "chemotherapy"),
            ),
            (
                ("cancer", "malignancy"),
                ("cataract",),
            ),
            (
                ("cataract",),
                ("chemotherapy", "appendectomy"),
            ),
            (
                ("migraine", "headache"),
                (
                    "appendectomy",
                    "laparoscopic appendectomy",
                    "cataract surgery",
                    "angioplasty",
                    "cesarean",
                    "c-section",
                ),
            ),
            (
                ("appendicitis",),
                (
                    "cataract",
                    "chemotherapy",
                    "angioplasty",
                ),
            ),
            (
                ("cataract",),
                (
                    "appendectomy",
                    "angioplasty",
                    "chemotherapy",
                ),
            ),
        ]

        for diagnosis_keywords, treatment_keywords in (
            incompatible_pairs
        ):
            diagnosis_match = any(
                keyword in diagnosis
                for keyword in diagnosis_keywords
            )

            treatment_match = any(
                keyword in treatment
                for keyword in treatment_keywords
            )

            if (
                diagnosis_match
                and treatment_match
            ):
                flags.append(
                    "CLINICAL_INCONSISTENCY: "
                    "Treatment description may not align "
                    "with the supplied diagnosis."
                )

                break

        return flags

    # =========================================================
    # Date parser
    # =========================================================

    def _parse_date(
        self,
        value: Any,
    ) -> Optional[date]:
        """
        Parse YYYY-MM-DD safely.
        """

        if not value:
            return None

        if isinstance(
            value,
            date,
        ):
            return value

        try:
            return date.fromisoformat(
                str(value)
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    # =========================================================
    # Risk calculation
    # =========================================================

    def _calculate_risk_level(
        self,
        risk_score: float,
    ) -> FraudRisk:

        if risk_score >= self.MEDIUM_RISK_THRESHOLD:
            return FraudRisk.HIGH

        if risk_score >= self.LOW_RISK_THRESHOLD:
            return FraudRisk.MEDIUM

        return FraudRisk.LOW