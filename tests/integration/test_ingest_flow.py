"""Integration test for the ingest flow using in-memory mocks."""

import pytest
from unittest.mock import AsyncMock

from app.application.use_cases.ingest_documents import IngestDocumentsUseCase
from app.application.dtos.document_dtos import IngestDocumentInput
from app.application.services.parsing_service import ParsingService
from app.application.services.chunking_service import ChunkingService


@pytest.mark.asyncio
async def test_ingest_txt_document(sample_agent, mock_agent_repo, mock_memory, mock_storage=None):
    """End-to-end ingest with real parsing/chunking services and mock infra."""
    mock_storage = AsyncMock()
    mock_document_repo = AsyncMock()
    mock_document_repo.find_by_config_hash.return_value = None
    mock_memory.ingest_chunks.return_value = 3
    mock_memory.get_memory_version.return_value = "abc12345"
    mock_agent_repo.find_by_id.return_value = sample_agent

    use_case = IngestDocumentsUseCase(
        agent_repo=mock_agent_repo,
        document_repo=mock_document_repo,
        storage=mock_storage,
        memory=mock_memory,
        parsing_service=ParsingService(),
        chunking_service=ChunkingService(),
    )

    txt_content = b"This is a test document. " * 20  # ~500 chars

    result = await use_case.execute(
        IngestDocumentInput(
            agent_id=sample_agent.id,
            filename="test.txt",
            content_type="text/plain",
            file_data=txt_content,
        )
    )

    assert result.status == "processed"
    assert result.filename == "test.txt"
    assert result.chunks_created == 3
    mock_storage.upload_file.assert_called_once()
    mock_agent_repo.update.assert_called_once()
