"""Porta para operações de memória vetorial (Memvid, pgvector, etc)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from app.domain.value_objects.chunk import Chunk


class SearchResult(BaseModel):
    """Resultado de uma busca na memória."""

    model_config = ConfigDict(frozen=True)

    text: str
    score: float
    source: str
    page: int | None = None


class MemoryPort(ABC):
    """Interface para criação, ingestão e busca na memória do agente."""

    @abstractmethod
    async def create_memory(self, agent_id: str) -> str:
        """Cria uma nova memória vazia. Retorna o caminho/identificador."""
        ...

    @abstractmethod
    async def ingest_chunks(
        self, agent_id: str, chunks: list[Chunk], embed: bool = False
    ) -> int:
        """
        Ingere chunks na memória do agente.

        Parâmetros:
            agent_id: Identificador do agente.
            chunks: Lista de chunks a indexar.
            embed: Se True e embedding disponível, gera e armazena embeddings.

        Retorno:
            Total de chunks indexados.
        """
        ...

    @abstractmethod
    async def search(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
        search_mode: str = "bm25",
        bm25_weight: float = 0.5,
    ) -> list[SearchResult]:
        """
        Busca na memória do agente.

        Parâmetros:
            agent_id: Identificador do agente.
            query: Query de busca.
            top_k: Número máximo de resultados.
            search_mode: "bm25" | "semantic" | "hybrid"
            bm25_weight: Peso do BM25 na busca híbrida (0.0 a 1.0).

        Retorno:
            Lista de resultados rankeados.
        """
        ...

    @abstractmethod
    async def search_multi(
        self,
        agent_id: str,
        queries: list[str],
        top_k: int = 5,
        search_mode: str = "bm25",
        bm25_weight: float = 0.5,
    ) -> list[SearchResult]:
        """
        Busca com múltiplas queries, mescla e deduplica por score máximo.

        Parâmetros:
            agent_id: Identificador do agente.
            queries: Lista de queries de busca.
            top_k: Número máximo de resultados após merge.
            search_mode: "bm25" | "semantic" | "hybrid"
            bm25_weight: Peso do BM25 na busca híbrida (0.0 a 1.0).

        Retorno:
            Lista de resultados mesclados e rankeados.
        """
        ...

    @abstractmethod
    async def get_memory_version(self, agent_id: str) -> str:
        """Retorna hash/versão da memória atual do agente."""
        ...

    @abstractmethod
    async def delete_memory(self, agent_id: str) -> None:
        """Remove o índice de memória do agente."""
        ...

    @abstractmethod
    async def index_stats(self, agent_id: str) -> dict:
        """Retorna estatísticas do índice de memória do agente (para debug)."""
        ...
