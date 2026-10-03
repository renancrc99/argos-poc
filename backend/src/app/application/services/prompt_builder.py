"""Serviço de construção do prompt de chat.

Extraído de ChatWithAgentUseCase: monta as mensagens (system + histórico +
pergunta) a partir da configuração do agente e dos trechos recuperados — uma
responsabilidade isolada ("transformar contexto em mensagens de LLM"),
separada da orquestração do pipeline de RAG (busca, reranking, chamada ao
LLM), que continua no use case.
"""

from app.domain.ports.llm_port import LLMMessage
from app.domain.ports.memory_port import SearchResult
from app.domain.value_objects.agent_config import AgentConfig


class PromptBuilder:
    """Monta a lista de mensagens (system + histórico + pergunta) para o LLM."""

    def build(
        self,
        config: AgentConfig,
        search_results: list[SearchResult],
        conversation_history: list[dict] | None,
        message: str,
    ) -> list[LLMMessage]:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=self._build_system_content(config, search_results))
        ]

        if conversation_history:
            limit = config.max_history_messages
            for msg in conversation_history[-limit:]:
                messages.append(LLMMessage(role=msg["role"], content=msg["content"]))

        messages.append(LLMMessage(role="user", content=message))
        return messages

    def _build_system_content(self, config: AgentConfig, search_results: list[SearchResult]) -> str:
        context_block = "\n\n".join(
            f"[Fonte: {r.source}" + (f", p.{r.page}" if r.page else "") + f" | Score: {r.score:.2f}]\n{r.text}"
            for r in search_results
        ) or "Nenhum contexto encontrado."

        return (
            f"{config.system_prompt}\n\n"
            f"Persona: {config.persona}\n"
            f"Idioma: {config.language}\n\n"
            f"Instruções de resposta:\n"
            f"- Responda SOMENTE com base no contexto recuperado abaixo.\n"
            f"- Antes de responder, analise CADA trecho e determine:\n"
            f"  (a) Quem é o SUJEITO (quem pratica a ação)?\n"
            f"  (b) Quem é o OBJETO/PACIENTE (quem recebe a ação)?\n"
            f"  Se a pergunta é sobre 'o que foi feito a X', use SOMENTE trechos onde X é o PACIENTE.\n"
            f"  Descarte trechos onde X é o SUJEITO praticando a mesma ação — são eventos distintos.\n"
            f"- NUNCA invente, suponha ou acrescente fatos que não estejam escritos no contexto. "
            f"Se um detalhe não aparecer explicitamente, não o inclua na resposta.\n"
            f"- Se o contexto contiver a informação, cite o trecho relevante para embasar a resposta.\n"
            f"- Se o contexto NÃO contiver a informação necessária para responder com segurança, "
            f"diga claramente que o trecho recuperado não cobre esse ponto e use o fallback.\n"
            f"- Fallback: \"{config.fallback_message}\"\n\n"
            f"--- CONTEXTO RECUPERADO ---\n{context_block}\n--- FIM DO CONTEXTO ---"
        )
