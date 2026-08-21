"""
Policy document ingestion script.

Usage:
    python Scripts/ingest_policies.py

Expected directory:

mediclaim-adjudication/
│
├── Scripts/
│   └── ingest_policies.py
│
├── data/
│   └── policies/
│       ├── health_policy.txt
│       ├── exclusions.txt
│       └── senior_citizen_policy.pdf
│
└── ...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Allow imports from project root when script is executed as:
# python Scripts/ingest_policies.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.policy_rag import create_vector_store
from config.settings import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
}


def load_text_file(path: Path) -> str:
    """Load a plain text or Markdown policy file."""

    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def load_pdf_file(path: Path) -> str:
    """Load text from a PDF document."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required to ingest PDF documents. "
            "Install it using: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""

        if text.strip():
            pages.append(
                f"\n[Page {page_number}]\n{text}"
            )

    return "\n".join(pages)


def load_document(path: Path) -> str:
    """Load a supported policy document."""

    extension = path.suffix.lower()

    if extension in {".txt", ".md"}:
        return load_text_file(path)

    if extension == ".pdf":
        return load_pdf_file(path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )


def infer_policy_type(path: Path) -> str:
    """
    Infer policy type from the filename.

    Examples:
        senior_citizen_policy.pdf
            -> Senior Citizen

        critical_illness_policy.txt
            -> Critical Illness

        individual_health_policy.txt
            -> Individual Health
    """

    filename = path.stem.lower()

    if "senior" in filename:
        return "Senior Citizen"

    if "critical" in filename:
        return "Critical Illness"

    if (
        "individual" in filename
        or "health" in filename
    ):
        return "Individual Health"

    if "group" in filename:
        return "Group Health"

    return "General Health"


def load_policy_documents(
    policy_directory: Path,
) -> List[Document]:
    """Load all supported policy files."""

    if not policy_directory.exists():
        raise FileNotFoundError(
            f"Policy directory does not exist: "
            f"{policy_directory}"
        )

    documents: List[Document] = []

    files = sorted(
        file
        for file in policy_directory.rglob("*")
        if file.is_file()
        and file.suffix.lower()
        in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.warning(
            "No policy documents found in %s",
            policy_directory,
        )

        return documents

    for path in files:
        logger.info(
            "Loading policy: %s",
            path,
        )

        try:
            text = load_document(path)

            if not text.strip():
                logger.warning(
                    "Skipping empty document: %s",
                    path,
                )
                continue

            policy_type = infer_policy_type(path)

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": path.name,
                        "file_path": str(path),
                        "policy_type": policy_type,
                        "document_type": "policy",
                    },
                )
            )

        except Exception:
            logger.exception(
                "Failed to load %s",
                path,
            )

    logger.info(
        "Loaded %d policy documents.",
        len(documents),
    )

    return documents


def split_documents(
    documents: List[Document],
) -> List[Document]:
    """
    Split policy documents into semantic chunks.

    Chunk sizes should be tuned using actual policy
    retrieval evaluation results.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
        ],
    )

    chunks = splitter.split_documents(
        documents
    )

    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = index

    logger.info(
        "Created %d policy chunks.",
        len(chunks),
    )

    return chunks


def validate_chunks(
    chunks: List[Document],
) -> List[Document]:
    """
    Basic quality validation before indexing.

    Empty or extremely short chunks are discarded.
    """

    valid_chunks = []

    for chunk in chunks:
        content = chunk.page_content.strip()

        if len(content) < 20:
            logger.warning(
                "Skipping very short chunk: %s",
                content,
            )
            continue

        valid_chunks.append(chunk)

    logger.info(
        "Validated %d/%d chunks.",
        len(valid_chunks),
        len(chunks),
    )

    return valid_chunks


def ingest(
    policy_directory: Path,
) -> None:
    """Execute the complete policy ingestion pipeline."""

    logger.info(
        "Starting policy ingestion..."
    )

    documents = load_policy_documents(
        policy_directory
    )

    if not documents:
        logger.warning(
            "Nothing to ingest."
        )
        return

    chunks = split_documents(
        documents
    )

    chunks = validate_chunks(
        chunks
    )

    if not chunks:
        logger.warning(
            "No valid chunks available."
        )
        return

    logger.info(
        "Creating vector store..."
    )

    create_vector_store(
        documents=chunks,
        persist_directory=settings.vector_db_path,
    )

    logger.info(
        "Policy ingestion completed successfully."
    )

    logger.info(
        "Indexed %d chunks.",
        len(chunks),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest insurance policy documents "
            "into the RAG vector database."
        )
    )

    parser.add_argument(
        "--policy-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "policies",
        help=(
            "Directory containing policy documents. "
            "Default: data/policies"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logger.info(
        "Project root: %s",
        PROJECT_ROOT,
    )

    logger.info(
        "Policy directory: %s",
        args.policy_dir,
    )

    ingest(
        policy_directory=args.policy_dir
    )


if __name__ == "__main__":
    main()