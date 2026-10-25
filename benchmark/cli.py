"""Ponto de entrada único da ferramenta de benchmark — especificação §9.1:
"Tudo reproduzível por um único comando."

Uso:
    python -m benchmark.cli run --corpus example_data/corpus.json \\
        --queries example_data/queries.json --corpus-root example_data \\
        --api http://localhost:8000 --chunking medio \\
        --configs A B C D E F --out-dir runs/<timestamp>

Sem --configs, roda as 6 configurações completas do estudo de ablação (§4.1).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ablation.configs import ABLATION_CONFIGS
from ablation.runner import AblationRunner
from dataset.schema import Corpus, QuerySet
from report.aggregate import (
    aggregate_by_config,
    load_raw_jsonl,
    timing_stats_by_config,
    write_aggregate_csv,
    write_timing_stats_csv,
)
from report.render import write_report


def cmd_run(args: argparse.Namespace) -> None:
    corpus = Corpus.model_validate(json.loads(Path(args.corpus).read_text(encoding="utf-8")))
    query_set = QuerySet.model_validate(json.loads(Path(args.queries).read_text(encoding="utf-8")))
    configs = args.configs or list(ABLATION_CONFIGS.keys())

    out_dir = Path(args.out_dir) if args.out_dir else Path("runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.jsonl"

    print(f"Rodando configs {configs} sobre {len(query_set.queries)} consultas, "
          f"perfil de chunking '{args.chunking}'", file=sys.stderr)
    print(f"Saída: {out_dir}", file=sys.stderr)

    runner = AblationRunner(api_base=args.api, corpus_root=Path(args.corpus_root))
    try:
        runner.run(
            corpus=corpus, query_set=query_set, configs=configs,
            chunking_profile=args.chunking, out_path=raw_path, run_tag=args.tag,
            index_mode=args.index_mode,
        )
    finally:
        runner.close()

    _aggregate(raw_path, out_dir)


def cmd_aggregate(args: argparse.Namespace) -> None:
    _aggregate(Path(args.raw), Path(args.out_dir))


def _aggregate(raw_path: Path, out_dir: Path) -> None:
    records = load_raw_jsonl(raw_path)
    by_config = aggregate_by_config(records)
    write_aggregate_csv(by_config, out_dir / "aggregate.csv")

    timing_stats = timing_stats_by_config(records)
    write_timing_stats_csv(timing_stats, out_dir / "timing_stats.csv")

    print("\n=== Resumo (Recall@5 e MRR por configuração) ===", file=sys.stderr)
    for config in sorted(by_config):
        r = by_config[config]["retrieval"]
        fb = by_config[config]["fallback"]
        label = ABLATION_CONFIGS[config].label if config in ABLATION_CONFIGS else config
        print(
            f"  {config} ({label}): recall@5={r.get('recall@5', 0):.3f} "
            f"mrr={r.get('mrr', 0):.3f} fallback_correto={fb['fallback_correto']:.3f} "
            f"fallback_indevido={fb['fallback_indevido']:.3f} "
            f"t_total_médio={by_config[config]['avg_t_total']}",
            file=sys.stderr,
        )
    print(f"\naggregate.csv escrito em {out_dir / 'aggregate.csv'}", file=sys.stderr)
    print(f"timing_stats.csv escrito em {out_dir / 'timing_stats.csv'}", file=sys.stderr)
    report_path = write_report(out_dir)
    print(f"report.md escrito em {report_path}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Roda o estudo de ablação completo e agrega os resultados")
    run_p.add_argument("--corpus", required=True)
    run_p.add_argument("--queries", required=True)
    run_p.add_argument("--corpus-root", required=True)
    run_p.add_argument("--api", default="http://localhost:8000")
    run_p.add_argument("--chunking", default="medio", choices=["automatico", "pequeno", "medio", "grande"])
    run_p.add_argument("--configs", nargs="*", choices=list(ABLATION_CONFIGS.keys()))
    run_p.add_argument("--out-dir")
    run_p.add_argument("--index-mode", default="consolidado",
                       choices=["consolidado", "segmentado"],
                       help="consolidado: um agente com todos os documentos. "
                            "segmentado: um agente por documento.")
    run_p.add_argument("--tag", default="")
    run_p.set_defaults(func=cmd_run)

    agg_p = sub.add_parser("aggregate", help="Recalcula aggregate.csv a partir de um raw.jsonl existente")
    agg_p.add_argument("--raw", required=True)
    agg_p.add_argument("--out-dir", required=True)
    agg_p.set_defaults(func=cmd_aggregate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
