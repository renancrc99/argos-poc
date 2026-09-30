"""DTOs para operações de Document."""

from pydantic import BaseModel

from app.domain.entities.document import Document


class IngestDocumentInput(BaseModel):
    agent_id: str
    filename: str
    content_type: str
    file_data: bytes
    # None = detecta automaticamente com base no tamanho do documento
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    benchmark_mode: bool = False


class IngestResult(BaseModel):
    agent_id: str
    document_id: str
    filename: str
    chunks_created: int
    status: str          # "processed" | "skipped"
    file_hash: str
    config_hash: str
    timings: dict[str, float] | None = None


class ChunkStats(BaseModel):
    count: int
    min_chars: int
    max_chars: int
    avg_chars: float
    total_chars: int


class DocumentRecord(BaseModel):
    id: str
    agent_id: str
    filename: str
    content_type: str
    size_bytes: int
    s3_key: str
    status: str
    chunk_size: int
    chunk_overlap: int
    chunk_count: int
    chunk_stats: ChunkStats
    ingested_at: str
    file_hash: str
    config_hash: str


def document_to_record(document: Document) -> DocumentRecord:
    """Mapeia a entidade Document para o DTO de saída da API. Fonte única desse mapeamento."""
    return DocumentRecord(
        id=document.id,
        agent_id=document.agent_id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        s3_key=document.s3_key,
        status=document.status,
        chunk_size=document.chunk_size,
        chunk_overlap=document.chunk_overlap,
        chunk_count=document.chunk_count,
        chunk_stats=ChunkStats(
            count=document.chunk_count,
            min_chars=document.chunk_min_chars,
            max_chars=document.chunk_max_chars,
            avg_chars=document.chunk_avg_chars,
            total_chars=document.chunk_total_chars,
        ),
        ingested_at=document.created_at.isoformat(),
        file_hash=document.file_hash,
        config_hash=document.config_hash,
    )
