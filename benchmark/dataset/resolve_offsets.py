"""Resolve as consultas de example_data/query_definitions.py (ou de um arquivo
equivalente para o corpus real) em queries.json com offsets precisos.

Por quê este script precisa rodar com acesso ao backend: usa o MESMO
ParsingService (`app.application.services.parsing_service.ParsingService`) que
o backend usa em produção pra extrair o texto de cada documento, garantindo
que os offsets anotados aqui batam exatamente com o que o sistema realmente
processa — sem duplicar a lógica de parsing (mojibake, normalização etc) e sem
risco de desalinhamento entre a anotação e a extração real.

Uso (de dentro do container do backend, ou com backend/src no PYTHONPATH):

    python -m benchmark.dataset.resolve_offsets \\
        --corpus benchmark/example_data/corpus.json \\
        --definitions benchmark/example_data/query_definitions.py \\
        --out benchmark/example_data/queries.json \\
        --corpus-root benchmark/example_data

Ver instruções completas de execução no README do pacote benchmark/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_parsing_service():
    try:
        from app.application.services.parsing_service import ParsingService
    except ImportError as exc:
        raise SystemExit(
            "Não consegui importar o ParsingService do backend. Rode este script "
            "de dentro do container do backend (onde /app/src já está no path) "
            "ou adicione backend/src ao PYTHONPATH antes de chamar."
        ) from exc
    return ParsingService()


def _load_definitions(path: Path):
    spec = importlib.util.spec_from_file_location("query_definitions", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.RAW_QUERIES


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True, help="Caminho para corpus.json")
    ap.add_argument("--definitions", required=True, help="Caminho para query_definitions.py")
    ap.add_argument("--out", required=True, help="Caminho de saída para queries.json")
    ap.add_argument(
        "--corpus-root", required=True,
        help="Diretório base a partir do qual os `path` do corpus.json são resolvidos",
    )
    args = ap.parse_args()

    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    raw_queries = _load_definitions(Path(args.definitions))
    parser = _load_parsing_service()
    root = Path(args.corpus_root)

    extracted: dict[str, list[dict]] = {}
    for doc in corpus["documents"]:
        data = (root / doc["path"]).read_bytes()
        pages = parser.extract_text(data, doc["content_type"], doc["path"])
        extracted[doc["id"]] = pages
        total_chars = sum(len(p["text"]) for p in pages)
        print(f"{doc['id']}: {len(pages)} página(s), {total_chars} chars totais", file=sys.stderr)

    def find_passage(document_id: str, quote: str) -> dict:
        for page_dict in extracted[document_id]:
            idx = page_dict["text"].find(quote)
            if idx != -1:
                return {
                    "document_id": document_id,
                    "page": page_dict["page"],
                    "offset_start": idx,
                    "offset_end": idx + len(quote),
                    "relevance": 2,
                    "reference_quote": quote,
                }
        raise ValueError(f"trecho não encontrado em {document_id!r}: {quote!r}")

    queries = []
    for qid, text, category, domain, passages in raw_queries:
        resolved = [find_passage(doc_id, quote) for doc_id, quote in passages]
        queries.append({
            "id": qid,
            "text": text,
            "category": category,
            "domain": domain,
            "relevant_passages": resolved,
        })

    Path(args.out).write_text(
        json.dumps({"queries": queries}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{len(queries)} consultas resolvidas com sucesso -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
