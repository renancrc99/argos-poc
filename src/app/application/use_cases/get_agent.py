"""Caso de uso: buscar um agente pelo id."""

from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.exceptions import AgentNotFoundError
from app.application.dtos.agent_dtos import AgentOutput, agent_to_output


class GetAgentUseCase:

    def __init__(self, agent_repo: AgentRepositoryPort):
        self._agent_repo = agent_repo

    async def execute(self, agent_id: str) -> AgentOutput:
        agent = await self._agent_repo.find_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        return agent_to_output(agent)
