"""
Application configuration for MediClaim Adjudication.

Loads configuration from environment variables / .env file.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Global application settings.
    """

    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    app_name: str = Field(
        default="mediclaim-adjudication",
        validation_alias="APP_NAME",
    )

    app_env: str = Field(
        default="development",
        validation_alias="APP_ENV",
    )

    app_version: str = Field(
        default="0.1.0",
        validation_alias="APP_VERSION",
    )

    debug: bool = Field(
        default=True,
        validation_alias="DEBUG",
    )

    host: str = Field(
        default="0.0.0.0",
        validation_alias="HOST",
    )

    port: int = Field(
        default=8000,
        validation_alias="PORT",
    )

    # ---------------------------------------------------------
    # LLM
    # ---------------------------------------------------------

    openai_api_key: str = Field(
        default="",
        validation_alias="OPENAI_API_KEY",
    )

    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="OPENAI_MODEL",
    )

    # ---------------------------------------------------------
    # LangSmith
    # ---------------------------------------------------------

    langchain_tracing_v2: bool = Field(
        default=False,
        validation_alias="LANGCHAIN_TRACING_V2",
    )

    langchain_api_key: str = Field(
        default="",
        validation_alias="LANGCHAIN_API_KEY",
    )

    langchain_project: str = Field(
        default="mediclaim-adjudication",
        validation_alias="LANGCHAIN_PROJECT",
    )

    # ---------------------------------------------------------
    # Vector Store
    # ---------------------------------------------------------

    vector_store: str = Field(
        default="faiss",
        validation_alias="VECTOR_STORE",
    )

    vector_store_path: str = Field(
        default="./vectorstore",
        validation_alias="VECTOR_STORE_PATH",
    )

    rag_chunk_size: int = Field(
        default=800,
        validation_alias="RAG_CHUNK_SIZE",
    )

    rag_chunk_overlap: int = Field(
        default=100,
        validation_alias="RAG_CHUNK_OVERLAP",
    )
    # ---------------------------------------------------------
    # Mem0
    # ---------------------------------------------------------

    mem0_api_key: str = Field(
        default="",
        validation_alias="MEM0_API_KEY",
    )

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------

    database_url: str = Field(
        default="sqlite:///./mediclaim.db",
        validation_alias="DATABASE_URL",
    )

    # ---------------------------------------------------------
    # MCP
    # ---------------------------------------------------------

    mcp_server_url: str = Field(
        default="http://localhost:9000",
        validation_alias="MCP_SERVER_URL",
    )

    # ---------------------------------------------------------
    # Security
    # ---------------------------------------------------------

    token_encryption_key: str = Field(
        default="",
        validation_alias="TOKEN_ENCRYPTION_KEY",
    )

    # ---------------------------------------------------------
    # Data paths
    # ---------------------------------------------------------

    policy_data_path: str = Field(
        default="./data/policies",
        validation_alias="POLICY_DATA_PATH",
    )

    claim_data_path: str = Field(
        default="./data/sample_claims",
        validation_alias="CLAIM_DATA_PATH",
    )

    medical_document_path: str = Field(
        default="./data/medical_documents",
        validation_alias="MEDICAL_DOCUMENT_PATH",
    )

    # ---------------------------------------------------------
    # Policy configuration
    # ---------------------------------------------------------

    policy_rules_path: str = Field(
        default="./config/policy_rules.yaml",
        validation_alias="POLICY_RULES_PATH",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def base_dir(self) -> Path:
        """Return project root directory."""
        return BASE_DIR

    @property
    def vector_store_absolute_path(self) -> Path:
        """Return absolute vector store path."""
        path = Path(self.vector_store_path)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path

    @property
    def vector_db_path(self) -> str:
        """Backward-compatible vector database path."""
        return str(self.vector_store_absolute_path)

    @property
    def policy_rules_absolute_path(self) -> Path:
        """Return absolute policy rules path."""
        path = Path(self.policy_rules_path)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path

    @property
    def policy_data_absolute_path(self) -> Path:
        """Return absolute policy data path."""
        path = Path(self.policy_data_path)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path

    @property
    def medical_document_absolute_path(self) -> Path:
        """Return absolute medical document path."""
        path = Path(self.medical_document_path)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path


@lru_cache
def get_settings() -> Settings:
    """
    Return cached application settings.

    Using lru_cache prevents .env from being read repeatedly
    during a single application process.
    """
    return Settings()


settings = get_settings()