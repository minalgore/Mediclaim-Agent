import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS


class SimpleHashEmbeddings(Embeddings):
    """
    Lightweight deterministic embeddings for local development.

    This avoids downloading a transformer embedding model while
    developing the application on Python 3.8.10.

    In production, this class can be replaced by an approved
    enterprise embedding model.
    """

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def _embed(self, text: str) -> List[float]:
        vector = np.zeros(
            self.dimensions,
            dtype=np.float32,
        )

        tokens = text.lower().split()

        for token in tokens:
            index = hash(token) % self.dimensions
            vector[index] += 1.0

        norm = np.linalg.norm(vector)

        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    def embed_documents(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        return [
            self._embed(text)
            for text in texts
        ]

    def embed_query(
        self,
        text: str,
    ) -> List[float]:
        return self._embed(text)


class PolicyRAG:
    """
    Policy document ingestion and semantic retrieval.

    Responsibilities:

        1. Read policy documents.
        2. Split documents into chunks.
        3. Attach policy metadata.
        4. Build a FAISS vector index.
        5. Persist the index locally.
        6. Retrieve relevant policy clauses.
        7. Filter results by policy type.
    """

    def __init__(
        self,
        policy_dir: str = "data/policies",
        vectorstore_dir: str = "vectorstore",
    ):
        self.policy_dir = Path(policy_dir)

        self.vectorstore_dir = Path(
            vectorstore_dir
        )

        self.embeddings = SimpleHashEmbeddings()

        self.vectorstore = None

        # Automatically load an existing index.
        self._load_vectorstore()

    # =========================================================
    # Load existing FAISS index
    # =========================================================

    def _load_vectorstore(self):
        index_file = (
            self.vectorstore_dir
            / "index.faiss"
        )

        store_file = (
            self.vectorstore_dir
            / "index.pkl"
        )

        if not index_file.exists():
            return

        if not store_file.exists():
            return

        try:
            self.vectorstore = FAISS.load_local(
                str(self.vectorstore_dir),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        except Exception:
            # If the stored index is incompatible or corrupted,
            # start without an index.
            self.vectorstore = None

    # =========================================================
    # Ingest policies
    # =========================================================

    def ingest(self) -> int:
        """
        Read policy documents and create the FAISS index.

        Currently supported:
            .txt
            .json

        Returns:
            Number of indexed chunks.
        """

        texts = []
        metadatas = []

        if not self.policy_dir.exists():
            self.policy_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        for path in sorted(
            self.policy_dir.glob("*")
        ):
            if not path.is_file():
                continue

            suffix = path.suffix.lower()

            if suffix == ".txt":
                content = path.read_text(
                    encoding="utf-8"
                )

            elif suffix == ".json":
                content = json.dumps(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    ),
                    indent=2,
                )

            else:
                continue

            if not content.strip():
                continue

            chunks = self._chunk_text(
                content
            )

            policy_type = (
                self._infer_policy_type(
                    content
                )
            )

            for index, chunk in enumerate(
                chunks
            ):
                texts.append(chunk)

                metadatas.append(
                    {
                        "source": path.name,
                        "page": None,
                        "policy_type": policy_type,
                        "clause_id": "{}-{}".format(
                            path.stem,
                            index + 1,
                        ),
                    }
                )

        if not texts:
            self.vectorstore = None
            return 0

        self.vectorstore = (
            FAISS.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas,
            )
        )

        self.vectorstore_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.vectorstore.save_local(
            str(self.vectorstore_dir)
        )

        return len(texts)

    # =========================================================
    # Chunking
    # =========================================================

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1200,
    ) -> List[str]:
        """
        Split policy text into manageable chunks.

        For the first implementation we use deterministic
        character-based chunks.

        Later this can be replaced by a clause-aware
        LangChain text splitter.
        """

        text = text.strip()

        if not text:
            return []

        chunks = []

        start = 0

        while start < len(text):
            end = start + chunk_size

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            start = end

        return chunks

    # =========================================================
    # Policy type detection
    # =========================================================

    def _infer_policy_type(
        self,
        text: str,
    ) -> str:
        """
        Infer policy type from policy text.

        Supported types:

            INDIVIDUAL_HEALTH
            SENIOR_CITIZEN
            CRITICAL_ILLNESS
        """

        upper_text = text.upper()

        if (
            "SENIOR CITIZEN" in upper_text
            or "SENIOR_CITIZEN" in upper_text
        ):
            return "SENIOR_CITIZEN"

        if (
            "CRITICAL ILLNESS" in upper_text
            or "CRITICAL_ILLNESS" in upper_text
        ):
            return "CRITICAL_ILLNESS"

        return "INDIVIDUAL_HEALTH"

    # =========================================================
    # Retrieve policy clauses
    # =========================================================

    def retrieve(
        self,
        query: str,
        policy_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        Retrieve policy clauses relevant to a claim.

        Args:
            query:
                Clinical/policy question.

            policy_type:
                Optional metadata filter.

            top_k:
                Maximum number of results.

        Returns:
            List of policy evidence dictionaries.
        """

        if not query:
            return []

        if self.vectorstore is None:
            self._load_vectorstore()

        if self.vectorstore is None:
            self.ingest()

        if self.vectorstore is None:
            return []

        # Retrieve more results than necessary so that
        # metadata filtering still leaves enough results.
        search_k = max(
            top_k * 3,
            top_k,
        )

        documents = (
            self.vectorstore.similarity_search(
                query,
                k=search_k,
            )
        )

        output = []

        for document in documents:

            metadata = dict(
                document.metadata or {}
            )

            document_policy_type = (
                metadata.get(
                    "policy_type"
                )
            )

            if (
                policy_type
                and document_policy_type
                != policy_type
            ):
                continue

            output.append(
                {
                    "content": document.page_content,
                    "source": metadata.get(
                        "source",
                        "",
                    ),
                    "page": metadata.get(
                        "page"
                    ),
                    "policy_type": (
                        document_policy_type
                    ),
                    "clause_id": metadata.get(
                        "clause_id",
                        "",
                    ),
                }
            )

            if len(output) >= top_k:
                break

        return output

    # =========================================================
    # Check whether vector store exists
    # =========================================================

    def is_indexed(self) -> bool:
        return (
            self.vectorstore is not None
        )

    # =========================================================
    # Clear vector store
    # =========================================================

    def clear(self):
        """
        Clear the in-memory vector store.

        The persisted files can be removed separately if required.
        """

        self.vectorstore = None


# =========================================================
# Backward-compatible vector store creation helper
# =========================================================

def create_vector_store(
    documents,
    persist_directory: str = "vectorstore",
):
    """
    Create and persist the policy FAISS vector store.

    Compatibility wrapper used by scripts/ingest_policies.py.
    """

    rag = PolicyRAG(
        vectorstore_dir=persist_directory,
    )

    # Reuse the existing PolicyRAG implementation.
    texts = [
        document.page_content
        for document in documents
    ]

    metadatas = [
        dict(document.metadata or {})
        for document in documents
    ]

    if not texts:
        rag.vectorstore = None
        return rag

    rag.vectorstore = FAISS.from_texts(
        texts=texts,
        embedding=rag.embeddings,
        metadatas=metadatas,
    )

    rag.vectorstore_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    rag.vectorstore.save_local(
        str(rag.vectorstore_dir)
    )

    return rag