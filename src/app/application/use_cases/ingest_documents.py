"""Caso de uso: ingerir documento e indexar na memória."""

import hashlib
import structlog

from app.domain.entities.document import Document
from app.domain.ports.agent_repository_port import AgentRepositoryPort
from app.domain.ports.document_repository_port import DocumentRepositoryPort
from app.domain.ports.storage_port import StoragePort
from app.domain.ports.memory_port import MemoryPort
from app.domain.exceptions import AgentNotFoundError
from app.application.dtos.document_dtos import IngestDocumentInput, IngestResult
from app.application.services import benchmark_timing as bt
from app.application.services.parsing_service import ParsingService
from app.application.services.chunking_service import ChunkingService
from app.settings import settings

logger = structlog.get_logger()


def _compute_hashes(
    file_data: bytes,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[str, str]:
    """
    Retorna (file_hash, config_hash).

    file_hash   — SHA-256 dos bytes crus do arquivo; identifica o conteúdo independente de nome ou configurações.
    config_hash — SHA-256 de "{file_hash}|{chunk_size}|{chunk_overlap}|{embedding_enabled}|{model}";
                  muda sempre que a configuração de ingestão muda, permitindo reingestão segura
                  com parâmetros de chunk ou modelos de embedding diferentes.
    """
    file_hash = hashlib.sha256(file_data).hexdigest()
    embedding_tag = (
        f"embed:{settings.embedding_model}"
        if settings.embedding_enabled
        else "embed:none"
    )
    config_str = f"{file_hash}|{chunk_size}|{chunk_overlap}|{embedding_tag}"
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()
    return file_hash, config_hash


class IngestDocumentsUseCase:

    def __init__(
        self,
        agent_repo: AgentRepositoryPort,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
        memory: MemoryPort,
        parsing_service: ParsingService,
        chunking_service: ChunkingService,
    ):
        self._agent_repo = agent_repo
        self._document_repo = document_repo
        self._storage = storage
        self._memory = memory
        self._parser = parsing_service
        self._chunker = chunking_service

    async def execute(self, input_dto: IngestDocumentInput) -> IngestResult:
        """Ponto de entrada público. Em modo benchmark, abre uma sessão de
        cronometragem por etapa e anexa os tempos coletados ao IngestResult."""
        if not input_dto.benchmark_mode:
            return await self._execute_inner(input_dto)

        with bt.session() as timings:
            with bt.stage("t_total"):
                result = await self._execute_inner(input_dto)
            result.timings = timings
            return result

    async def _execute_inner(self, input_dto: IngestDocumentInput) -> IngestResult:
        agent = await self._agent_repo.find_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)

        # ── 1. Extrai o texto (necessário para autodetectar os parâmetros de chunk) ──
        with bt.stage("t_parsing"):
            pages = self._parser.extract_text(
                file_data=input_dto.file_data,
                content_type=input_dto.content_type,
                filename=input_dto.filename,
            )

        # ── 2. Resolve os parâmetros finais de chunk ─────────────────────────────
        chunk_size, chunk_overlap = self._chunker.resolve_params(
            input_dto.chunk_size, input_dto.chunk_overlap, pages
        )

        # ── 3. Calcula os hashes e verifica duplicidade ──────────────────────────
        file_hash, config_hash = _compute_hashes(
            input_dto.file_data, chunk_size, chunk_overlap
        )

        existing = await self._document_repo.find_by_config_hash(agent.id, config_hash)
        if existing:
            logger.info(
                "ingest_skipped_duplicate",
                agent_id=agent.id,
                filename=input_dto.filename,
                config_hash=config_hash,
            )
            return IngestResult(
                agent_id=agent.id,
                document_id=existing.id,
                filename=input_dto.filename,
                chunks_created=existing.chunk_count,
                status="skipped",
                file_hash=file_hash,
                config_hash=config_hash,
            )

        # ── 4. Faz upload do arquivo original para o storage ─────────────────────
        s3_key = f"docs/{agent.id}/{input_dto.filename}"
        await self._storage.upload_file(
            bucket=settings.s3_bucket_name,
            key=s3_key,
            data=input_dto.file_data,
        )
        logger.info("document_uploaded", agent_id=agent.id, s3_key=s3_key)

        # ── 5. Divide em chunks, gera embeddings e indexa ────────────────────────
        with bt.stage("t_chunking"):
            chunks = self._chunker.split(pages, chunk_size, chunk_overlap)
        logger.info("document_chunked", agent_id=agent.id, chunks=len(chunks))

        total_indexed = await self._memory.ingest_chunks(
            agent.id, chunks, embed=settings.embedding_enabled
        )

        # ── 6. Persiste o registro do documento ───────────────────────────────────
        doc = Document(
            agent_id=agent.id,
            filename=input_dto.filename,
            content_type=input_dto.content_type,
            size_bytes=len(input_dto.file_data),
            s3_key=s3_key,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            file_hash=file_hash,
            config_hash=config_hash,
        )
        doc.mark_processed(chunks)
        await self._document_repo.save(doc)

        # ── 7. Atualiza o estado do agente ────────────────────────────────────────
        version = await self._memory.get_memory_version(agent.id)
        agent.increment_documents()
        agent.mark_as_ready(total_chunks=total_indexed, memory_version=version)
        await self._agent_repo.update(agent)

        logger.info("ingestion_complete", agent_id=agent.id, chunks=total_indexed, version=version)

        return IngestResult(
            agent_id=agent.id,
            document_id=doc.id,
            filename=input_dto.filename,
            chunks_created=total_indexed,
            status="processed",
            file_hash=file_hash,
            config_hash=config_hash,
        )
