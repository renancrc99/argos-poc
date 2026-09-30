"""Porta para persistência de documentos ingeridos."""

from abc import ABC, abstractmethod

from app.domain.entities.document import Document


class DocumentRepositoryPort(ABC):

    @abstractmethod
    async def save(self, document: Document) -> None:
        ...

    @abstractmethod
    async def find_by_agent(self, agent_id: str) -> list[Document]:
        ...

    @abstractmethod
    async def find_by_config_hash(self, agent_id: str, config_hash: str) -> Document | None:
        """Retorna o documento existente deste agente que corresponde ao config_hash, ou None."""
        ...

    @abstractmethod
    async def delete_by_agent(self, agent_id: str) -> None:
        ...
