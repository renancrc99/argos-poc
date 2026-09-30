"""DTOs para operações de Chat."""

from pydantic import BaseModel


class ChatInput(BaseModel):
    agent_id: str
    message: str
    conversation_history: list[dict] | None = None
    benchmark_mode: bool = False
    bm25_weight_override: float | None = None


class ChatOutput(BaseModel):
    response: str
    sources: list[dict]
    input_tokens: int
    output_tokens: int
    model: str
    timings: dict[str, float] | None = None
    llm_calls: int = 1
