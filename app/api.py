"""
FastAPI endpoints for MediClaim Adjudication.
"""

import json
import os
import tempfile
from typing import Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.adjudicator import Adjudicator
from app.claim_agent import ClaimAgent
from app.document_processor import DocumentProcessor
from app.models import ClaimRequest
from app.observability import (
    configure_langsmith,
    trace,
)
from app.pii_redactor import PIIRedactor


router = APIRouter()


# ---------------------------------------------------------
# Application services
# ---------------------------------------------------------

configure_langsmith()

document_processor = DocumentProcessor()
pii_redactor = PIIRedactor()
claim_agent = ClaimAgent(
    pii_redactor=pii_redactor,
    document_processor=document_processor,
)

adjudicator = Adjudicator()


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _process_uploaded_document(
    content: bytes,
    filename: str,
):
    """
    Process uploaded document.

    Flow:

        bytes
          ↓
        temporary file
          ↓
        DocumentProcessor
          ↓
        extracted text
          ↓
        PIIRedactor
          ↓
        sanitized text
    """

    if not content:
        raise ValueError(
            "Uploaded document is empty."
        )

    suffix = os.path.splitext(
        filename
    )[1].lower()

    if not suffix:
        suffix = ".txt"

    temporary_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temporary_file:

            temporary_file.write(
                content
            )

            temporary_path = (
                temporary_file.name
            )

        # -------------------------------------------------
        # Extract text
        # -------------------------------------------------

        extracted_text = (
            document_processor.extract_text(
                temporary_path
            )
        )

        # -------------------------------------------------
        # PII / PHI redaction
        # -------------------------------------------------

        redaction_result = (
            pii_redactor.redact_text(
                extracted_text
            )
        )

        document_type = (
            document_processor.get_document_type(
                temporary_path
            )
        )

        return {
            "document_type": document_type,
            "extracted_text": extracted_text,
            "sanitized_text": (
                redaction_result.text
            ),
            "detected_entities": (
                getattr(
                    redaction_result,
                    "entities",
                    [],
                )
            ),
            "redaction_count": (
                getattr(
                    redaction_result,
                    "redaction_count",
                    0,
                )
            ),
        }

    finally:

        if (
            temporary_path is not None
            and os.path.exists(
                temporary_path
            )
        ):

            os.remove(
                temporary_path
            )


# ---------------------------------------------------------
# Health / Status
# ---------------------------------------------------------

@router.get(
    "/api/v1/status"
)
def status():
    """
    Service health/status endpoint.
    """

    return {
        "service": "mediclaim-adjudication",
        "status": "running",
    }


# ---------------------------------------------------------
# Document Processing
# ---------------------------------------------------------

@router.post(
    "/api/v1/documents/process"
)
@trace("document_processing")
async def process_medical_document(
    file: UploadFile = File(...),
):
    """
    Upload and process a medical document.

    Processing flow:

        Upload
          ↓
        Document extraction
          ↓
        PII / PHI detection
          ↓
        Redaction
          ↓
        Sanitized document
    """

    try:

        content = await file.read()

        result = _process_uploaded_document(
            content=content,
            filename=(
                file.filename
                or "document.txt"
            ),
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ImportError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Document processing failed: "
                + str(exc)
            ),
        ) from exc


# ---------------------------------------------------------
# Claim Adjudication
# ---------------------------------------------------------

@router.post(
    "/api/v1/claims/adjudicate"
)
@trace("claim_adjudication")
async def adjudicate_claim(
    claim: str = Form(...),
    file: Optional[UploadFile] = File(
        default=None
    ),
):
    """
    Adjudicate a medical insurance claim.

    Parameters
    ----------
    claim:
        JSON string containing ClaimRequest fields.

    file:
        Optional medical document.

    The Adjudicator owns the complete pipeline:

        ClaimRequest
            ↓
        Adjudicator
            ↓
        ClaimAgent
            ↓
        PII Redaction
            ↓
        Policy RAG
            ↓
        Memory
            ↓
        Rule Engine
            ↓
        Fraud Detection
            ↓
        Adjudication
            ↓
        Guardrails
            ↓
        Final Output
    """

    try:

        # -------------------------------------------------
        # Parse claim JSON
        # -------------------------------------------------

        try:

            claim_data = json.loads(
                claim
            )

        except json.JSONDecodeError as exc:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid claim JSON."
                ),
            ) from exc

        if not isinstance(
            claim_data,
            dict,
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "Claim JSON must be an object."
                ),
            )

        # -------------------------------------------------
        # Validate claim
        # -------------------------------------------------

        validated_claim = ClaimRequest(
            **claim_data
        )

        if hasattr(
            validated_claim,
            "model_dump",
        ):

            claim_dict = (
                validated_claim.model_dump()
            )

        else:

            claim_dict = (
                validated_claim.dict()
            )

        # -------------------------------------------------
        # Optional medical document
        # -------------------------------------------------

        if file is not None:

            content = await file.read()

            document = (
                _process_uploaded_document(
                    content=content,
                    filename=(
                        file.filename
                        or "document.txt"
                    ),
                )
            )

            # Store sanitized text only.
            claim_dict[
                "sanitized_document"
            ] = document[
                "sanitized_text"
            ]

            claim_dict[
                "document_type"
            ] = document[
                "document_type"
            ]

            claim_dict[
                "detected_entities"
            ] = document[
                "detected_entities"
            ]

        # -------------------------------------------------
        # Complete adjudication
        # -------------------------------------------------

        # -------------------------------------------------
        # Run Claim Agent pipeline
        # -------------------------------------------------

        agent_context = claim_agent.process_claim(
            claim_dict
        )

        # -------------------------------------------------
        # Final adjudication
        # -------------------------------------------------

        print(
            "DEBUG SANITIZED CLAIM:",
            agent_context["sanitized_claim"]
        )

        print(
            "DEBUG POLICYHOLDER:",
            repr(
                agent_context["sanitized_claim"].get(
                    "policyholder_id"
                )
            )
        )
        result = adjudicator.adjudicate(
            claim=agent_context["sanitized_claim"],
            rule_results=agent_context["rule_results"],
            fraud_result=agent_context["fraud_result"],
            policy_evidence=agent_context["policy_evidence"],
        )
        # -------------------------------------------------
        # Return JSON-safe result
        # -------------------------------------------------

        if hasattr(
            result,
            "model_dump",
        ):

            return result.model_dump(
                mode="json"
            )

        if hasattr(
            result,
            "dict",
        ):

            return result.dict()

        return result

    except HTTPException:

        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Claim adjudication failed: "
                + str(exc)
            ),
        ) from exc