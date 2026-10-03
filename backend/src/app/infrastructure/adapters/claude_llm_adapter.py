"""Adaptador para Claude via API Anthropic."""

import anthropic
import structlog

from app.domain.exceptions import LLMCompletionError
from app.domain.ports.llm_port import LLMPort, LLMMessage, LLMResponse
from app.settings import settings

logger = structlog.get_logger()


class ClaudeLLMAdapter(LLMPort):

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def complete(
        self, messages: list[LLMMessage], max_tokens: int = 1024, temperature: float = 0.3
    ) -> LLMResponse:
        system_content = ""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content += msg.content + "\n"
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_content.strip(),
                messages=api_messages,
            )
            content = response.content[0].text
        except Exception as exc:
            raise LLMCompletionError(f"Falha ao chamar o Claude ({self._model}): {exc}") from exc

        logger.info(
            "llm_call",
            model=self._model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
        )
