"""
Adaptador de memória vetorial usando BM25 + persistência JSON.

Suporta três modos de busca:
  - "bm25"     : busca léxica clássica (padrão)
  - "semantic" : busca por similaridade coseno via embeddings
  - "hybrid"   : combina BM25 e semântico com peso adaptativo

A interface pública (MemoryPort) não muda — o restante da aplicação
não sabe que o backend mudou. (OCP + DIP)
"""

import hashlib
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from app.domain.exceptions import MemoryIngestionError
from app.domain.ports.memory_port import MemoryPort, SearchResult
from app.domain.value_objects.chunk import Chunk
from app.application.services import benchmark_timing as bt
from app.application.services.text_analysis import cosine_similarity, tokenize
from app.settings import settings

if TYPE_CHECKING:
    from app.domain.ports.embedding_port import EmbeddingPort

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class BM25Index:
    """Índice BM25 em memória com persistência em JSON e suporte a embeddings."""

    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self.docs: list[dict] = []           # [{text, source, page, index, embedding?}, ...]
        self.tokenized: list[list[str]] = []
        self._df: dict[str, int] = {}        # frequência do termo entre os documentos
        self._avgdl: float = 0.0

    def add(
        self,
        text: str,
        source: str,
        page: int | None,
        index: int,
        embedding: list[float] | None = None,
    ) -> None:
        """Adiciona um documento ao índice, com embedding opcional."""
        tokens = tokenize(text)
        doc: dict = {"text": text, "source": source, "page": page, "index": index}
        if embedding is not None:
            doc["embedding"] = embedding
        self.docs.append(doc)
        self.tokenized.append(tokens)
        for term in set(tokens):
            self._df[term] = self._df.get(term, 0) + 1
        total_len = sum(len(t) for t in self.tokenized)
        self._avgdl = total_len / len(self.tokenized)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Busca BM25 clássica."""
        if not self.docs:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []

        n = len(self.docs)
        scores: list[float] = []

        for i, tokens in enumerate(self.tokenized):
            dl = len(tokens)
            tf_map: dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1

            score = 0.0
            for term in query_terms:
                tf = tf_map.get(term, 0)
                df = self._df.get(term, 0)
                if tf == 0 or df == 0:
                    continue
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
                norm_tf = (tf * (self.K1 + 1)) / (
                    tf + self.K1 * (1 - self.B + self.B * dl / self._avgdl)
                )
                score += idf * norm_tf
            scores.append(score)

        ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)[:top_k]
        max_score = scores[ranked[0]] if scores[ranked[0]] > 0 else 1.0

        return [
            SearchResult(
                text=self.docs[i]["text"],
                score=round(scores[i] / max_score, 4),
                source=self.docs[i]["source"],
                page=self.docs[i]["page"],
            )
            for i in ranked
            if scores[i] > 0
        ]

    def search_semantic(
        self, query_emb: list[float], top_k: int = 5
    ) -> list[SearchResult]:
        """Busca por similaridade coseno usando embeddings armazenados."""
        if not self.docs or not query_emb:
            return []

        scored: list[tuple[int, float]] = []
        for i, doc in enumerate(self.docs):
            doc_emb = doc.get("embedding")
            if not doc_emb:
                continue
            sim = cosine_similarity(query_emb, doc_emb)
            scored.append((i, sim))

        if not scored:
            return []

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        return [
            SearchResult(
                text=self.docs[i]["text"],
                score=round(sim, 4),
                source=self.docs[i]["source"],
                page=self.docs[i]["page"],
            )
            for i, sim in top
            if sim > 0
        ]

    def search_hybrid(
        self,
        query: str,
        query_emb: list[float],
        bm25_weight: float,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Busca híbrida: combina BM25 e similaridade semântica.

        Busca 2*top_k candidatos de cada método e combina os scores.
        score = bm25_weight * bm25_norm + (1 - bm25_weight) * cosine
        """
        candidates = top_k * 2

        # Scores do BM25 normalizados
        with bt.stage("t_search_lexical"):
            bm25_results = self.search(query, top_k=candidates)
        bm25_score_map: dict[str, float] = {r.text: r.score for r in bm25_results}

        # Scores semânticos (cosseno bruto, sem normalizar)
        semantic_scored: dict[str, float] = {}
        if query_emb:
            with bt.stage("t_search_vector"):
                for i, doc in enumerate(self.docs):
                    doc_emb = doc.get("embedding")
                    if not doc_emb:
                        continue
                    sim = cosine_similarity(query_emb, doc_emb)
                    if sim > 0:
                        semantic_scored[doc["text"]] = sim

        with bt.stage("t_fusion"):
            # Normaliza os scores semânticos para [0, 1]
            if semantic_scored:
                max_sem = max(semantic_scored.values())
                if max_sem > 0:
                    semantic_scored = {k: v / max_sem for k, v in semantic_scored.items()}

            # Coleta candidatos únicos entre os melhores de cada método
            candidate_texts: set[str] = set(bm25_score_map.keys())
            # Adiciona os melhores candidatos semânticos
            sem_top = sorted(semantic_scored.items(), key=lambda x: x[1], reverse=True)[
                :candidates
            ]
            candidate_texts.update(t for t, _ in sem_top)

            # Mapeia texto -> doc para recuperar source/page
            text_to_doc: dict[str, dict] = {d["text"]: d for d in self.docs}

            # Combina os scores
            combined: list[tuple[str, float]] = []
            for text in candidate_texts:
                doc = text_to_doc.get(text)
                if not doc:
                    continue
                bm25_s = bm25_score_map.get(text, 0.0)
                sem_s = semantic_scored.get(text, 0.0)
                score = bm25_weight * bm25_s + (1.0 - bm25_weight) * sem_s
                combined.append((text, score))

            combined.sort(key=lambda x: x[1], reverse=True)
            top = combined[:top_k]

        return [
            SearchResult(
                text=text,
                score=round(score, 4),
                source=text_to_doc[text]["source"],
                page=text_to_doc[text]["page"],
            )
            for text, score in top
            if score > 0
        ]

    @property
    def total_docs(self) -> int:
        return len(self.docs)

    def to_dict(self) -> dict:
        """Serializa o índice, incluindo embeddings se presentes."""
        return {"docs": self.docs}

    @classmethod
    def from_dict(cls, data: dict) -> "BM25Index":
        """Desserializa o índice. Tolera docs sem campo 'embedding' (índices antigos)."""
        idx = cls()
        for doc in data.get("docs", []):
            idx.add(
                text=doc["text"],
                source=doc["source"],
                page=doc.get("page"),
                index=doc.get("index", 0),
                embedding=doc.get("embedding"),  # None se ausente — suporte a índices antigos
            )
        return idx


