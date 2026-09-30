"""Porta para chamadas ao LLM (Claude, GPT, etc)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class LLMMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMPort(ABC):
    """Interface para completions de LLM."""

    @abstractmethod
    async def complete(
        self, messages: list[LLMMessage], max_tokens: int = 1024, temperature: float = 0.3
    ) -> LLMResponse:
        """Envia mensagens ao LLM e retorna a resposta."""
        ...
