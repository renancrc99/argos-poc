"""Entidade Agent — representa um agente de suporte configurado para um cliente."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.value_objects.agent_config import AgentConfig


class Agent(BaseModel):
    """Entidade raiz do agregado Agent."""

    name: str
    description: str
    config: AgentConfig
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["created", "ready", "error"] = "created"
    total_documents: int = 0
    total_chunks: int = 0
    memory_version: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_as_ready(self, total_chunks: int, memory_version: str) -> None:
        """Marca o agente como pronto após ingestão bem-sucedida."""
        self.status = "ready"
        self.total_chunks = total_chunks
        self.memory_version = memory_version
        self.updated_at = datetime.now(timezone.utc)

    def increment_documents(self, count: int = 1) -> None:
        self.total_documents += count
        self.updated_at = datetime.now(timezone.utc)
