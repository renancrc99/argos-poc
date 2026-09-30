"""Porta abstrata para geração de embeddings."""

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    """Interface para geração de embeddings de texto."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Gera embedding para um único texto. Retorna lista vazia em caso de erro."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings para múltiplos textos. Retorna lista de listas vazias em caso de erro."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Retorna True se o serviço de embeddings está disponível."""
        ...
