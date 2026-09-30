"""Caso de uso: criar um novo agente."""

import structlog

from app.domain.entities.agent import Agent
from app.domain.value_objects.agent_config import AgentConfig
from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.ports.memory_port import MemoryPort
from app.application.dtos.agent_dtos import CreateAgentInput, AgentOutput, agent_to_output

logger = structlog.get_logger()


class CreateAgentUseCase:

    def __init__(self, agent_repo: AgentRepositoryPort, memory: MemoryPort):
        self._agent_repo = agent_repo
        self._memory = memory

    async def execute(self, input_dto: CreateAgentInput) -> AgentOutput:
        config = AgentConfig(
            system_prompt=input_dto.system_prompt,
            persona=input_dto.persona,
            language=input_dto.language,
            max_history_messages=input_dto.max_history_messages,
            max_context_chunks=input_dto.max_context_chunks,
            enable_multiquery=input_dto.enable_multiquery,
            multiquery_variants=input_dto.multiquery_variants,
            use_embeddings=input_dto.use_embeddings,
            search_mode=input_dto.search_mode,
            enable_reranker=input_dto.enable_reranker,
            temperature=input_dto.temperature,
        )

        agent = Agent(
            name=input_dto.name,
            description=input_dto.description,
            config=config,
        )

        await self._memory.create_memory(agent.id)
        await self._agent_repo.save(agent)

        logger.info("agent_created", agent_id=agent.id, name=agent.name)

        return agent_to_output(agent)
