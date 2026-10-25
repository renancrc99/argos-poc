#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestra o experimento completo da monografia.

Roda as 4 configurações de ablação (A, B, C, F) nas duas condições de índice,
captura a especificação do ambiente e consolida tudo numa pasta por execução.

    python run_experimento.py --api http://localhost:8000

Pré-requisitos: backend no ar (docker compose up) e `pip install -e .` feito
dentro de benchmark/.
"""
from __future__ import annotations

import argparse, json, platform, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent          # benchmark/
DATASET = RAIZ.parent / "dataset"               # rag-platform-poc/dataset
CONFIGS = ["A", "B", "C", "F"]

CONDICOES = {
    "consolidado": DATASET / "queries-consolidado.json",
    "segmentado":  DATASET / "queries-segmentado.json",
}


def capturar_ambiente(api: str) -> dict:
    def cmd(*a):
        try:
            return subprocess.run(a, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            return ""
    amb = {
        "capturado_em": datetime.now(timezone.utc).isoformat(),
        "sistema": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "api": api,
        "docker_images": cmd("docker", "compose", "images"),
        "ollama_ps": cmd("ollama", "ps"),
        "ollama_list": cmd("ollama", "list"),
    }
    # checagem de GPU — pendência 93: confirmar que o Ollama não caiu para CPU
    ps = amb["ollama_ps"]
    if ps:
        amb["gpu_em_uso"] = "GPU" in ps.upper() or "%" in ps
        amb["ALERTA_GPU"] = None if amb["gpu_em_uso"] else (
            "ollama ps não indica uso de GPU. Se o modelo estiver em CPU, os tempos "
            "medidos não representam o protótipo como projetado — verifique antes de "
            "usar qualquer número de latência na monografia."
        )
    return amb


def rodar(api: str, condicao: str, queries: Path, out_dir: Path, chunking: str) -> int:
    print(f"\n{'='*70}\n  CONDIÇÃO: {condicao}  |  configs: {' '.join(CONFIGS)}\n{'='*70}", flush=True)
    cmd = [sys.executable, "-m", "benchmark.cli", "run",
           "--corpus", str(DATASET / "corpus.json"),
           "--queries", str(queries),
           "--corpus-root", str(DATASET),
           "--api", api,
           "--chunking", chunking,
           "--configs", *CONFIGS,
           "--out-dir", str(out_dir),
           "--tag", condicao]
    # modo de índice: só existe depois de aplicado o patch do runner
    cmd += ["--index-mode", condicao]
    print("  $ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(RAIZ.parent))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--chunking", default="medio",
                    choices=["automatico", "pequeno", "medio", "grande"])
    ap.add_argument("--condicoes", nargs="*", default=list(CONDICOES),
                    choices=list(CONDICOES))
    ap.add_argument("--out-root", default=str(RAIZ / "runs"))
    args = ap.parse_args()

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = Path(args.out_root) / f"monografia_{carimbo}"
    base.mkdir(parents=True, exist_ok=True)

    amb = capturar_ambiente(args.api)
    (base / "ambiente.json").write_text(json.dumps(amb, ensure_ascii=False, indent=2), encoding="utf-8")
    if amb.get("ALERTA_GPU"):
        print("\n*** " + amb["ALERTA_GPU"] + "\n", flush=True)

    # cópia do dataset usado, para o run ser autocontido e reproduzível
    destino = base / "dataset"
    destino.mkdir(exist_ok=True)
    for nome in ["corpus.json", "queries-consolidado.json", "queries-segmentado.json"]:
        if (DATASET / nome).exists():
            shutil.copy2(DATASET / nome, destino / nome)

    t0 = time.time()
    status = {}
    for cond in args.condicoes:
        out = base / cond
        rc = rodar(args.api, cond, CONDICOES[cond], out, args.chunking)
        status[cond] = "ok" if rc == 0 else f"falhou (rc={rc})"
        if rc != 0:
            print(f"\n!!! condição '{cond}' terminou com erro — seguindo para a próxima", flush=True)

    resumo = {
        "execucao": carimbo,
        "duracao_s": round(time.time() - t0, 1),
        "chunking": args.chunking,
        "configs": CONFIGS,
        "condicoes": status,
        "saida": str(base),
    }
    (base / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*70}")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    print(f"{'='*70}\nArtefatos em: {base}")


if __name__ == "__main__":
    main()
