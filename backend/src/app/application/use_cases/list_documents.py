"""Caso de uso: listar documentos ingeridos por um agente."""

from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.application.dtos.document_dtos import DocumentRecord, document_to_record


class ListDocumentsUseCase:

    def __init__(self, document_repo: DocumentRepositoryPort):
        self._document_repo = document_repo

    async def execute(self, agent_id: str) -> list[DocumentRecord]:
        documents = await self._document_repo.find_by_agent(agent_id)
        return [document_to_record(d) for d in documents]
