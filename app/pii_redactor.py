import re
import uuid
from typing import Dict, List


from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
)

from app.models import RedactionResult


class PIIRedactor:
    """
    Indian PII/PHI redaction layer.

    Detects:
        - Aadhaar numbers
        - PAN numbers
        - ABHA IDs
        - Indian phone numbers
        - Hospital IPD numbers
        - Hospital registration numbers

    Original values are stored in a local token map so that
    authorized de-anonymization can be performed later.
    """

    def __init__(self):
        self.analyzer = AnalyzerEngine()

        self._token_map: Dict[str, str] = {}

        self._register_indian_recognizers()

    # =========================================================
    # Register Indian-specific recognizers
    # =========================================================

    def _register_indian_recognizers(self):
        recognizers = [
            self._aadhaar_recognizer(),
            self._pan_recognizer(),
            self._abha_recognizer(),
            self._phone_recognizer(),
            self._ipd_recognizer(),
            self._registration_recognizer(),
        ]

        for recognizer in recognizers:
            try:
                self.analyzer.registry.add_recognizer(
                    recognizer
                )
            except Exception:
                # Prevent duplicate-registration errors
                # during application reload.
                pass

    # =========================================================
    # Aadhaar
    # =========================================================

    def _aadhaar_recognizer(self):
        pattern = Pattern(
        name="aadhaar_pattern",
        regex=(
            r"(?<![\d+])"
            r"\d{4}[- ]?\d{4}[- ]?\d{4}"
            r"(?!\d)"
        ),
        score=0.90,
    )

        return PatternRecognizer(
            supported_entity="IN_AADHAAR",
            patterns=[pattern],
        )

    # =========================================================
    # PAN
    # =========================================================

    def _pan_recognizer(self):
        """
        Indian PAN format:

            ABCDE1234F

        The regex is intentionally strict so dates such as:

            2026-08-10

        cannot be considered PAN values.
        """

        pattern = Pattern(
            name="pan_pattern",
            regex=(
                r"(?<![A-Z0-9])"
                r"[A-Z]{5}[0-9]{4}[A-Z]"
                r"(?![A-Z0-9])"
            ),
            score=0.99,
        )

        return PatternRecognizer(
            supported_entity="IN_PAN",
            patterns=[pattern],
        )

    # =========================================================
    # ABHA ID
    # =========================================================

    def _abha_recognizer(self):
        pattern = Pattern(
            name="abha_pattern",
            regex=(
                r"(?<!\d)"
                r"\d{2}-\d{4}-\d{4}-\d{4}"
                r"(?!\d)"
            ),
            score=0.99,
        )

        return PatternRecognizer(
            supported_entity="IN_ABHA",
            patterns=[pattern],
        )

    # =========================================================
    # Indian phone number
    # =========================================================

    def _phone_recognizer(self):
        pattern = Pattern(
            name="indian_phone_pattern",
            regex=(
                r"(?<!\d)"
                r"(?:\+91[\s-]?)?"
                r"[6-9]\d{9}"
                r"(?!\d)"
            ),
            score=0.95,
        )

        return PatternRecognizer(
            supported_entity="IN_PHONE",
            patterns=[pattern],
        )

    # =========================================================
    # Hospital IPD number
    # =========================================================

    def _ipd_recognizer(self):
        pattern = Pattern(
        name="ipd_pattern",
        regex=(
            r"\bIPD202\d{8}\b"
        ),
        score=0.95,
    )

        return PatternRecognizer(
        supported_entity="IN_IPD",
        patterns=[pattern],
    )
    # =========================================================
    # Hospital registration number
    # =========================================================

    def _registration_recognizer(self):
        """
        Match hospital registration identifiers when they occur
        after a registration label.
        """

        pattern = Pattern(
            name="registration_pattern",
            regex=(
                r"(?i)"
                r"(?<=Registration Number: )"
                r"[A-Z0-9][A-Z0-9/-]{2,}"
            ),
            score=0.95,
        )

        return PatternRecognizer(
            supported_entity="IN_REGISTRATION",
            patterns=[pattern],
        )

    # =========================================================
    # Redact text
    # =========================================================

    def redact_text(
        self,
        text: str,
    ) -> RedactionResult:
        """
        Detect and replace Indian PII with temporary tokens.
        """

        if not text:
            return RedactionResult(
                text="",
                token_map={},
                redaction_count=0,
            )

        entities = [
            "IN_AADHAAR",
            "IN_PAN",
            "IN_ABHA",
            "IN_PHONE",
            "IN_IPD",
            "IN_REGISTRATION",
        ]

        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=entities,
        )

        if not results:
            return RedactionResult(
                text=text,
                token_map={},
                redaction_count=0,
            )

        # -----------------------------------------------------
        # Remove false positives / unwanted entities
        # -----------------------------------------------------

        results = self._filter_results(
            text,
            results,
        )

        if not results:
            return RedactionResult(
                text=text,
                token_map={},
                redaction_count=0,
            )

        # -----------------------------------------------------
        # Remove overlapping entities
        # -----------------------------------------------------

        results = self._remove_overlapping_results(
            results
        )

        # -----------------------------------------------------
        # Replace from right to left
        # -----------------------------------------------------

        results = sorted(
            results,
            key=lambda result: result.start,
            reverse=True,
        )

        token_map: Dict[str, str] = {}

        redacted_text = text

        for result in results:

            original_value = text[
                result.start:result.end
            ]

            token = self._create_token(
                result.entity_type
            )

            token_map[token] = original_value

            redacted_text = (
                redacted_text[:result.start]
                + token
                + redacted_text[result.end:]
            )

        # Keep mapping locally.
        self._token_map.update(
            token_map
        )

        return RedactionResult(
            text=redacted_text,
            token_map=token_map,
            redaction_count=len(token_map),
        )

    # =========================================================
    # Filter false positives
    # =========================================================

    def _filter_results(
        self,
        text: str,
        results,
    ):
        """
        Remove known false positives.

        In particular:
            - dates must never be treated as PAN
            - IPD labels themselves must not be redacted
            - obvious date values are ignored
        """

        filtered = []

        for result in results:

            value = text[
                result.start:result.end
            ]

            entity_type = result.entity_type

            # -------------------------------------------------
            # Never classify date-like values as PAN
            # -------------------------------------------------

            if entity_type == "IN_PAN":

                if self._looks_like_date(
                    value
                ):
                    continue

            # -------------------------------------------------
            # IPD must be an actual value, not the label
            # -------------------------------------------------

            if entity_type == "IN_IPD":

                normalized = value.strip()

                if normalized.upper() in {
                    "IPD",
                    "IPD NO",
                    "IPD NUMBER",
                }:
                    continue

                if len(normalized) < 3:
                    continue

            # -------------------------------------------------
            # Registration must have a real value
            # -------------------------------------------------

            if entity_type == "IN_REGISTRATION":

                normalized = value.strip()

                if len(normalized) < 3:
                    continue

            filtered.append(result)

        return filtered

    # =========================================================
    # Date detection
    # =========================================================

    def _looks_like_date(
        self,
        value: str,
    ) -> bool:
        """
        Return True for common date formats.

        Examples:

            2026-08-10
            10-08-2026
            10/08/2026
            2026/08/10
        """

        value = value.strip()

        date_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",
            r"^\d{4}/\d{2}/\d{2}$",
            r"^\d{2}-\d{2}-\d{4}$",
            r"^\d{2}/\d{2}/\d{4}$",
            r"^\d{2}\.\d{2}\.\d{4}$",
        ]

        return any(
            re.fullmatch(
                pattern,
                value,
            )
            for pattern in date_patterns
        )

    # =========================================================
    # Remove overlapping results
    # =========================================================

    def _remove_overlapping_results(
        self,
        results,
    ):
        """
        Presidio can return overlapping entities.

        Keep the higher-confidence result.
        """

        sorted_results = sorted(
            results,
            key=lambda result: (
                result.score,
                -(result.end - result.start),
            ),
            reverse=True,
        )

        selected = []

        for result in sorted_results:

            overlaps = False

            for existing in selected:

                if (
                    result.start < existing.end
                    and result.end > existing.start
                ):
                    overlaps = True
                    break

            if not overlaps:
                selected.append(result)

        return selected

    # =========================================================
    # Create token
    # =========================================================

    def _create_token(
        self,
        entity_type: str,
    ) -> str:
        """
        Create a short irreversible-looking token.
        """

        token_id = uuid.uuid4().hex[:10]

        return (
            "[{}:{}]".format(
                entity_type,
                token_id,
            )
        )

    # =========================================================
    # Restore token
    # =========================================================

    def restore_text(
        self,
        text: str,
    ) -> str:
        """
        Restore tokens using the local token map.

        This should only be used by an authorized caller.
        """

        restored = text

        for token, original in (
            self._token_map.items()
        ):
            restored = restored.replace(
                token,
                original,
            )

        return restored

    # =========================================================
    # Token map
    # =========================================================

    def get_token_map(self) -> Dict[str, str]:
        """
        Return a copy of the current token map.
        """

        return dict(
            self._token_map
        )