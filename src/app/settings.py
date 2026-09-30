"""Configurações centralizadas da aplicação. Carrega de variáveis de ambiente."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS / LocalStack
    aws_endpoint_url: str | None = None
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    aws_default_region: str = "us-east-1"
    s3_bucket_name: str = "rag-platform-docs"

    # LLM — chaveamento: "anthropic" ou "ollama"
    llm_provider: str = "ollama"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Ollama (local)
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:14b"

    # Memória (cache do índice BM25)
    memvid_cache_dir: str = "/app/cache"

    # Embeddings (Ollama)
    embedding_model: str = "nomic-embed-text"
    embedding_enabled: bool = False  # requer: ollama pull nomic-embed-text

    # Reranker (baseado em LLM) — liga/desliga por agente via AgentConfig.enable_reranker
    reranker_candidates_multiplier: int = 3  # busca 3x mais chunks e depois reordena até max_context_chunks

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
