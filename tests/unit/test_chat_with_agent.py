"""Unit tests for ChatWithAgentUseCase."""

import pytest
from unittest.mock import AsyncMock

from app.application.use_cases.chat_with_agent import ChatWithAgentUseCase
from app.application.dtos.chat_dtos import ChatInput
from app.domain.ports.memory_port import SearchResult
from app.domain.ports.llm_port import LLMResponse
from app.domain.exceptions import AgentNotFoundError, AgentNotReadyError


@pytest.fixture
def use_case(mock_agent_repo, mock_memory, mock_llm) -> ChatWithAgentUseCase:
    return ChatWithAgentUseCase(
        agent_repo=mock_agent_repo, memory=mock_memory, llm=mock_llm
    )


@pytest.mark.asyncio
async def test_chat_raises_when_agent_not_found(use_case, mock_agent_repo):
    mock_agent_repo.find_by_id.return_value = None
    with pytest.raises(AgentNotFoundError):
        await use_case.execute(ChatInput(agent_id="missing", message="hello"))


@pytest.mark.asyncio
async def test_chat_raises_when_agent_not_ready(use_case, mock_agent_repo, sample_agent):
    sample_agent.status = "created"
    mock_agent_repo.find_by_id.return_value = sample_agent
    with pytest.raises(AgentNotReadyError):
        await use_case.execute(ChatInput(agent_id=sample_agent.id, message="hello"))


@pytest.mark.asyncio
async def test_chat_returns_response(use_case, mock_agent_repo, mock_memory, mock_llm, sample_agent):
    sample_agent.status = "ready"
    mock_agent_repo.find_by_id.return_value = sample_agent
    mock_memory.search.return_value = [
        SearchResult(text="Relevant context.", score=0.9, source="doc.pdf", page=1)
    ]
    mock_llm.complete.return_value = LLMResponse(
        content="Based on the document...",
        input_tokens=100,
        output_tokens=50,
        model="claude-sonnet-4-20250514",
    )

    result = await use_case.execute(ChatInput(agent_id=sample_agent.id, message="What is the policy?"))

    assert result.response == "Based on the document..."
    assert len(result.sources) == 1
    assert result.sources[0]["source"] == "doc.pdf"
    assert result.input_tokens == 100
