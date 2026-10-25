"""Estatísticas de distribuição de tempo por etapa — percentis, média e desvio
padrão, calculados por configuração a partir de raw.jsonl.

Cada registro de raw.jsonl carrega um dict `timings` (ou None, se a interação
não rodou em modo benchmark). Nem toda etapa aparece em todo registro — por
exemplo, "t_search_vector" só existe quando o modo de busca realmente usou
embeddings (semantic/hybrid); ver memvid_memory_adapter.py::_resolve_search_results.
Por isso cada etapa "normal" é agregada só sobre os registros em que ela de
fato ocorreu (campo "n" no resultado reflete isso, e varia por etapa).

`busca_total` é a exceção deliberada: uma etapa sintética, calculada por
INTERAÇÃO (não por soma de médias já prontas) como
t_search_vector + t_search_lexical + t_fusion, tratando sub-etapa ausente
como 0 — assim ela fica comparável entre configs que usam sub-etapas
diferentes (ex.: config B, BM25 pura, só tem t_search_lexical; config A,
vetorial pura, só tem t_search_vector). Somar as médias individuais dessas 3
etapas depois de agregadas NÃO seria equivalente: percentil não é uma função
linear, p95(X) + p95(Y) != p95(X + Y) em geral.
"""

from __future__ import annotations

import math
import statistics

BUSCA_TOTAL_COMPONENTS = ("t_search_vector", "t_search_lexical", "t_fusion")
BUSCA_TOTAL_STAGE = "busca_total"
PERCENTILES = (50, 90, 95, 99)


def percentile(values: list[float], p: float) -> float:
    """Percentil p (0-100) por interpolação linear entre os postos mais
    próximos — mesmo método de numpy.percentile (default) e Excel
    PERCENTILE.INC. Com um único valor, retorna esse valor para qualquer p."""
    if not values:
        raise ValueError("lista vazia")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (p / 100) * (len(s) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def stage_stats(values: list[float]) -> dict[str, float]:
    """Média, desvio padrão amostral (Bessel, n-1) e percentis {50,90,95,99}
    de uma lista de tempos (segundos) de uma única etapa. n < 2 produz
    std=0.0 (desvio padrão amostral não é definido para 1 observação)."""
    out: dict[str, float] = {
        "n": len(values),
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) >= 2 else 0.0,
    }
    for p in PERCENTILES:
        out[f"p{p}"] = percentile(values, p)
    return out


def busca_total_for_record(timings: dict[str, float]) -> float:
    """Soma das 3 sub-etapas de busca de UMA interação, tratando sub-etapa
    ausente (porque o modo de busca configurado não a executa) como 0 — ver
    docstring do módulo."""
    return sum(timings.get(k, 0.0) for k in BUSCA_TOTAL_COMPONENTS)


def timing_stats_for_records(records: list[dict]) -> dict[str, dict[str, float]]:
    """Estatísticas por etapa (incluindo busca_total) para um conjunto de
    registros de raw.jsonl já filtrado (ex.: só de uma configuração). Etapas
    com n=0 nesse conjunto (nunca ocorreram) não aparecem no resultado."""
    with_timings = [r["timings"] for r in records if r.get("timings")]

    stage_names = sorted({name for t in with_timings for name in t})
    result: dict[str, dict[str, float]] = {}
    for stage_name in stage_names:
        values = [t[stage_name] for t in with_timings if stage_name in t]
        if values:
            result[stage_name] = stage_stats(values)

    busca_total_values = [busca_total_for_record(t) for t in with_timings]
    if busca_total_values:
        result[BUSCA_TOTAL_STAGE] = stage_stats(busca_total_values)

    return result
