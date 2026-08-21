# MediClaim Adjudication

Autonomous Claim Adjudication & Fraud Detection Agent for Indian Health Insurance Claims.

The system is designed to process medical claim documents, redact sensitive Indian PII/PHI, retrieve applicable policy clauses, maintain claim history, perform deterministic policy calculations, detect fraud/anomalies, and produce a validated adjudication decision.

## Core Capabilities

- Medical document ingestion
- PDF/image/text processing
- Indian PII/PHI redaction
- Aadhaar detection
- PAN detection
- ABHA ID detection
- Indian phone number detection
- Hospital IPD/registration ID detection
- Policy clause RAG
- IRDAI guideline retrieval
- Long-term claim memory
- Clinical diagnosis/treatment validation
- ICD-10 integration
- Tariff lookup
- Room-rent calculation
- Proportional deduction
- Waiting-period validation
- Sum Insured validation
- Non-payable item detection
- Fraud/anomaly detection
- Unbundling detection
- Timeline mismatch detection
- Structured JSON adjudication
- Guardrails and financial validation
- LangSmith tracing

## Technology Stack

| Capability | Technology |
|---|---|
| API | FastAPI |
| Language | Python 3.11+ |
| PII/PHI | Microsoft Presidio |
| RAG | LangChain |
| Vector DB | FAISS |
| Long-term Memory | Mem0 |
| Agent | LangChain |
| Tool Integration | MCP / Function Calling |
| Output Validation | Pydantic / Guardrails AI |
| Observability | LangSmith |
| OCR | Tesseract |
| Document Processing | PyMuPDF |
| Containerization | Docker |

## Project Structure

```text
mediclaim-adjudication/
│
├── app.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
├── Dockerfile
├── docker-compose.yml
│
├── config/
│   ├── settings.py
│   └── policy_rules.yaml
│
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── models.py
│   ├── document_processor.py
│   ├── pii_redactor.py
│   ├── policy_rag.py
│   ├── memory.py
│   ├── claim_agent.py
│   ├── tools.py
│   ├── rule_engine.py
│   ├── fraud_detector.py
│   ├── guardrails.py
│   ├── adjudicator.py
│   └── observability.py
│
├── data/
│   ├── policies/
│   ├── sample_claims/
│   └── medical_documents/
│
├── vectorstore/
│
├── tests/
│
└── scripts/



Medical Claim Document
        |
        v
Document Processing / OCR
        |
        v
Microsoft Presidio
PII / PHI Redaction
        |
        v
Clinical + Billing Extraction
        |
        +-------------------+
        |                   |
        v                   v
    Policy RAG           Mem0 Memory
    LangChain            Claim History
        |                   |
        +---------+---------+
                  |
                  v
            Claim Agent
             LangChain
                  |
                  v
             MCP Tools
                  |
       +----------+----------+
       |          |          |
       v          v          v
    ICD-10     Tariff     Rule Engine
                           |
                           v
                    Financial Result
                           |
              +------------+------------+
              |                         |
              v                         v
       Fraud Detection             Guardrails
              |                         |
              +------------+------------+
                           |
                           v
                    Final JSON
                           |
                           v
                       LangSmith