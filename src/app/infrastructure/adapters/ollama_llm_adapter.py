"""Adaptador para LLM local via Ollama."""

import json
import time

import httpx
import structlog

from app.application.services import benchmark_timing as bt
from app.domain.exceptions import LLMCompletionError
from app.domain.ports.llm_port import LLMPort, LLMMessage, LLMResponse
from app.settings import settings

logger = structlog.get_logger()


class OllamaLLMAdapter(LLMPort):
    """Chama o Ollama local usando /api/chat com array de mensagens."""

    def __init__(self):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    async def complete(
        self, messages: list[LLMMessage], max_tokens: int = 1024, temperature: float = 0.3
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }

        logger.debug("ollama_request", model=self._model, messages_count=len(messages))

        try:
            with bt.stage("t_llm_total"):
                if bt.is_active():
                    # Em modo benchmark, usa streaming pra conseguir medir t_llm_ttft
                    # (tempo até o primeiro token) — a chamada não-streaming não expõe isso.
                    content, prompt_tokens, completion_tokens = await self._complete_streaming(payload)
                else:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(f"{self._base_url}/api/chat", json=payload)
                        response.raise_for_status()
                        data = response.json()
                    content = data["message"]["content"]
                    prompt_tokens = data.get("prompt_eval_count", 0)
                    completion_tokens = data.get("eval_count", 0)
        except Exception as exc:
            raise LLMCompletionError(f"Falha ao chamar o Ollama ({self._model}): {exc}") from exc

        logger.info(
            "ollama_call",
            model=self._model,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
        )

        return LLMResponse(
            content=content,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            model=self._model,
        )

    async def _complete_streaming(self, payload: dict) -> tuple[str, int, int]:
        """
        Chama /api/chat com stream=true e registra t_llm_ttft no instante em que o
        primeiro pedaço de conteúdo chega. Ollama retorna um objeto JSON por linha;
        o último tem done=true e carrega as contagens finais de tokens.
        """
        stream_payload = {**payload, "stream": True}
        content_parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        request_start = time.perf_counter()
        first_token_seen = False

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", f"{self._base_url}/api/chat", json=stream_payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    chunk_content = data.get("message", {}).get("content", "")
                    if chunk_content:
                        if not first_token_seen:
                            first_token_seen = True
                            bt.record("t_llm_ttft", time.perf_counter() - request_start)
                        content_parts.append(chunk_content)
                    if data.get("done"):
                        prompt_tokens = data.get("prompt_eval_count", 0)
                        completion_tokens = data.get("eval_count", 0)

        return "".join(content_parts), prompt_tokens, completion_tokens
