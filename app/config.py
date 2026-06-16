from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gpt-oss:120b-cloud"
    ollama_embed_model: str = "nomic-embed-text"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "landchain_rag_v2"
    qdrant_api_key: str = ""

    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"
    hybrid_enabled: bool = True
    rrf_k: int = 60

    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./storage/uploads")
    ingest_index_path: Path = Path("./storage/ingest_index.json")

    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4
    retrieve_k: int = 24
    rerank_enabled: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_min_score: float = -2.0

    query_rewrite_enabled: bool = True
    query_rewrite_timeout: float = 2.0

    neighbor_expand_enabled: bool = True
    neighbor_window: int = 1
    expand_max_chunks: int = 8
    session_db_path: Path = Path("./storage/sessions.db")
    max_upload_size_mb: int = 20
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "landchain"
    postgres_password: str = "landchain"
    postgres_db: str = "landchain"

    postgres_business_collection: str = "order"
    postgres_business_id_field: str = "ID"
    postgres_business_time_field: str = "created_at"

    chitchat_direct_enabled: bool = True
    chitchat_max_length: int = 24

    allowed_extensions: frozenset[str] = frozenset({".pdf", ".txt", ".md"})

    # Agent
    agent_enabled: bool = True
    agent_session_db_path: Path = Path("./storage/agent_sessions.db")
    agent_audit_db_path: Path = Path("./storage/agent_audit.db")
    agent_max_iterations: int = 15
    agent_tool_result_max_chars: int = 12000
    ollama_agent_model: str = ""
    ollama_agent_fallback_model: str = "qwen2.5:14b"
    agent_shell_enabled: bool = True
    agent_shell_mode: str = "allowlist"
    agent_shell_timeout: int = 30
    agent_shell_cwd: Path = Path("./")
    agent_execution_env: str = "container"
    agent_shell_allowlist: str = r"^python scripts/,^pip ,^curl http://localhost"
    agent_hitl_enabled: bool = True
    agent_hitl_timeout: int = 300
    agent_api_key: str = ""
    agent_summarize_after_messages: int = 30
    agent_tasks_path: Path = Path("./storage/agent_tasks.yaml")
    agent_task_timeout: int = 60
    agent_timezone: str = "Asia/Shanghai"
    postgres_agent_collection_allowlist: str = ""
    postgres_agent_collection_denylist: str = "agent_runs,agent_audit"
    postgres_schema_sample_size: int = 50
    postgres_schema_cache_ttl: int = 3600
    postgres_schema_cache_path: Path = Path("./storage/postgres_schema_cache.json")
    postgres_collection_overrides_path: Path = Path("./storage/collection_overrides.yaml")

    @property
    def effective_agent_model(self) -> str:
        return self.ollama_agent_model or self.ollama_chat_model

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def agent_shell_allowlist_patterns(self) -> list[str]:
        return [p.strip() for p in self.agent_shell_allowlist.split(",") if p.strip()]

    @property
    def postgres_agent_allowlist(self) -> set[str]:
        if not self.postgres_agent_collection_allowlist.strip():
            return set()
        return {
            c.strip()
            for c in self.postgres_agent_collection_allowlist.split(",")
            if c.strip()
        }

    @property
    def postgres_agent_denylist(self) -> set[str]:
        return {
            c.strip()
            for c in self.postgres_agent_collection_denylist.split(",")
            if c.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
