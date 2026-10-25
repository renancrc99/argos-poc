"""Modelos do corpus, do conjunto de consultas e da verdade de referência.

Ponto crítico da especificação (seção 3.3): a verdade de referência é anotada
no nível do TRECHO DE ORIGEM (documento, página, offset_inicial, offset_final),
nunca por chunk_id — o chunk_id muda a cada estratégia de chunking. O
mapeamento trecho → chunk_id é resolvido em tempo de execução por
`chunk_resolver.py`, uma vez por estratégia de chunking testada.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Domain(str, Enum):
    ATENDIMENTO = "atendimento"       # FAQ / suporte ao cliente — trechos curtos e objetivos
    TECNICO = "tecnico"               # manual técnico — linguagem densa, procedimentos, códigos
    ACADEMICO = "academico"           # documento informativo/acadêmico — terminologia específica
    JURIDICO = "juridico"             # texto normativo — artigos, parágrafos, incisos, remissões


class CorpusDocument(BaseModel):
    """Um documento do corpus de benchmark.

    `id` é um identificador estável usado nas anotações de consulta — não é o
    `document_id` gerado pelo backend na ingestão (que só existe depois de
    ingerido, e muda a cada reingestão)."""

    id: str
    path: str  # caminho relativo a este arquivo de manifesto
    domain: Domain
    description: str
    content_type: str  # MIME type esperado pelo endpoint de upload


class Corpus(BaseModel):
    documents: list[CorpusDocument]

    def get(self, document_id: str) -> CorpusDocument:
        for doc in self.documents:
            if doc.id == document_id:
                return doc
        raise KeyError(f"documento não encontrado no corpus: {document_id}")


class QueryCategory(str, Enum):
    FACTUAL = "factual"                # resposta literal presente em um trecho
    PARAFRASE = "parafrase"            # vocabulário da pergunta diverge do documento
    TERMO_TECNICO = "termo_tecnico"    # código, nome próprio, correspondência exata
    MULTI_TRECHO = "multi_trecho"      # resposta exige dois ou mais trechos
    FORA_DA_BASE = "fora_da_base"      # resposta não existe no corpus — mede o fallback


class PassageAnnotation(BaseModel):
    """Verdade de referência para uma consulta: um trecho de origem relevante.

    `relevance` é graduada (0=irrelevante, 1=parcialmente relevante,
    2=totalmente relevante) para viabilizar nDCG — ver especificação seção 5."""

    document_id: str
    page: int | None = None  # None para documentos sem paginação nesta implementação (md/txt/docx)
    offset_start: int
    offset_end: int
    relevance: int = Field(default=2, ge=0, le=2)
    reference_quote: str = ""  # trecho literal usado só para conferência humana, não pelo cálculo


class Query(BaseModel):
    id: str
    text: str
    category: QueryCategory
    domain: Domain
    target_document: str | None = None  # roteamento no modo segmentado; None = infere do gabarito
    relevant_passages: list[PassageAnnotation] = Field(default_factory=list)


class QuerySet(BaseModel):
    queries: list[Query]

    def by_category(self, category: QueryCategory) -> list[Query]:
        return [q for q in self.queries if q.category == category]

    def by_domain(self, domain: Domain) -> list[Query]:
        return [q for q in self.queries if q.domain == domain]
