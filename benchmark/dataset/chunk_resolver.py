"""Resolve, para uma consulta e um conjunto de resultados de busca já obtidos
da API, quais resultados retornados realmente cobrem algum trecho anotado como
relevante — critério da especificação §3.3: sobreposição ≥ 50% do trecho
anotado conta como "o chunk cobre a anotação".

Importante: não recalculamos texto de documento nem reimportamos o
ParsingService do backend aqui. Cada `PassageAnnotation` já carrega
`reference_quote` — o texto literal exato que foi localizado no momento da
anotação (ver `resolve_offsets.py`) — e é esse texto que usamos como proxy do
trecho anotado. Isso mantém o pacote benchmark/ 100% desacoplado dos internals
do backend em tempo de execução; só o script de preparo do dataset precisa
importar o backend, uma única vez, offline.

Não há chunk_id estável exposto pela API de busca hoje (SearchResult não
carrega um índice) — por isso tratamos (source, texto do chunk) como a
identidade prática de um chunk dentro de uma execução de benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from dataset.schema import PassageAnnotation


@dataclass(frozen=True)
class RetrievedChunk:
    """Um resultado de busca devolvido pela API, na forma mínima que o resolver precisa."""

    source: str
    text: str
    score: float
    page: int | None = None


def _overlap_ratio(reference_quote: str, chunk_text: str) -> float:
    """Fração do `reference_quote` coberta pelo `chunk_text`. 1.0 se o trecho
    anotado aparece inteiro no chunk; caso contrário, usa a maior substring
    comum como aproximação — tolera truncamento quando o trecho anotado cai
    perto de um limite de chunk."""
    if not reference_quote:
        return 0.0
    if reference_quote in chunk_text:
        return 1.0
    matcher = SequenceMatcher(None, reference_quote, chunk_text)
    match = matcher.find_longest_match(0, len(reference_quote), 0, len(chunk_text))
    return match.size / len(reference_quote)


def is_hit(
    passage: PassageAnnotation,
    chunk: RetrievedChunk,
    filename_by_document_id: dict[str, str],
    min_overlap: float = 0.5,
) -> bool:
    """True se `chunk` cobre `passage` (mesma fonte + sobreposição ≥ min_overlap)."""
    expected_filename = filename_by_document_id.get(passage.document_id)
    if expected_filename is None or chunk.source != expected_filename:
        return False
    return _overlap_ratio(passage.reference_quote, chunk.text) >= min_overlap


def hit_ranks(
    passages: list[PassageAnnotation],
    retrieved: list[RetrievedChunk],
    filename_by_document_id: dict[str, str],
    min_overlap: float = 0.5,
) -> list[int]:
    """
    Para uma consulta, retorna as posições (1-indexadas, na ordem de `retrieved`)
    dos resultados que cobrem QUALQUER trecho relevante anotado. Lista vazia
    significa que nenhum resultado retornado cobriu um trecho relevante — usado
    por Recall@k/Precision@k/MRR/Hit Rate (métricas binárias, sem relevância
    graduada — ver `graded_hit_ranks` para nDCG).
    """
    ranks = []
    for i, chunk in enumerate(retrieved, start=1):
        if any(is_hit(p, chunk, filename_by_document_id, min_overlap) for p in passages):
            ranks.append(i)
    return ranks


def graded_hit_ranks(
    passages: list[PassageAnnotation],
    retrieved: list[RetrievedChunk],
    filename_by_document_id: dict[str, str],
    min_overlap: float = 0.5,
) -> dict[int, int]:
    """
    Como `hit_ranks`, mas retorna {posição: nível_de_relevância} — usado só por
    nDCG@k (especificação §5), que precisa da relevância graduada (0/1/2), não
    só de um hit binário. Quando mais de um trecho anotado bate no mesmo
    resultado, usa o maior nível de relevância entre eles.
    """
    result: dict[int, int] = {}
    for i, chunk in enumerate(retrieved, start=1):
        matched = [
            p.relevance for p in passages
            if is_hit(p, chunk, filename_by_document_id, min_overlap)
        ]
        if matched:
            result[i] = max(matched)
    return result
