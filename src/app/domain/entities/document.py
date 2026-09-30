"""Entidade Document — representa um documento ingerido por um agente."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Document(BaseModel):
    agent_id: str
    filename: str
    content_type: str
    size_bytes: int
    s3_key: str
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["uploaded", "processed", "error"] = "uploaded"
    chunk_size: int = 1024
    chunk_overlap: int = 128
    chunk_count: int = 0
    chunk_min_chars: int = 0
    chunk_max_chars: int = 0
    chunk_avg_chars: float = 0.0
    chunk_total_chars: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Identificadores de deduplicação
    # file_hash: SHA-256 dos bytes crus do arquivo — identidade do conteúdo, independente de nome ou configurações
    # config_hash: SHA-256 de (file_hash + parâmetros de chunking + configuração de embedding) — único por
    #              combinação (conteúdo × configuração de ingestão); usado para pular reingestão
    #              e como futura chave para compartilhar chunks indexados entre agentes
    file_hash: str = ""
    config_hash: str = ""

    def mark_processed(self, chunks: list) -> None:
        sizes = [len(c.text) for c in chunks]
        self.status = "processed"
        self.chunk_count = len(sizes)
        self.chunk_min_chars = min(sizes) if sizes else 0
        self.chunk_max_chars = max(sizes) if sizes else 0
        self.chunk_total_chars = sum(sizes)
        self.chunk_avg_chars = round(self.chunk_total_chars / len(sizes), 1) if sizes else 0.0
