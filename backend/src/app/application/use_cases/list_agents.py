"""Caso de uso: listar todos os agentes."""

from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.application.dtos.agent_dtos import AgentOutput, agent_to_output


class ListAgentsUseCase:

    def __init__(self, agent_repo: AgentRepositoryPort):
        self._agent_repo = agent_repo

    async def execute(self) -> list[AgentOutput]:
        agents = await self._agent_repo.find_all()
        return [agent_to_output(a) for a in agents]
