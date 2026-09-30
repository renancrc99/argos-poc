"""Objeto de Valor para configuração do agente."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """Configuração imutável do comportamento do agente.

    Os limites abaixo (Field ge/le) fazem o objeto de valor proteger suas
    próprias invariantes — ele é válido por construção, sem depender de quem
    o cria também revalidar os limites (hoje a API já valida os mesmos limites
    em CreateAgentRequest, mas isso é defesa em profundidade: qualquer outro
    caminho que monte um AgentConfig diretamente — testes, use cases futuros —
    ganha a mesma garantia sem precisar lembrar de repetir a validação).
    """

    model_config = ConfigDict(frozen=True)

    system_prompt: str
    persona: str = "cordial e objetivo"
    language: str = "pt-BR"
    fallback_message: str = "Não encontrei informação sobre isso na minha base. Posso te ajudar com outra coisa?"
    max_context_chunks: int = Field(default=5, ge=1, le=20)
    max_history_messages: int = Field(default=10, ge=1, le=100)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    enable_multiquery: bool = False
    multiquery_variants: int = Field(default=3, ge=1, le=5)
    use_embeddings: bool = False       # quando True, sobrescreve search_mode para "hybrid" adaptativo
    search_mode: Literal["bm25", "semantic", "hybrid"] = "bm25"  # ignorado se use_embeddings=True
    enable_reranker: bool = False

    def effective_search_mode(self) -> str:
        """Retorna o modo de busca que deve ser usado, considerando use_embeddings."""
        return "hybrid" if self.use_embeddings else self.search_mode

    def fetch_k(self, top_k: int, candidates_multiplier: int) -> int:
        """Retorna quantos candidatos buscar antes do corte final, considerando o reranker."""
        return top_k * candidates_multiplier if self.enable_reranker else top_k
