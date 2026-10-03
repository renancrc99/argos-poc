"""Endpoints de debug/inspeção do RAG. Apenas para desenvolvimento."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.container import container
from app.application.services.text_analysis import tokenize, query_bm25_weight

router = APIRouter(prefix="/agents/{agent_id}/debug", tags=["debug"])


class DebugSearchResult(BaseModel):
    rank: int
    score: float
    source: str
    page: int | None
    text: str


class DebugSearchResponse(BaseModel):
    agent_id: str
    query: str
    query_tokens: list[str]
    index_stats: dict
    results: list[DebugSearchResult]
    search_mode: str
    bm25_weight: float
    embedding_available: bool


@router.get("/search", response_model=DebugSearchResponse)
async def debug_search(
    agent_id: str,
    q: str = Query(..., description="Query de busca"),
    top_k: int = Query(default=10, ge=1, le=50),
    search_mode: str = Query(default="bm25", description="Modo de busca: bm25, semantic, hybrid"),
):
    """
    Inspeciona o que o retriever recupera para uma query.
    Útil para entender por que o RAG está respondendo bem ou mal.
    Suporta modos: bm25 (padrão), semantic, hybrid.
    """
    if search_mode not in ("bm25", "semantic", "hybrid"):
        raise HTTPException(
            status_code=422,
            detail="search_mode must be one of: bm25, semantic, hybrid",
        )

    agent = await container.agent_repo.find_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    bm25_weight = query_bm25_weight(q)

    # Verifica disponibilidade do embedding
    embedding_available = False
    if container.embedding is not None:
        try:
            embedding_available = await container.embedding.is_available()
        except Exception:
            embedding_available = False

    results = await container.memory.search(
        agent_id=agent_id,
        query=q,
        top_k=top_k,
        search_mode=search_mode,
        bm25_weight=bm25_weight,
    )
    stats = await container.memory.index_stats(agent_id=agent_id)

    return DebugSearchResponse(
        agent_id=agent_id,
        query=q,
        query_tokens=tokenize(q),
        index_stats=stats,
        results=[
            DebugSearchResult(
                rank=i + 1,
                score=r.score,
                source=r.source,
                page=r.page,
                text=r.text,
            )
            for i, r in enumerate(results)
        ],
        search_mode=search_mode,
        bm25_weight=bm25_weight,
        embedding_available=embedding_available,
    )


class DebugMultiqueryResponse(BaseModel):
    agent_id: str
    original_query: str
    variants: list[str]
    all_queries: list[str]
    index_stats: dict
    results: list[DebugSearchResult]


@router.get("/multiquery", response_model=DebugMultiqueryResponse)
async def debug_multiquery(
    agent_id: str,
    q: str = Query(..., description="Query original"),
    variants: int = Query(default=3, ge=1, le=5),
    top_k: int = Query(default=10, ge=1, le=50),
):
    """
    Testa o multiquery: expande a query com o LLM e mostra os resultados mesclados.
    """
    agent = await container.agent_repo.find_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    expanded = await container.chat_with_agent.expand_query(q, variants)
    all_queries = [q] + expanded

    results = await container.memory.search_multi(
        agent_id=agent_id, queries=all_queries, top_k=top_k
    )
    stats = await container.memory.index_stats(agent_id=agent_id)

    return DebugMultiqueryResponse(
        agent_id=agent_id,
        original_query=q,
        variants=expanded,
        all_queries=all_queries,
        index_stats=stats,
        results=[
            DebugSearchResult(rank=i + 1, score=r.score, source=r.source, page=r.page, text=r.text)
            for i, r in enumerate(results)
        ],
    )
