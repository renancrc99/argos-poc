"""Test configuration and shared fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.domain.entities.agent import Agent
from app.domain.value_objects.agent_config import AgentConfig


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    return AgentConfig(system_prompt="You are a helpful assistant.")


@pytest.fixture
def sample_agent(sample_agent_config: AgentConfig) -> Agent:
    return Agent(
        id="test-agent-id",
        name="Test Agent",
        description="A test agent",
        config=sample_agent_config,
    )


@pytest.fixture
def mock_agent_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_memory():
    return AsyncMock()


@pytest.fixture
def mock_llm():
    return AsyncMock()
