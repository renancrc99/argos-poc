"""Porta para persistência de agentes."""

from abc import ABC, abstractmethod

from app.domain.entities.agent import Agent


class AgentRepositoryPort(ABC):

    @abstractmethod
    async def save(self, agent: Agent) -> None:
        ...

    @abstractmethod
    async def find_by_id(self, agent_id: str) -> Agent | None:
        ...

    @abstractmethod
    async def find_all(self) -> list[Agent]:
        ...

    @abstractmethod
    async def update(self, agent: Agent) -> None:
        ...

    @abstractmethod
    async def delete(self, agent_id: str) -> None:
        ...