# ---------------------------------------------------------------------------
# Adaptador
# ---------------------------------------------------------------------------

class MemvidMemoryAdapter(MemoryPort):

    def __init__(self, embedding: "EmbeddingPort | None" = None) -> None:
        self._cache_dir = Path(settings.memvid_cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._embedding = embedding

    def _index_path(self, agent_id: str) -> Path:
        return self._cache_dir / f"{agent_id}.json"

    def _load(self, agent_id: str) -> BM25Index:
        path = self._index_path(agent_id)
        if path.exists():
            return BM25Index.from_dict(json.loads(path.read_text(encoding="utf-8")))
        return BM25Index()

    def _save(self, agent_id: str, index: BM25Index) -> None:
        path = self._index_path(agent_id)
        path.write_text(json.dumps(index.to_dict(), ensure_ascii=False), encoding="utf-8")
        logger.debug("memory_saved", agent_id=agent_id, docs=len(index.docs), path=str(path))

    async def create_memory(self, agent_id: str) -> str:
        path = self._index_path(agent_id)
        self._save(agent_id, BM25Index())
        logger.info("memory_created", agent_id=agent_id, path=str(path))
        return str(path)

    async def ingest_chunks(
        self, agent_id: str, chunks: list[Chunk], embed: bool = False
    ) -> int:
        """
        Ingere chunks na memória do agente.

        Se embed=True e embedding port disponível, gera e armazena embeddings.
        """
        index = self._load(agent_id)

        embeddings: list[list[float]] = []
        if embed and self._embedding is not None:
            try:
                texts = [c.text for c in chunks]
                with bt.stage("t_embedding"):
                    embeddings = await self._embedding.embed_batch(texts)
                logger.info(
                    "ingest_embeddings_generated",
                    agent_id=agent_id,
                    count=len(embeddings),
                )
            except Exception as exc:
                logger.warning(
                    "ingest_embed_failed",
                    agent_id=agent_id,
                    error=str(exc),
                )
                embeddings = []

        try:
            with bt.stage("t_indexing"):
                for i, chunk in enumerate(chunks):
                    emb = embeddings[i] if i < len(embeddings) and embeddings[i] else None
                    index.add(
                        text=chunk.text,
                        source=chunk.source_document,
                        page=chunk.page,
                        index=chunk.index,
                        embedding=emb,
                    )
                self._save(agent_id, index)
        except Exception as exc:
            raise MemoryIngestionError(agent_id, reason=str(exc)) from exc

        logger.info(
            "memory_ingested",
            agent_id=agent_id,
            new_chunks=len(chunks),
            total=len(index.docs),
            embedded=len(embeddings) > 0,
        )
        return len(chunks)

    async def _warn_if_stale_index(self, index: "BM25Index", agent_id: str) -> None:
        """Avisa quando o índice tem chunks mas nenhum com embedding (ingeridos antes de EMBEDDING_ENABLED=true)."""
        chunks_with_emb = sum(1 for d in index.docs if d.get("embedding"))
        if chunks_with_emb == 0 and index.total_docs > 0:
            logger.warning(
                "hybrid_stale_index",
                agent_id=agent_id,
                total_chunks=index.total_docs,
                chunks_with_embeddings=0,
                hint="Reingira os documentos com EMBEDDING_ENABLED=true para ativar a busca semântica",
            )

    async def _resolve_search_results(
        self,
        index: "BM25Index",
        agent_id: str,
        query: str,
        top_k: int,
        search_mode: str,
        bm25_weight: float,
        embedding_cache: dict[str, list[float]] | None = None,
    ) -> list[SearchResult]:
        """
        Resolve os resultados de busca para uma query, aplicando o modo pedido.
        Se embedding indisponível (ou o índice não tiver embeddings) e mode != "bm25", fallback para BM25.
        Compartilhado por search() e search_multi() — único lugar que decide o modo de busca.

        embedding_cache, quando fornecido, evita recalcular o embedding de uma query repetida
        (search_multi passa um cache compartilhado entre as várias queries da mesma chamada).
        """
        if search_mode in ("semantic", "hybrid"):
            if self._embedding is None:
                logger.warning(
                    "search_mode_fallback",
                    reason="embedding_port_not_configured",
                    fallback="bm25",
                    agent_id=agent_id,
                )
                with bt.stage("t_search_lexical"):
                    return index.search(query, top_k=top_k)

            await self._warn_if_stale_index(index, agent_id)

            with bt.stage("t_embed_query"):
                if embedding_cache is not None:
                    if query not in embedding_cache:
                        embedding_cache[query] = await self._embedding.embed(query)
                    query_emb = embedding_cache[query]
                else:
                    query_emb = await self._embedding.embed(query)
            if not query_emb:
                logger.warning(
                    "search_mode_fallback",
                    reason="embed_returned_empty",
                    fallback="bm25",
                    agent_id=agent_id,
                )
                with bt.stage("t_search_lexical"):
                    return index.search(query, top_k=top_k)

            if search_mode == "semantic":
                with bt.stage("t_search_vector"):
                    return index.search_semantic(query_emb, top_k=top_k)
            return index.search_hybrid(
                query=query, query_emb=query_emb, bm25_weight=bm25_weight, top_k=top_k
            )

        with bt.stage("t_search_lexical"):
            return index.search(query, top_k=top_k)  # "bm25" — comportamento original preservado

    async def search(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
        search_mode: str = "bm25",
        bm25_weight: float = 0.5,
    ) -> list[SearchResult]:
        """
        Busca na memória do agente.

        Modos suportados: "bm25", "semantic", "hybrid".
        Se embedding indisponível e mode != "bm25", fallback para BM25.
        """
        index = self._load(agent_id)
        results = await self._resolve_search_results(
            index, agent_id, query, top_k, search_mode, bm25_weight
        )

        logger.debug(
            "memory_search",
            agent_id=agent_id,
            query=query,
            mode=search_mode,
            bm25_weight=bm25_weight,
            hits=len(results),
        )
        for i, r in enumerate(results):
            logger.debug(
                "memory_hit",
                rank=i,
                source=r.source,
                score=r.score,
                snippet=r.text[:80],
            )
        return results

    async def search_multi(
        self,
        agent_id: str,
        queries: list[str],
        top_k: int = 5,
        search_mode: str = "bm25",
        bm25_weight: float = 0.5,
    ) -> list[SearchResult]:
        """
        Busca com múltiplas queries, mescla e deduplica por score máximo.

        Suporta os mesmos modos de busca de search().
        """
        index = self._load(agent_id)
        seen: dict[str, SearchResult] = {}  # text -> melhor resultado
        embedding_cache: dict[str, list[float]] = {}

        for query in queries:
            results = await self._resolve_search_results(
                index, agent_id, query, top_k, search_mode, bm25_weight, embedding_cache
            )
            for result in results:
                existing = seen.get(result.text)
                if existing is None or result.score > existing.score:
                    seen[result.text] = result

        merged = sorted(seen.values(), key=lambda r: r.score, reverse=True)[:top_k]
        logger.info(
            "memory_search_multi",
            agent_id=agent_id,
            queries=len(queries),
            candidates=len(seen),
            returned=len(merged),
            mode=search_mode,
            bm25_weight=bm25_weight,
        )
        return merged

    async def get_memory_version(self, agent_id: str) -> str:
        path = self._index_path(agent_id)
        if not path.exists():
            return ""
        return hashlib.md5(path.read_bytes()).hexdigest()[:8]

    async def delete_memory(self, agent_id: str) -> None:
        path = self._index_path(agent_id)
        if path.exists():
            path.unlink()
            logger.info("memory_deleted", agent_id=agent_id)

    async def index_stats(self, agent_id: str) -> dict:
        """Estatísticas do índice para debug."""
        index = self._load(agent_id)
        docs_with_embeddings = sum(
            1 for d in index.docs if d.get("embedding")
        )
        path = self._index_path(agent_id)
        return {
            "total_chunks": index.total_docs,
            "vocabulary_size": len(index._df),
            "avg_chunk_tokens": round(index._avgdl, 1),
            "chunks_with_embeddings": docs_with_embeddings,
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
        }
