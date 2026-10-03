"""DTOs para operações de Agent."""

from pydantic import BaseModel

from app.domain.entities.agent import Agent


class CreateAgentInput(BaseModel):
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


class AgentOutput(BaseModel):
    id: str
    name: str
    description: str
    status: str
    system_prompt: str
    persona: str
    language: str = "pt-BR"
    total_documents: int
    total_chunks: int
    created_at: str
    max_history_messages: int = 10
    max_context_chunks: int = 5
    enable_multiquery: bool = False
    multiquery_variants: int = 3
    use_embeddings: bool = False
    search_mode: str = "bm25"
    enable_reranker: bool = False
    temperature: float = 0.3


def agent_to_output(agent: Agent) -> AgentOutput:
    """Mapeia a entidade Agent para o DTO de saída da API. Fonte única desse mapeamento."""
    return AgentOutput(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        system_prompt=agent.config.system_prompt,
        persona=agent.config.persona,
        language=agent.config.language,
        total_documents=agent.total_documents,
        total_chunks=agent.total_chunks,
        created_at=agent.created_at.isoformat(),
        max_history_messages=agent.config.max_history_messages,
        max_context_chunks=agent.config.max_context_chunks,
        enable_multiquery=agent.config.enable_multiquery,
        multiquery_variants=agent.config.multiquery_variants,
        use_embeddings=agent.config.use_embeddings,
        search_mode=agent.config.search_mode,
        enable_reranker=agent.config.enable_reranker,
        temperature=agent.config.temperature,
    )
