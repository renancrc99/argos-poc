"""Monta o report.md final a partir de aggregate.csv/raw.jsonl — especificação
§9.1/§9.2. Não tenta reproduzir os Quadros 6-16 inteiros (vários dependem de
custo/AWS/RAGAS, ainda não implementados) — monta o que já está disponível
(Quadro 8-equivalente de recuperação por configuração) e deixa placeholders
claros para o resto, para o relatório crescer incrementalmente conforme os
outros módulos (cost/, metrics/response_quality.py) forem rodados sobre a
mesma pasta de execução.
"""

from __future__ import annotations

import csv
from pathlib import Path

DIVERGENCIAS_PATH = Path(__file__).resolve().parents[3] / "divergencias-especificacao-vs-implementacao.md"


def render_report(out_dir: Path, aggregate_csv: Path, environment: dict | None = None) -> str:
    lines: list[str] = []
    lines.append(f"# Relatório de benchmark — {out_dir.name}\n")
    lines.append(
        "Gerado por `rag-platform-poc/benchmark/`. Ver `raw.jsonl` (um registro por "
        "interação) e `aggregate.csv` (métricas agregadas por configuração) nesta mesma pasta.\n"
    )

    if environment:
        lines.append("## Ambiente\n")
        for k, v in environment.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    lines.append("## Quadro — Qualidade da recuperação por configuração\n")
    if aggregate_csv.exists():
        with open(aggregate_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            headers = list(rows[0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "---|" * len(headers))
            for row in rows:
                lines.append("| " + " | ".join(row[h] for h in headers) + " |")
    else:
        lines.append("*(aggregate.csv não encontrado — rode `python -m benchmark.cli run` primeiro)*")
    lines.append("")

    lines.append("## Quadro — Estatística de tempo por etapa (percentis)\n")
    timing_stats_csv = out_dir / "timing_stats.csv"
    if timing_stats_csv.exists():
        with open(timing_stats_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            headers = list(rows[0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "---|" * len(headers))
            for row in rows:
                lines.append("| " + " | ".join(row[h] for h in headers) + " |")
        lines.append(
            "\n`busca_total` é uma etapa sintética (t_search_vector + t_search_lexical + "
            "t_fusion), somada por interação antes de calcular média/percentis — não é a "
            "soma das médias individuais dessas 3 etapas, já que percentil não é uma função "
            "linear. Etapas com n=0 numa configuração (ex.: t_search_vector em configs "
            "BM25-puras) não aparecem nessa tabela."
        )
    else:
        lines.append("*(timing_stats.csv não encontrado — rode `python -m benchmark.cli run` primeiro)*")
    lines.append("")

    lines.append("## Divergências entre a especificação e a implementação\n")
    if DIVERGENCIAS_PATH.exists():
        lines.append(
            f"Ver documento completo: `{DIVERGENCIAS_PATH.name}` (na raiz do projeto, "
            "fora deste pacote — cobre arquitetura de armazenamento/busca, fusão, "
            "reranking, chunking e a avaliação técnica do Memvid real)."
        )
    else:
        lines.append("*(documento de divergências não encontrado)*")
    lines.append("")

    lines.append("## Limitações\n")
    lines.append(
        "1. Resultados de latência e vazão são de máquina única com LLM local; não se "
        "generalizam para Bedrock nem para ECS Fargate.\n"
        "2. Qwen 2.5:14b tem capacidade inferior aos modelos previstos em produção; a "
        "qualidade das respostas tende a ser subestimada.\n"
        "3. A simulação de S3 via LocalStack não reproduz latência nem vazão do serviço "
        "gerenciado (e, nesta implementação, o índice de memória sequer usa S3 — fica "
        "num volume Docker local; ver documento de divergências).\n"
        "4. O custo na AWS é estimado a partir de preços públicos, não medido em operação real.\n"
        "5. Não houve validação com usuários reais.\n"
        "6. O corpus é de escala limitada e não representa a diversidade documental de "
        "clientes reais — se esta execução usou o corpus de exemplo (`example_data/`), "
        "ela NÃO satisfaz os requisitos mínimos de corpus/consultas da especificação "
        "(seção 3) e serve só para validar que a ferramenta funciona ponta a ponta.\n"
        "7. GPU AMD (não NVIDIA) — amostragem de VRAM é best-effort; convém confirmar se "
        "o Ollama está de fato usando a GPU ou caindo para CPU nesta máquina."
    )

    return "\n".join(lines)


def write_report(out_dir: Path, environment: dict | None = None) -> Path:
    report_path = out_dir / "report.md"
    content = render_report(out_dir, out_dir / "aggregate.csv", environment)
    report_path.write_text(content, encoding="utf-8")
    return report_path
