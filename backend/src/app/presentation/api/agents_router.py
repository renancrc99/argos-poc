"""Routes para CRUD de agentes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.container import container
from app.application.dtos.agent_dtos import CreateAgentInput
from app.domain.exceptions import AgentNotFoundError

router = APIRouter(prefix="/agents", tags=["agents"])


class CreateAgentRequest(BaseModel):
    name: str
    description: str
    system_prompt: str
    persona: str = "cordial e objetivo"
    language: str = "pt-BR"
    max_history_messages: int = 10
    max_context_chunks: int = 5
    enable_multiquery: bool = False
    multiquery_variants: int = 3
    use_embeddings: bool = False
    search_mode: str = "bm25"
    enable_reranker: bool = False
    temperature: float = 0.3

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if v < 0.0 or v > 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("max_history_messages")
    @classmethod
    def validate_history(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("max_history_messages must be between 1 and 100")
        return v

    @field_validator("max_context_chunks")
    @classmethod
    def validate_chunks(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("max_context_chunks must be between 1 and 20")
        return v

    @field_validator("multiquery_variants")
    @classmethod
    def validate_variants(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("multiquery_variants must be between 1 and 5")
        return v

    @field_validator("search_mode")
    @classmethod
    def validate_search_mode(cls, v: str) -> str:
        if v not in ("bm25", "semantic", "hybrid"):
            raise ValueError("search_mode must be bm25, semantic, or hybrid")
        return v


@router.post("", status_code=201)
async def create_agent(req: CreateAgentRequest):
    result = await container.create_agent.execute(
        CreateAgentInput(
            name=req.name,
            description=req.description,
            system_prompt=req.system_prompt,
            persona=req.persona,
            language=req.language,
            max_history_messages=req.max_history_messages,
            max_context_chunks=req.max_context_chunks,
            enable_multiquery=req.enable_multiquery,
            multiquery_variants=req.multiquery_variants,
            use_embeddings=req.use_embeddings,
            search_mode=req.search_mode,
            enable_reranker=req.enable_reranker,
            temperature=req.temperature,
        )
    )
    return result


@router.get("")
async def list_agents():
    return await container.list_agents.execute()


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str):
    try:
        await container.delete_agent.execute(agent_id)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    try:
        return await container.get_agent.execute(agent_id)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
