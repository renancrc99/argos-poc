"""Métricas de qualidade da recuperação — especificação §5.

Todas as funções por-consulta operam sobre `hit_ranks`/`graded_hit_ranks`
(ver `dataset/chunk_resolver.py`): as posições (1-indexadas) dos resultados
retornados que cobrem algum trecho relevante anotado, e `total_relevant`: o
total de trechos relevantes anotados para a consulta (pode ser maior que o
número de hits, se nem todos foram recuperados no top-k).

Consultas "fora da base" (sem trechos relevantes anotados) não entram no
cálculo de Recall/Precision/MRR/nDCG/Hit Rate — elas alimentam só a taxa de
fallback (`fallback_metrics`), que é conceitualmente diferente (mede se o
agente reconheceu corretamente que não tinha a resposta, não se recuperou os
trechos certos).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def recall_at_k(hit_ranks: list[int], total_relevant: int, k: int) -> float:
    if total_relevant == 0:
        return 0.0
    hits_in_k = sum(1 for r in hit_ranks if r <= k)
    return hits_in_k / total_relevant


def precision_at_k(hit_ranks: list[int], k: int) -> float:
    if k == 0:
        return 0.0
    hits_in_k = sum(1 for r in hit_ranks if r <= k)
    return hits_in_k / k


def reciprocal_rank(hit_ranks: list[int]) -> float:
    """MRR é a média disto entre todas as consultas."""
    if not hit_ranks:
        return 0.0
    return 1.0 / min(hit_ranks)


def hit_rate_at_k(hit_ranks: list[int], k: int) -> float:
    return 1.0 if any(r <= k for r in hit_ranks) else 0.0


def ndcg_at_k(graded_ranks: dict[int, int], all_relevances: list[int], k: int) -> float:
    """
    graded_ranks: {posição: nível_de_relevância} dos resultados retornados que
    bateram em algum trecho anotado (ver chunk_resolver.graded_hit_ranks).
    all_relevances: níveis de relevância de TODOS os trechos anotados da
    consulta (usado só para montar o ranking ideal — IDCG).
    """
    dcg = sum(
        (2 ** rel - 1) / math.log2(rank + 1)
        for rank, rel in graded_ranks.items()
        if rank <= k
    )
    ideal = sorted(all_relevances, reverse=True)[:k]
    idcg = sum((2 ** rel - 1) / math.log2(i + 1) for i, rel in enumerate(ideal, start=1))
    return dcg / idcg if idcg > 0 else 0.0


@dataclass
class QueryRetrievalResult:
    """Entrada mínima que as funções de agregação abaixo precisam por consulta."""

    query_id: str
    category: str
    domain: str
    is_out_of_base: bool  # True se a consulta é "fora_da_base" (sem trechos relevantes)
    hit_ranks: list[int]
    graded_ranks: dict[int, int]
    total_relevant: int
    all_relevances: list[int]
    fallback_triggered: bool  # se a resposta do agente usou a mensagem de fallback


K_VALUES_RP = (1, 3, 5, 10)
K_VALUES_NDCG = (5, 10)
HIT_RATE_K = 5


def metrics_for_query(r: QueryRetrievalResult) -> dict[str, float]:
    """Métricas de recuperação para uma única consulta (não fora-da-base)."""
    out: dict[str, float] = {}
    for k in K_VALUES_RP:
        out[f"recall@{k}"] = recall_at_k(r.hit_ranks, r.total_relevant, k)
        out[f"precision@{k}"] = precision_at_k(r.hit_ranks, k)
    out["mrr"] = reciprocal_rank(r.hit_ranks)
    for k in K_VALUES_NDCG:
        out[f"ndcg@{k}"] = ndcg_at_k(r.graded_ranks, r.all_relevances, k)
    out[f"hit_rate@{HIT_RATE_K}"] = hit_rate_at_k(r.hit_ranks, HIT_RATE_K)
    return out


def aggregate_metrics(results: list[QueryRetrievalResult]) -> dict[str, float]:
    """Média das métricas de recuperação entre todas as consultas não-fora-da-base."""
    scored = [r for r in results if not r.is_out_of_base]
    if not scored:
        return {}
    per_query = [metrics_for_query(r) for r in scored]
    keys = per_query[0].keys()
    return {k: sum(m[k] for m in per_query) / len(per_query) for k in keys}


def fallback_metrics(results: list[QueryRetrievalResult]) -> dict[str, float]:
    """
    Taxa de fallback geral, e as duas quebras que a especificação pede (§5):
    - fallback_correto: entre as fora-da-base, quantas acionaram o fallback (queremos alto)
    - fallback_indevido: entre as com resposta no corpus, quantas acionaram o fallback por engano (queremos baixo)
    """
    out_of_base = [r for r in results if r.is_out_of_base]
    in_base = [r for r in results if not r.is_out_of_base]
    total = len(results)

    return {
        "fallback_rate": sum(1 for r in results if r.fallback_triggered) / total if total else 0.0,
        "fallback_correto": (
            sum(1 for r in out_of_base if r.fallback_triggered) / len(out_of_base)
            if out_of_base else 0.0
        ),
        "fallback_indevido": (
            sum(1 for r in in_base if r.fallback_triggered) / len(in_base)
            if in_base else 0.0
        ),
    }


def metrics_by_category(results: list[QueryRetrievalResult]) -> dict[str, dict[str, float]]:
    categories = sorted({r.category for r in results})
    return {cat: aggregate_metrics([r for r in results if r.category == cat]) for cat in categories}


def metrics_by_domain(results: list[QueryRetrievalResult]) -> dict[str, dict[str, float]]:
    domains = sorted({r.domain for r in results})
    return {dom: aggregate_metrics([r for r in results if r.domain == dom]) for dom in domains}
