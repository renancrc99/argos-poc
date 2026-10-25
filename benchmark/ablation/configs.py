"""Configurações do estudo de ablação — especificação §4.1 e §4.2.

Mapeamento validado contra o código real do backend (`AgentConfig.effective_search_mode()`,
`domain/value_objects/agent_config.py`): `use_embeddings=True` força modo "hybrid"
independente de `search_mode`; só com `use_embeddings=False` o `search_mode`
("bm25" | "semantic") explícito é respeitado. Por isso a config A (vetorial
pura) usa `use_embeddings=False, search_mode="semantic"` — não é um erro.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AblationConfig:
    letter: str
    label: str
    use_embeddings: bool
    search_mode: str
    enable_multiquery: bool
    enable_reranker: bool

    def agent_payload_overrides(self) -> dict:
        return {
            "use_embeddings": self.use_embeddings,
            "search_mode": self.search_mode,
            "enable_multiquery": self.enable_multiquery,
            "enable_reranker": self.enable_reranker,
        }


ABLATION_CONFIGS: dict[str, AblationConfig] = {
    "A": AblationConfig("A", "Vetorial pura", use_embeddings=False, search_mode="semantic",
                         enable_multiquery=False, enable_reranker=False),
    "B": AblationConfig("B", "Léxica pura (BM25)", use_embeddings=False, search_mode="bm25",
                         enable_multiquery=False, enable_reranker=False),
    "C": AblationConfig("C", "Híbrida (base)", use_embeddings=True, search_mode="bm25",
                         enable_multiquery=False, enable_reranker=False),
    "D": AblationConfig("D", "Híbrida + expansão", use_embeddings=True, search_mode="bm25",
                         enable_multiquery=True, enable_reranker=False),
    "E": AblationConfig("E", "Híbrida + reranking", use_embeddings=True, search_mode="bm25",
                         enable_multiquery=False, enable_reranker=True),
    "F": AblationConfig("F", "Completa (produção)", use_embeddings=True, search_mode="bm25",
                         enable_multiquery=True, enable_reranker=True),
}


@dataclass(frozen=True)
class ChunkingProfile:
    name: str
    chunk_size: int | None  # None = automático (deixa o backend decidir)
    chunk_overlap: int | None


# Perfis do experimento de chunking (especificação §4.2) — médio/grande usam os
# mesmos valores 1024/128 e 2048/256 do default interno real do backend
# (ChunkingService.resolve_params, alinhado à especificação desde 2026-09-27).
# A unidade continua divergindo (caracteres, não tokens — ver
# divergencias-especificacao-vs-implementacao.md, item 6). "automatico" deixa
# o backend decidir sozinho com base no tamanho do documento; os demais
# perfis passam chunk_size/chunk_overlap explícitos na ingestão.
CHUNKING_PROFILES: dict[str, ChunkingProfile] = {
    "automatico": ChunkingProfile("automatico", None, None),
    "pequeno": ChunkingProfile("pequeno", 512, 64),
    "medio": ChunkingProfile("medio", 1024, 128),
    "grande": ChunkingProfile("grande", 2048, 256),
}


# AgentConfig.fallback_message não é exposto por GET /agents/{id} — como os
# agentes de ablação nunca sobrescrevem esse campo, usamos aqui o mesmo valor
# padrão do domínio (domain/value_objects/agent_config.py) pra detectar fallback
# nas respostas. Se o default mudar no backend, atualizar aqui também.
DEFAULT_FALLBACK_MESSAGE = "Não encontrei informação sobre isso na minha base. Posso te ajudar com outra coisa?"

DEFAULT_AGENT_DEFAULTS = {
    "system_prompt": (
        "Você é um assistente que responde SOMENTE com base nos documentos fornecidos. "
        "Se a informação não estiver no contexto recuperado, diga claramente que não sabe."
    ),
    "persona": "objetivo e técnico",
    "language": "pt-BR",
    "max_history_messages": 10,
    "max_context_chunks": 5,
    "multiquery_variants": 3,
    "temperature": 0,
}
