"""Caso de uso: remover um agente e tudo que pertence a ele."""

import structlog

from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.memory_port import MemoryPort
from app.domain.exceptions import AgentNotFoundError

logger = structlog.get_logger()


class DeleteAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepositoryPort,
        document_repo: DocumentRepositoryPort,
        memory: MemoryPort,
    ):
        self._agent_repo = agent_repo
        self._document_repo = document_repo
        self._memory = memory

    async def execute(self, agent_id: str) -> None:
        agent = await self._agent_repo.find_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)

        await self._document_repo.delete_by_agent(agent_id)
        await self._memory.delete_memory(agent_id)
        await self._agent_repo.delete(agent_id)

        logger.info("agent_deleted", agent_id=agent_id)
