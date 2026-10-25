"""Lê raw.jsonl e calcula as métricas agregadas por configuração — especificação
§9.1 (aggregate.csv) e Quadro 8 (recuperação por configuração)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from metrics.retrieval import (
    QueryRetrievalResult,
    aggregate_metrics,
    fallback_metrics,
    metrics_by_category,
    metrics_by_domain,
)
from metrics.timing_stats import busca_total_for_record, timing_stats_for_records


def load_raw_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def record_to_retrieval_result(r: dict) -> QueryRetrievalResult:
    return QueryRetrievalResult(
        query_id=r["query_id"],
        category=r["category"],
        domain=r["domain"],
        is_out_of_base=r["is_out_of_base"],
        hit_ranks=r["hit_ranks"],
        graded_ranks={int(k): v for k, v in r["graded_ranks"].items()},
        total_relevant=r["total_relevant"],
        all_relevances=r["all_relevances"],
        fallback_triggered=r["fallback_triggered"],
    )


def _avg_timing(records: list[dict], field: str) -> float | None:
    values = [r["timings"][field] for r in records if r.get("timings") and field in r["timings"]]
    return sum(values) / len(values) if values else None


def _avg_busca_total(records: list[dict]) -> float | None:
    """Média de busca_total (t_search_vector + t_search_lexical + t_fusion,
    somados por interação — ver metrics/timing_stats.py)."""
    values = [busca_total_for_record(r["timings"]) for r in records if r.get("timings")]
    return sum(values) / len(values) if values else None


def aggregate_by_config(records: list[dict]) -> dict[str, dict]:
    configs = sorted({r["config"] for r in records})
    out = {}
    for config in configs:
        config_records = [r for r in records if r["config"] == config]
        results = [record_to_retrieval_result(r) for r in config_records]
        n = len(config_records)
        out[config] = {
            "n_queries": n,
            "retrieval": aggregate_metrics(results),
            "retrieval_by_category": metrics_by_category(results),
            "retrieval_by_domain": metrics_by_domain(results),
            "fallback": fallback_metrics(results),
            "avg_input_tokens": sum(r["input_tokens"] for r in config_records) / n,
            "avg_output_tokens": sum(r["output_tokens"] for r in config_records) / n,
            "avg_llm_calls": sum(r["llm_calls"] for r in config_records) / n,
            "avg_t_total": _avg_timing(config_records, "t_total"),
            "avg_t_search_lexical": _avg_timing(config_records, "t_search_lexical"),
            "avg_t_search_vector": _avg_timing(config_records, "t_search_vector"),
            "avg_t_fusion": _avg_timing(config_records, "t_fusion"),
            "avg_busca_total": _avg_busca_total(config_records),
            "avg_t_llm_ttft": _avg_timing(config_records, "t_llm_ttft"),
            "avg_t_llm_total": _avg_timing(config_records, "t_llm_total"),
        }
    return out


def timing_stats_by_config(records: list[dict]) -> dict[str, dict[str, dict[str, float]]]:
    """Estatísticas de distribuição (n, média, desvio padrão, p50/p90/p95/p99)
    por etapa de tempo, por configuração — inclui a etapa sintética
    busca_total (ver metrics/timing_stats.py)."""
    configs = sorted({r["config"] for r in records})
    return {
        config: timing_stats_for_records([r for r in records if r["config"] == config])
        for config in configs
    }


def write_aggregate_csv(by_config: dict[str, dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    any_retrieval = next((d["retrieval"] for d in by_config.values() if d["retrieval"]), {})
    metric_keys = sorted(any_retrieval.keys())

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "config", "n_queries", *metric_keys,
            "fallback_rate", "fallback_correto", "fallback_indevido",
            "avg_input_tokens", "avg_output_tokens", "avg_llm_calls",
            "avg_t_total", "avg_t_search_lexical", "avg_t_search_vector",
            "avg_t_fusion", "avg_busca_total", "avg_t_llm_ttft", "avg_t_llm_total",
        ])
        for config, data in sorted(by_config.items()):
            row = [config, data["n_queries"]]
            row += [round(data["retrieval"].get(k, 0.0), 4) for k in metric_keys]
            fb = data["fallback"]
            row += [round(fb["fallback_rate"], 4), round(fb["fallback_correto"], 4), round(fb["fallback_indevido"], 4)]
            row += [round(data["avg_input_tokens"], 1), round(data["avg_output_tokens"], 1), round(data["avg_llm_calls"], 2)]
            for key in ("avg_t_total", "avg_t_search_lexical", "avg_t_search_vector", "avg_t_fusion", "avg_busca_total", "avg_t_llm_ttft", "avg_t_llm_total"):
                val = data[key]
                row.append(round(val, 4) if val is not None else "")
            writer.writerow(row)


def write_timing_stats_csv(by_config_stats: dict[str, dict[str, dict[str, float]]], out_path: Path) -> None:
    """Formato longo (config, etapa) por linha — mais legível que achatar em
    colunas quando há várias etapas × 6 estatísticas cada."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "config", "etapa", "n",
            "media_s", "desvio_padrao_s", "p50_s", "p90_s", "p95_s", "p99_s",
        ])
        for config in sorted(by_config_stats):
            for stage_name in sorted(by_config_stats[config]):
                s = by_config_stats[config][stage_name]
                writer.writerow([
                    config, stage_name, s["n"],
                    round(s["mean"], 4), round(s["std"], 4),
                    round(s["p50"], 4), round(s["p90"], 4),
                    round(s["p95"], 4), round(s["p99"], 4),
                ])
