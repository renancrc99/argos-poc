"""
Adaptador para geração de embeddings via Ollama.

Tenta a nova API primeiro (POST /api/embed com "input"),
com fallback para a API antiga (POST /api/embeddings com "prompt").
Se o Ollama não estiver disponível, loga o erro e retorna listas vazias.
"""

import structlog
import httpx

from app.domain.ports.embedding_port import EmbeddingPort

logger = structlog.get_logger()


class OllamaEmbeddingAdapter(EmbeddingPort):
    """Gera embeddings via Ollama local."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def embed(self, text: str) -> list[float]:
        """Gera embedding para um único texto. Retorna lista vazia em caso de falha."""
        # Tenta nova API: POST /api/embed com "input"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": text},
                )
                resp.raise_for_status()
                data = resp.json()
                # Nova API retorna {"embeddings": [[...]], ...}
                embeddings = data.get("embeddings")
                if embeddings and isinstance(embeddings, list) and len(embeddings) > 0:
                    return embeddings[0]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Nova API não existe, tentamos a antiga
                logger.debug("ollama_new_api_not_found", fallback="old_api")
            else:
                logger.warning(
                    "ollama_embed_http_error",
                    model=self._model,
                    status=exc.response.status_code,
                    error=str(exc),
                )
                return []
        except Exception as exc:
            logger.warning("ollama_embed_new_api_failed", model=self._model, error=str(exc))
            # Não retorna aqui — tenta a API antiga abaixo

        # Fallback: API antiga POST /api/embeddings com "prompt"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding")
                if embedding and isinstance(embedding, list):
                    return embedding
        except Exception as exc:
            logger.warning(
                "ollama_embed_old_api_failed",
                model=self._model,
                error=str(exc),
            )

        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Gera embeddings para múltiplos textos.

        Tenta usar a nova API com "input" como lista para eficiência.
        Faz fallback para chamadas individuais se necessário.
        """
        if not texts:
            return []

        # Tenta nova API com lista de inputs
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": texts},
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings")
                if (
                    embeddings
                    and isinstance(embeddings, list)
                    and len(embeddings) == len(texts)
                ):
                    return embeddings
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                logger.warning(
                    "ollama_embed_batch_http_error",
                    model=self._model,
                    status=exc.response.status_code,
                    error=str(exc),
                )
        except Exception as exc:
            logger.warning(
                "ollama_embed_batch_new_api_failed",
                model=self._model,
                count=len(texts),
                error=str(exc),
            )

        # Fallback: chama embed() individualmente
        results: list[list[float]] = []
        for text in texts:
            emb = await self.embed(text)
            results.append(emb)
        return results

    async def is_available(self) -> bool:
        """Retorna True se o Ollama está acessível e o modelo responde."""
        try:
            emb = await self.embed("test")
            return len(emb) > 0
        except Exception as exc:
            logger.debug("ollama_embedding_unavailable", model=self._model, error=str(exc))
            return False
