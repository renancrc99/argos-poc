"""Caso de uso: conversar com um agente via RAG."""

import json
import re
import structlog

from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.ports.memory_port import MemoryPort, SearchResult
from app.domain.ports.llm_port import LLMPort, LLMMessage
from app.domain.exceptions import AgentNotFoundError, AgentNotReadyError
from app.application.dtos.chat_dtos import ChatInput, ChatOutput
from app.application.services import benchmark_timing as bt
from app.application.services.prompt_builder import PromptBuilder
from app.application.services.text_analysis import query_bm25_weight
from app.settings import settings

logger = structlog.get_logger()


class ChatWithAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepositoryPort,
        memory: MemoryPort,
        llm: LLMPort,
        prompt_builder: PromptBuilder | None = None,
    ):
        self._agent_repo = agent_repo
        self._memory = memory
        self._llm = llm
        self._prompt_builder = prompt_builder or PromptBuilder()

    # ------------------------------------------------------------------
    # Multiquery
    # ------------------------------------------------------------------

    async def expand_query(self, query: str, n: int, temperature: float = 0.3) -> list[str]:
        """Pede ao LLM n variações da query para ampliar o recall do BM25."""
        prompt = (
            f"You must produce exactly {n} alternative search queries for the question below.\n"
            f"Rules:\n"
            f"- Each query must use different words and phrasing than the original.\n"
            f"- Focus on synonyms, related concepts, and different angles.\n"
            f"- Output ONLY a JSON array with exactly {n} strings. No explanation, no markdown.\n"
            f"- Example format: [\"query one\", \"query two\", \"query three\"]\n\n"
            f"Original question: {query}\n\n"
            f"JSON array with {n} alternatives:"
        )
        try:
            with bt.stage("t_expansion"):
                response = await self._llm.complete(
                    messages=[LLMMessage(role="user", content=prompt)],
                    max_tokens=300,
                    temperature=temperature,
                )
            match = re.search(r"\[.*?\]", response.content, re.DOTALL)
            if match:
                variants = json.loads(match.group())
                if isinstance(variants, list):
                    valid = [v for v in variants if isinstance(v, str) and v.strip()][:n]
                    logger.info("multiquery_expanded", original=query, variants=valid)
                    return valid
        except Exception as exc:
            logger.warning("multiquery_failed", error=str(exc))
        return []

    # ------------------------------------------------------------------
    # Reranker via LLM
    # ------------------------------------------------------------------

    async def _rerank(
        self, query: str, results: list[SearchResult], top_n: int, temperature: float = 0.3
    ) -> list[SearchResult]:
        """
        Pede ao LLM uma nota de relevância pra cada chunk em relação à query.
        Retorna os top_n resultados reordenados.
        Se o LLM falhar, retorna results[:top_n] sem reordenar.
        """
        if not results:
            return results

        n = len(results)
        numbered = "\n\n".join(
            f"[{i + 1}] {r.text[:400]}" for i, r in enumerate(results)
        )
        prompt = (
            f"You are a relevance scoring system. Score each passage for how directly it answers the query.\n"
            f"Scoring guide:\n"
            f"  1.0 = directly and completely answers the query\n"
            f"  0.7 = contains clearly related information\n"
            f"  0.4 = partially related or background context\n"
            f"  0.1 = loosely related topic\n"
            f"  0.0 = unrelated or contradicts the query\n\n"
            f"CRITICAL rules:\n"
            f"- Pay close attention to WHO does WHAT to WHOM. "
            f"A passage where 'A stabs B' is NOT relevant to a query asking 'What stabbed A'.\n"
            f"- If a passage mentions the query's subject but in the opposite role (agent vs patient), score it 0.1 or lower.\n"
            f"- Return ONLY a JSON array of exactly {n} floats. No text, no markdown. "
            f"Example for {n} passages: {str([0.0] * n)}\n\n"
            f"Query: {query}\n\n"
            f"Passages:\n{numbered}\n\n"
            f"JSON array of {n} scores:"
        )
        try:
            with bt.stage("t_rerank"):
                resp = await self._llm.complete(
                    [LLMMessage(role="user", content=prompt)], max_tokens=128, temperature=temperature
                )
            match = re.search(r'\[.*?\]', resp.content, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                if isinstance(scores, list) and len(scores) == len(results):
                    paired = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
                    return [r for r, _ in paired[:top_n]]
        except Exception as exc:
            logger.warning("reranker_failed", error=str(exc))
        return results[:top_n]

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    async def execute(self, input_dto: ChatInput) -> ChatOutput:
        """Ponto de entrada público. Em modo benchmark, abre uma sessão de
        cronometragem por etapa e anexa os tempos coletados ao ChatOutput."""
        if not input_dto.benchmark_mode:
            return await self._execute_inner(input_dto)

        with bt.session() as timings:
            with bt.stage("t_total"):
                output = await self._execute_inner(input_dto)
            output.timings = timings
            return output

    async def _execute_inner(self, input_dto: ChatInput) -> ChatOutput:
        agent = await self._agent_repo.find_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.status != "ready":
            raise AgentNotReadyError(input_dto.agent_id)

        top_k = agent.config.max_context_chunks
        bm25_weight = (
            input_dto.bm25_weight_override
            if input_dto.bm25_weight_override is not None
            else query_bm25_weight(input_dto.message)
        )
        search_mode = agent.config.effective_search_mode()

        logger.debug(
            "rag_search_params",
            agent_id=agent.id,
            use_embeddings=agent.config.use_embeddings,
            search_mode=search_mode,
            bm25_weight=bm25_weight,
        )

        fetch_k = agent.config.fetch_k(top_k, settings.reranker_candidates_multiplier)
        llm_calls = 1  # geração final, sempre acontece — somamos expansão/reranker abaixo se ativos

        # --- Recuperação RAG ---
        if agent.config.enable_multiquery:
            llm_calls += 1
            variants = await self.expand_query(
                input_dto.message, agent.config.multiquery_variants, agent.config.temperature
            )
            all_queries = [input_dto.message] + variants
            search_results = await self._memory.search_multi(
                agent_id=agent.id,
                queries=all_queries,
                top_k=fetch_k,
                search_mode=search_mode,
                bm25_weight=bm25_weight,
            )
            logger.info(
                "rag_multiquery",
                agent_id=agent.id,
                queries=len(all_queries),
                hits=len(search_results),
                search_mode=search_mode,
                bm25_weight=bm25_weight,
            )
        else:
            search_results = await self._memory.search(
                agent_id=agent.id,
                query=input_dto.message,
                top_k=fetch_k,
                search_mode=search_mode,
                bm25_weight=bm25_weight,
            )
            logger.info(
                "rag_search",
                agent_id=agent.id,
                hits=len(search_results),
                search_mode=search_mode,
                bm25_weight=bm25_weight,
            )

        # --- Reranqueamento ---
        if agent.config.enable_reranker and search_results:
            llm_calls += 1
            logger.debug(
                "reranker_start",
                agent_id=agent.id,
                candidates=len(search_results),
                target=top_k,
            )
            search_results = await self._rerank(
                query=input_dto.message,
                results=search_results,
                top_n=top_k,
                temperature=agent.config.temperature,
            )
            logger.info(
                "reranker_done",
                agent_id=agent.id,
                returned=len(search_results),
            )

        for i, r in enumerate(search_results):
            logger.debug("rag_chunk", index=i, source=r.source, score=r.score, snippet=r.text[:80])

        with bt.stage("t_prompt_build"):
            messages = self._prompt_builder.build(
                config=agent.config,
                search_results=search_results,
                conversation_history=input_dto.conversation_history,
                message=input_dto.message,
            )

        llm_response = await self._llm.complete(messages=messages, temperature=agent.config.temperature)

        logger.info(
            "chat_completed",
            agent_id=agent.id,
            sources=len(search_results),
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

        return ChatOutput(
            response=llm_response.content,
            sources=[
                {
                    "source": r.source,
                    "page": r.page,
                    "score": round(r.score, 3),
                    "snippet": r.text[:150],
                    # Texto completo do chunk, só em modo benchmark — o snippet
                    # truncado não é suficiente pra calcular sobreposição com
                    # trechos anotados que não caem logo no início do chunk.
                    "text": r.text if input_dto.benchmark_mode else None,
                }
                for r in search_results
            ],
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            model=llm_response.model,
            llm_calls=llm_calls,
        )
