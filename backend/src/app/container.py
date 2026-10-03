"""Container de Injeção de Dependência. Instancia os adapters e monta os use cases."""

from app.infrastructure.adapters.s3_storage_adapter import S3StorageAdapter
from app.infrastructure.adapters.memvid_memory_adapter import MemvidMemoryAdapter
from app.infrastructure.adapters.ollama_embedding_adapter import OllamaEmbeddingAdapter
from app.infrastructure.adapters.claude_llm_adapter import ClaudeLLMAdapter
from app.infrastructure.adapters.ollama_llm_adapter import OllamaLLMAdapter
from app.infrastructure.adapters.sqlite_agent_repository import SQLiteAgentRepository
from app.infrastructure.adapters.sqlite_document_repository import SQLiteDocumentRepository
from app.application.services.parsing_service import ParsingService
from app.application.services.chunking_service import ChunkingService
from app.application.services.prompt_builder import PromptBuilder
from app.application.use_cases.create_agent import CreateAgentUseCase
from app.application.use_cases.get_agent import GetAgentUseCase
from app.application.use_cases.delete_agent import DeleteAgentUseCase
from app.application.use_cases.ingest_documents import IngestDocumentsUseCase
from app.application.use_cases.list_documents import ListDocumentsUseCase
from app.application.use_cases.chat_with_agent import ChatWithAgentUseCase
from app.application.use_cases.list_agents import ListAgentsUseCase
from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.storage_port import StoragePort
from app.domain.ports.memory_port import MemoryPort
from app.domain.ports.llm_port import LLMPort
from app.domain.ports.embedding_port import EmbeddingPort
from app.settings import settings
import structlog

logger = structlog.get_logger()


def _build_llm() -> LLMPort:
    """Instancia o adaptador de LLM conforme LLM_PROVIDER."""
    if settings.llm_provider == "anthropic":
        logger.info("llm_provider", provider="anthropic", model=settings.anthropic_model)
        return ClaudeLLMAdapter()
    logger.info("llm_provider", provider="ollama", model=settings.ollama_model)
    return OllamaLLMAdapter()


def _build_embedding() -> "EmbeddingPort | None":
    """Instancia o adaptador de embedding se habilitado nas configurações."""
    if not settings.embedding_enabled:
        logger.info("embedding_disabled")
        return None
    logger.info(
        "embedding_enabled",
        provider="ollama",
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )
    return OllamaEmbeddingAdapter(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )


class Container:
    """Container de DI simples. Instancia os adapters e conecta as dependências."""

    def __init__(self):
        # Adapters (infraestrutura) — expostos pelo tipo da Porta, não da classe concreta
        self.storage: StoragePort = S3StorageAdapter()
        self.embedding: EmbeddingPort | None = _build_embedding()
        self.memory: MemoryPort = MemvidMemoryAdapter(embedding=self.embedding)
        self.llm: LLMPort = _build_llm()
        self.agent_repo: AgentRepositoryPort = SQLiteAgentRepository()
        self.document_repo: DocumentRepositoryPort = SQLiteDocumentRepository()

        # Serviços (aplicação)
        self.parsing_service = ParsingService()
        self.chunking_service = ChunkingService()
        self.prompt_builder = PromptBuilder()

        # Use Cases
        self.create_agent = CreateAgentUseCase(
            agent_repo=self.agent_repo,
            memory=self.memory,
        )
        self.list_agents = ListAgentsUseCase(agent_repo=self.agent_repo)
        self.get_agent = GetAgentUseCase(agent_repo=self.agent_repo)
        self.delete_agent = DeleteAgentUseCase(
            agent_repo=self.agent_repo,
            document_repo=self.document_repo,
            memory=self.memory,
        )
        self.ingest_documents = IngestDocumentsUseCase(
            agent_repo=self.agent_repo,
            document_repo=self.document_repo,
            storage=self.storage,
            memory=self.memory,
            parsing_service=self.parsing_service,
            chunking_service=self.chunking_service,
        )
        self.list_documents = ListDocumentsUseCase(document_repo=self.document_repo)
        self.chat_with_agent = ChatWithAgentUseCase(
            agent_repo=self.agent_repo,
            memory=self.memory,
            llm=self.llm,
            prompt_builder=self.prompt_builder,
        )


# Singleton
container = Container()
