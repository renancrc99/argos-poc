"""Executa o estudo de ablação: cria um agente por configuração (A-F), ingere o
corpus, roda todas as consultas contra cada agente em modo benchmark, e grava
um registro por interação em raw.jsonl — especificação §4.1, §7.1, §9.1.

Desenho importante: usamos SÓ o endpoint /chat (com X-Benchmark: true) como
fonte única de dados de recuperação e de resposta, configurando
max_context_chunks=10 em todos os agentes de ablação. Isso garante que as
métricas de recuperação (Recall@10 incluso) refletem exatamente o que o
pipeline de produção retornou — incluindo o efeito real do reranking nas
configs E/F — em vez de uma chamada separada a /debug/search com parâmetros
que podem não bater com o que o agente realmente faria (o debug/multiquery,
por exemplo, não permite escolher search_mode, então não serviria pra testar
D/F em modo híbrido).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/ no path

from ablation.configs import (
    ABLATION_CONFIGS,
    CHUNKING_PROFILES,
    DEFAULT_AGENT_DEFAULTS,
    DEFAULT_FALLBACK_MESSAGE,
)
from dataset.chunk_resolver import RetrievedChunk, graded_hit_ranks, hit_ranks
from dataset.schema import Corpus, QuerySet


MAX_CONTEXT_CHUNKS_FOR_ABLATION = 10  # cobre Recall@10 sem precisar de endpoint separado


def _filename_by_document_id(corpus: Corpus) -> dict[str, str]:
    return {doc.id: Path(doc.path).name for doc in corpus.documents}


class AblationRunner:
    def __init__(self, api_base: str, corpus_root: Path, timeout: float = 180.0):
        self._api_base = api_base.rstrip("/")
        self._corpus_root = corpus_root
        self._client = httpx.Client(base_url=self._api_base, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _create_agent(self, config_letter: str, name_suffix: str) -> str:
        config = ABLATION_CONFIGS[config_letter]
        payload = {
            **DEFAULT_AGENT_DEFAULTS,
            **config.agent_payload_overrides(),
            "name": f"[benchmark] {config.letter} — {config.label} {name_suffix}",
            "description": f"Agente de ablação, configuração {config.letter}",
            "max_context_chunks": MAX_CONTEXT_CHUNKS_FOR_ABLATION,
        }
        resp = self._client.post("/agents", json=payload)
        resp.raise_for_status()
        return resp.json()["id"]

    def _delete_agent(self, agent_id: str) -> None:
        self._client.delete(f"/agents/{agent_id}")

    def _ingest_corpus(self, agent_id: str, corpus: Corpus, chunking_profile: str) -> None:
        profile = CHUNKING_PROFILES[chunking_profile]
        for doc in corpus.documents:
            path = self._corpus_root / doc.path
            with open(path, "rb") as f:
                files = {"file": (path.name, f, doc.content_type)}
                data = {}
                if profile.chunk_size is not None:
                    data["chunk_size"] = str(profile.chunk_size)
                    data["chunk_overlap"] = str(profile.chunk_overlap)
                resp = self._client.post(
                    f"/agents/{agent_id}/documents", files=files, data=data,
                    headers={"X-Benchmark": "true"},
                )
                resp.raise_for_status()

    def _chat(self, agent_id: str, message: str) -> dict:
        resp = self._client.post(
            f"/agents/{agent_id}/chat",
            json={"message": message},
            headers={"X-Benchmark": "true"},
        )
        resp.raise_for_status()
        return resp.json()

    def run(
        self,
        corpus: Corpus,
        query_set: QuerySet,
        configs: list[str],
        chunking_profile: str,
        out_path: Path,
        run_tag: str = "",
        index_mode: str = "consolidado",
    ) -> None:
        """index_mode="consolidado": um agente por configuração, com o corpus inteiro.
        index_mode="segmentado": um agente por documento, por configuração; cada
        consulta vai ao agente do seu `target_document`."""
        filename_by_doc_id = _filename_by_document_id(corpus)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if index_mode == "segmentado":
            buckets = {doc.id: Corpus(documents=[doc]) for doc in corpus.documents}
        else:
            buckets = {"_todos": corpus}

        with open(out_path, "a", encoding="utf-8") as out_file:
            for config_letter in configs:
                print(f"\n=== Configuração {config_letter} ({index_mode}) ===", file=sys.stderr)
                agentes: dict[str, str] = {}
                try:
                    for bucket_id, bucket_corpus in buckets.items():
                        sufixo = f"{run_tag} {bucket_id}".strip()
                        agente = self._create_agent(config_letter, sufixo)
                        agentes[bucket_id] = agente
                        self._ingest_corpus(agente, bucket_corpus, chunking_profile)
                        print(f"  agente {bucket_id}: {agente} — corpus ingerido", file=sys.stderr)

                    for query in query_set.queries:
                        bucket = self._bucket_da_consulta(query, buckets)
                        if bucket is None:
                            print(f"  {query.id}: sem agente de destino, pulada", file=sys.stderr)
                            continue
                        result = self._chat(agentes[bucket], query.text)
                        record = self._build_record(
                            config_letter, chunking_profile, query, result,
                            filename_by_doc_id, DEFAULT_FALLBACK_MESSAGE,
                        )
                        record["index_mode"] = index_mode
                        record["agent_bucket"] = bucket
                        out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        out_file.flush()
                        print(f"  {query.id} [{query.category}] -> {bucket} ok", file=sys.stderr)
                finally:
                    for agente in agentes.values():
                        self._delete_agent(agente)

    @staticmethod
    def _bucket_da_consulta(query, buckets: dict) -> str | None:
        """Consolidado: sempre o agente único. Segmentado: o `target_document` da
        consulta; sem ele, o documento do primeiro trecho de referência."""
        if "_todos" in buckets:
            return "_todos"
        alvo = getattr(query, "target_document", None)
        if alvo is None and query.relevant_passages:
            alvo = query.relevant_passages[0].document_id
        return alvo if alvo in buckets else None

    @staticmethod
    def _build_record(
        config_letter: str,
        chunking_profile: str,
        query,
        chat_result: dict,
        filename_by_doc_id: dict[str, str],
        fallback_message: str,
    ) -> dict:
        retrieved = [
            RetrievedChunk(
                source=s["source"],
                text=s.get("text") or s.get("snippet", ""),
                score=s["score"],
                page=s.get("page"),
            )
            for s in chat_result.get("sources", [])
        ]
        # `text` (texto completo do chunk) só vem preenchido em modo benchmark
        # (ver chat_with_agent.py) — cai pro snippet truncado como fallback caso
        # o registro tenha vindo de uma chamada fora do modo benchmark.
        ranks = hit_ranks(query.relevant_passages, retrieved, filename_by_doc_id)
        graded = graded_hit_ranks(query.relevant_passages, retrieved, filename_by_doc_id)

        response_text = chat_result.get("response", "")
        fallback_triggered = fallback_message[:30].lower() in response_text.lower()

        return {
            "config": config_letter,
            "chunking_profile": chunking_profile,
            "query_id": query.id,
            "category": query.category.value if hasattr(query.category, "value") else query.category,
            "domain": query.domain.value if hasattr(query.domain, "value") else query.domain,
            "is_out_of_base": len(query.relevant_passages) == 0,
            "response": response_text,
            "sources": chat_result.get("sources", []),
            "input_tokens": chat_result.get("input_tokens", 0),
            "output_tokens": chat_result.get("output_tokens", 0),
            "llm_calls": chat_result.get("llm_calls", 1),
            "timings": chat_result.get("timings"),
            "fallback_triggered": fallback_triggered,
            "hit_ranks": ranks,
            "graded_ranks": {str(k): v for k, v in graded.items()},
            "total_relevant": len(query.relevant_passages),
            "all_relevances": [p.relevance for p in query.relevant_passages],
        }
