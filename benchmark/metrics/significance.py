"""Teste de significância para as comparações do estudo de ablação — especificação §5:
teste de permutação pareado (ou Wilcoxon pareado) por consulta, com correção de
Bonferroni para comparações múltiplas. Sem isso, diferenças de 1-2 pontos
percentuais entre configurações não sustentam conclusão nenhuma.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy import stats

# As comparações que a especificação pede (§5, cruzando com a tabela de configs §4.1):
# C×A isola o ganho da fusão híbrida sobre busca vetorial pura
# C×B isola o ganho da fusão híbrida sobre busca léxica pura
# D×C isola o ganho da expansão de consultas (multiquery)
# E×C isola o ganho do reranking
# F×C dá o ganho acumulado da configuração completa
PLANNED_COMPARISONS = [("C", "A"), ("C", "B"), ("D", "C"), ("E", "C"), ("F", "C")]


@dataclass
class SignificanceResult:
    metric: str
    config_a: str
    config_b: str
    mean_a: float
    mean_b: float
    diff: float
    p_value: float
    p_value_bonferroni: float
    significant_at_005: bool
    method: str


def paired_test(
    values_a: list[float],
    values_b: list[float],
    metric: str,
    config_a: str,
    config_b: str,
    n_comparisons: int,
    method: str = "wilcoxon",
) -> SignificanceResult:
    """
    Compara os valores de uma métrica (ex: recall@5) por consulta entre duas
    configurações, pareados pela mesma consulta nas duas listas (mesma ordem).

    method="wilcoxon" usa o teste de postos com sinal de Wilcoxon (rápido,
    padrão para dados pareados não-normais). method="permutation" usa teste de
    permutação pareado (mais lento, sem pressuposto de distribuição — preferível
    com poucas consultas, onde o Wilcoxon perde poder).
    """
    if len(values_a) != len(values_b):
        raise ValueError("values_a e values_b precisam ter o mesmo tamanho (consultas pareadas)")

    diffs = [a - b for a, b in zip(values_a, values_b)]
    if all(d == 0 for d in diffs):
        p_value = 1.0
    elif method == "wilcoxon":
        _, p_value = stats.wilcoxon(values_a, values_b, zero_method="wilcox")
    elif method == "permutation":
        def statistic(x, y):
            return sum(x) / len(x) - sum(y) / len(y)

        result = stats.permutation_test(
            (values_a, values_b),
            statistic,
            permutation_type="samples",
            n_resamples=9999,
        )
        p_value = float(result.pvalue)
    else:
        raise ValueError(f"método desconhecido: {method!r}")

    p_bonferroni = min(p_value * n_comparisons, 1.0)
    mean_a = sum(values_a) / len(values_a)
    mean_b = sum(values_b) / len(values_b)

    return SignificanceResult(
        metric=metric,
        config_a=config_a,
        config_b=config_b,
        mean_a=mean_a,
        mean_b=mean_b,
        diff=mean_a - mean_b,
        p_value=p_value,
        p_value_bonferroni=p_bonferroni,
        significant_at_005=p_bonferroni < 0.05,
        method=method,
    )


def run_planned_comparisons(
    per_query_metric_by_config: dict[str, dict[str, float]],
    metric: str,
    comparisons: list[tuple[str, str]] = PLANNED_COMPARISONS,
    method: str = "wilcoxon",
) -> list[SignificanceResult]:
    """
    per_query_metric_by_config: {config_letra: {query_id: valor_da_métrica}} —
    mesmo conjunto de query_ids em todas as configs (o runner de ablação garante
    isso rodando as mesmas consultas em todas as configurações).
    """
    results = []
    for config_a, config_b in comparisons:
        metrics_a = per_query_metric_by_config[config_a]
        metrics_b = per_query_metric_by_config[config_b]
        query_ids = sorted(set(metrics_a) & set(metrics_b))
        values_a = [metrics_a[q] for q in query_ids]
        values_b = [metrics_b[q] for q in query_ids]
        results.append(
            paired_test(
                values_a, values_b, metric, config_a, config_b,
                n_comparisons=len(comparisons), method=method,
            )
        )
    return results
