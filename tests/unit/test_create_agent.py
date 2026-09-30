"""Unit tests for CreateAgentUseCase."""

import pytest
from unittest.mock import AsyncMock

from app.application.use_cases.create_agent import CreateAgentUseCase
from app.application.dtos.agent_dtos import CreateAgentInput


@pytest.fixture
def use_case(mock_agent_repo, mock_memory) -> CreateAgentUseCase:
    return CreateAgentUseCase(agent_repo=mock_agent_repo, memory=mock_memory)


@pytest.mark.asyncio
async def test_create_agent_saves_and_returns_output(use_case, mock_agent_repo, mock_memory):
    input_dto = CreateAgentInput(
        name="Support Bot",
        description="Customer support agent",
        system_prompt="You help customers.",
    )

    result = await use_case.execute(input_dto)

    mock_memory.create_memory.assert_called_once()
    mock_agent_repo.save.assert_called_once()

    assert result.name == "Support Bot"
    assert result.status == "created"
    assert result.total_documents == 0
    assert result.total_chunks == 0
    assert result.id is not None


@pytest.mark.asyncio
async def test_create_agent_uses_default_persona(use_case, mock_agent_repo, mock_memory):
    input_dto = CreateAgentInput(
        name="Bot",
        description="Desc",
        system_prompt="Prompt",
    )
    result = await use_case.execute(input_dto)
    assert result.persona == "cordial e objetivo"
