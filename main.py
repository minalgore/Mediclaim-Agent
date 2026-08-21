"""
MediClaim Adjudication FastAPI application.

Application entry point.
"""

from fastapi import FastAPI

from app.api import router


# =========================================================
# FastAPI Application
# =========================================================

app = FastAPI(
    title="MediClaim Adjudication",
    description=(
        "Autonomous Health Insurance Claim "
        "Adjudication and Fraud Detection Agent"
    ),
    version="1.0.0",
)


# =========================================================
# API Router
# =========================================================

app.include_router(router)


# =========================================================
# Root Endpoint
# =========================================================

@app.get("/")
def root():
    """
    Root service endpoint.
    """

    return {
        "service": "mediclaim-adjudication",
        "status": "running",
        "version": "1.0.0",
    }


# =========================================================
# Application Health Check
# =========================================================

@app.get("/health")
def health():
    """
    Basic health check.
    """

    return {
        "status": "healthy",
    }