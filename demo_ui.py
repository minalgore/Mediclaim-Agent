"""
MediClaim Adjudication - Browser Demo UI

Loads demo claims dynamically from:

    data/sample_claims/*.json

Each JSON file represents one demo claim.

The dropdown displays the business/test-case description
rather than the JSON filename.
"""

import json
from pathlib import Path

import requests
import streamlit as st


# =========================================================
# Configuration
# =========================================================

API_URL = "http://127.0.0.1:8000/api/v1/claims/adjudicate"

PROJECT_ROOT = Path(__file__).resolve().parent

CLAIMS_DIR = (
    PROJECT_ROOT
    / "data"
    / "sample_claims"
)


# =========================================================
# Streamlit Page Configuration
# =========================================================

st.set_page_config(
    page_title="MediClaim Adjudication",
    page_icon="🏥",
    layout="wide",
)


# =========================================================
# Custom Styling
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        font-size: 1.05rem;
        color: #666;
        margin-bottom: 1.5rem;
    }

    .case-description {
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    /* Compact Claim Summary metrics */
    div[data-testid="stMetric"] {
        padding: 0.25rem 0;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.05rem !important;
        line-height: 1.2 !important;
    }

    div[data-testid="stMetricValue"] > div {
        font-size: 1.05rem !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Load Demo Claims
# =========================================================

def load_claim_files():
    """
    Load individual claim JSON files.

    Expected format:

        {
            "claim_id": "...",
            "description": "...",
            ...
        }

    JSON files containing a list are ignored.
    """

    claims = {}

    if not CLAIMS_DIR.exists():
        return claims

    for file_path in sorted(
        CLAIMS_DIR.glob("*.json")
    ):

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as file:

                claim = json.load(file)

            # -------------------------------------------------
            # Ignore legacy combined JSON files containing
            # a list of claims.
            # -------------------------------------------------

            if not isinstance(
                claim,
                dict,
            ):

                continue

            claim_id = claim.get(
                "claim_id"
            )

            if not claim_id:
                continue

            claims[claim_id] = {
                "filename": file_path.name,
                "data": claim,
            }

        except Exception as exc:

            st.warning(
                "Could not load {}: {}".format(
                    file_path.name,
                    exc,
                )
            )

    return claims


# =========================================================
# Claim Dropdown Label
# =========================================================

def claim_label(claim_id):
    """
    Text displayed in the claim selection dropdown.
    """

    claim = claims[
        claim_id
    ]["data"]

    description = claim.get(
        "description",
        "Demo Claim",
    )

    return "{}".format(
        description,
    )


# =========================================================
# API Call
# =========================================================

def submit_claim(claim):
    """
    Submit the selected claim to FastAPI.
    """

    response = requests.post(
        API_URL,
        data={
            "claim": json.dumps(
                claim
            )
        },
        timeout=120,
    )

    return response


# =========================================================
# Formatting Helpers
# =========================================================

def format_status(status):

    if not status:
        return "UNKNOWN"

    return str(
        status
    ).replace(
        "_",
        " ",
    )


def get_fraud_assessment(result):

    fraud = result.get(
        "fraud_assessment",
        {},
    )

    if not isinstance(
        fraud,
        dict,
    ):
        return {}

    return fraud


def get_fraud_score(result):

    fraud = get_fraud_assessment(
        result
    )

    return fraud.get(
        "risk_score",
        0,
    )


def get_fraud_level(result):

    fraud = get_fraud_assessment(
        result
    )

    level = fraud.get(
        "risk_level",
        "LOW",
    )

    return str(
        level
    ).replace(
        "FraudRisk.",
        "",
    )


# =========================================================
# Header
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🏥 MediClaim Adjudication'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="subtitle">
    Autonomous Health Insurance Claim Adjudication
    & Fraud Detection Demo
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Load Claims
# =========================================================

claims = load_claim_files()

if not claims:

    st.error(
        "No valid demo claim JSON files found."
    )

    st.markdown(
        "Expected folder:"
    )

    st.code(
        str(
            CLAIMS_DIR
        ),
        language="text",
    )

    st.stop()


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:

    st.header(
        "🎯 Demo Controls"
    )

    claim_ids = list(
        claims.keys()
    )

    selected_claim_id = st.selectbox(
        "Select Test Case",
        claim_ids,
        format_func=claim_label,
    )

    selected_claim = claims[
        selected_claim_id
    ]

    selected_claim_data = (
        selected_claim["data"]
    )

    st.divider()

    st.subheader(
        "Selected Scenario"
    )

    st.write(
        selected_claim_data.get(
            "description",
            "Demo Claim",
        )
    )

    st.divider()

    st.subheader(
        "Backend API"
    )

    st.code(
        API_URL,
        language="text",
    )

    st.divider()

    if st.button(
        "🔄 Reload Test Cases",
        use_container_width=True,
    ):

        st.rerun()


# =========================================================
# Selected Claim
# =========================================================

claim = selected_claim_data


# =========================================================
# Test Case Description
# =========================================================

st.subheader(
    "Selected Test Case"
)

st.markdown(
    '<div class="case-description">{}</div>'.format(
        claim.get(
            "description",
            "Demo Claim",
        )
    ),
    unsafe_allow_html=True,
)


# =========================================================
# Claim Summary
# =========================================================

st.subheader(
    "Claim Summary"
)

col1, col2, col3, col4 = st.columns(
    4
)


with col1:

    st.metric(
        "Claim ID",
        claim.get(
            "claim_id",
            "-",
        ),
    )


with col2:

    st.metric(
        "Policy",
        claim.get(
            "policy_id",
            "-",
        ),
    )


with col3:

    st.metric(
        "Diagnosis",
        claim.get(
            "diagnosis",
            "-",
        ),
    )


with col4:

    claimed_amount = float(
        claim.get(
            "claimed_amount",
            0,
        )
        or 0
    )

    st.metric(
        "Claimed Amount",
        "₹{:,.0f}".format(
            claimed_amount
        ),
    )


# =========================================================
# Input Claim JSON
# =========================================================

with st.expander(
    "📄 View Input Claim JSON",
    expanded=False,
):

    st.json(
        claim
    )


# =========================================================
# Adjudication Button
# =========================================================

st.divider()

run_col, spacer = st.columns(
    [1, 3]
)


with run_col:

    adjudicate = st.button(
        "🚀 Adjudicate Claim",
        type="primary",
        use_container_width=True,
    )


# =========================================================
# Run Adjudication
# =========================================================

if adjudicate:

    with st.spinner(
        "Running autonomous claim adjudication..."
    ):

        try:

            response = submit_claim(
                claim
            )

        except requests.exceptions.ConnectionError:

            st.error(
                "❌ Could not connect to the FastAPI backend."
            )

            st.info(
                "Start the backend with:"
            )

            st.code(
                "PYTHONPATH=. uvicorn main:app",
                language="bash",
            )

            st.stop()

        except requests.exceptions.Timeout:

            st.error(
                "❌ The API request timed out."
            )

            st.stop()

        except Exception as exc:

            st.error(
                "❌ Unexpected error: {}".format(
                    exc
                )
            )

            st.stop()


    # =====================================================
    # HTTP Error
    # =====================================================

    if response.status_code != 200:

        st.error(
            "API returned HTTP {}".format(
                response.status_code
            )
        )

        st.code(
            response.text,
            language="json",
        )

        st.stop()


    # =====================================================
    # Parse Response
    # =====================================================

    try:

        result = response.json()

    except Exception:

        st.error(
            "API returned an invalid JSON response."
        )

        st.code(
            response.text,
            language="text",
        )

        st.stop()


    # =====================================================
    # Success
    # =====================================================

    st.success(
        "✅ Claim adjudication completed successfully."
    )


    # =====================================================
    # Result Header
    # =====================================================

    st.subheader(
        "📊 Adjudication Result"
    )


    # =====================================================
    # Result Metrics
    # =====================================================

    status = result.get(
        "claim_status",
        "UNKNOWN",
    )

    claimed_amount = float(
        result.get(
            "claimed_amount",
            claim.get(
                "claimed_amount",
                0,
            ),
        )
        or 0
    )

    approved_amount = float(
        result.get(
            "approved_amount",
            0,
        )
        or 0
    )

    fraud_score = float(
        get_fraud_score(
            result
        )
        or 0
    )

    fraud_level = get_fraud_level(
        result
    )

    # Human-review decision is returned by the fraud assessment.
    # Fall back to the top-level field for backward compatibility.
    fraud = get_fraud_assessment(result)

    human_review = fraud.get(
        "requires_human_review",
        result.get(
            "requires_human_review",
            False,
        ),
    )


    col1, col2, col3, col4, col5 = (
        st.columns(5)
    )


    with col1:

        st.metric(
            "Claim Status",
            format_status(
                status
            ),
        )


    with col2:

        st.metric(
            "Claimed",
            "₹{:,.0f}".format(
                claimed_amount
            ),
        )


    with col3:

        st.metric(
            "Approved",
            "₹{:,.0f}".format(
                approved_amount
            ),
        )


    with col4:

        st.metric(
            "Fraud Score",
            "{:.0f}".format(
                fraud_score
            ),
        )


    with col5:

        st.metric(
            "Fraud Risk",
            fraud_level,
        )


    # =====================================================
    # Human Review
    # =====================================================

    if human_review:

        st.warning(
            "⚠️ HUMAN REVIEW REQUIRED"
        )

    else:

        st.success(
            "✅ No human review required"
        )


    # =====================================================
    # Fraud Assessment
    # =====================================================

    fraud = get_fraud_assessment(
        result
    )

    anomaly_flags = fraud.get(
        "anomaly_flags",
        [],
    )

    if anomaly_flags:

        st.subheader(
            "🚨 Fraud / Anomaly Flags"
        )

        for flag in anomaly_flags:

            st.warning(
                flag
            )


    # =====================================================
    # Query Reasons
    # =====================================================

    query_reasons = result.get(
        "query_reasons",
        [],
    )

    if query_reasons:

        st.subheader(
            "❓ Query Reasons"
        )

        for reason in query_reasons:

            st.info(
                reason
            )


    # =====================================================
    # Deduction Reasons
    # =====================================================

    deduction_reasons = result.get(
        "deduction_reasons",
        [],
    )

    if deduction_reasons:

        st.subheader(
            "💰 Deduction Reasons"
        )

        for reason in deduction_reasons:

            st.write(
                "• {}".format(
                    reason
                )
            )


    # =====================================================
    # Policy Citations
    # =====================================================

    citations = result.get(
        "policy_clause_citations",
        [],
    )

    if citations:

        st.subheader(
            "📚 Policy Clause Citations"
        )

        for citation in citations:

            st.code(
                citation,
                language="text",
            )


    # =====================================================
    # Amount Breakdown
    # =====================================================

    amount_breakdown = result.get(
        "amount_breakdown",
        {},
    )

    if amount_breakdown:

        st.subheader(
            "🧮 Amount Breakdown"
        )

        st.json(
            amount_breakdown
        )


    # =====================================================
    # Complete API Response
    # =====================================================

    with st.expander(
        "🔍 View Complete API Response",
        expanded=False,
    ):

        st.json(
            result
        )


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "MediClaim Adjudication • Training / Demonstration Project"
)